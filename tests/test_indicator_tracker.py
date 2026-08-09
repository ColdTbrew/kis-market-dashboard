from __future__ import annotations

import json
import sys
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from indicator_tracker_data import (
    KST,
    add_technicals,
    build_flow_series,
    build_report,
    load_toss_credentials,
    normalize_candles,
    build_index_candles,
    weekly_candles,
)
from indicator_tracker_discord import (
    DiscordDeliveryError,
    load_discord_webhook_url,
    send_discord_batch,
    split_delivery_batches,
)
import indicator_tracker_render as render_module
from indicator_tracker_render import OUTPUT_HEIGHT, OUTPUT_WIDTH, render_report


def make_candles(count: int, start: date = date(2023, 1, 2)) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        value = 100 + index * 0.3 + (index % 7) * 0.2
        day = start + timedelta(days=index)
        rows.append(
            {
                "timestamp": f"{day.isoformat()}T09:00:00+09:00",
                "date": day.isoformat(),
                "open": value - 0.4,
                "high": value + 1.0,
                "low": value - 1.0,
                "close": value,
                "volume": 1_000_000 + index,
            }
        )
    return rows


def make_investor_records(count: int = 20) -> list[dict[str, object]]:
    def amount(buy: float, sell: float) -> dict[str, str]:
        return {"buyAmount": str(int(buy)), "sellAmount": str(int(sell))}

    records = []
    for index in range(count):
        day = date(2025, 1, 3) + timedelta(days=index * 7)
        records.append(
            {
                "date": day.isoformat(),
                "updatedAt": f"{day.isoformat()}T18:10:00+09:00",
                "foreigner": amount(20_000 + index * 50, 21_000),
                "individual": amount(22_000, 20_000 + index * 20),
                "institution": {
                    **amount(19_000 + index * 10, 18_000),
                    "breakdown": {"pensionFund": amount(3_000 + index * 5, 2_500)},
                },
                "otherCorporation": amount(1_000, 900),
            }
        )
    return records


class FakeToss:
    def __init__(self) -> None:
        self.daily = make_candles(900)

    def investor_trading(self, symbol: str, *, count: int) -> list[dict[str, object]]:
        assert symbol == "KOSPI"
        return make_investor_records(count=20)

    def candles(self, symbol: str, *, count: int, indicator: bool = False) -> list[dict[str, object]]:
        assert symbol in {"KOSPI", "KOSDAQ", "KR_BOND_3Y", "005930", "000660", "GLD", "ONEQ", "SPY"}
        return self.daily[-count:]


def fake_fred(series_id: str, *, count: int) -> list[dict[str, object]]:
    assert series_id in {"DEXKOUS", "DEXJPUS", "DGS10", "NASDAQCOM", "SP500"}
    start = date(2023, 1, 2)
    return [
        {"date": (start + timedelta(days=index)).isoformat(), "value": 3.0 + index * 0.002}
        for index in range(count)
    ]


def test_load_toss_credentials_from_openclaw_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TOSS_CLIENT_ID", raising=False)
    monkeypatch.delenv("TOSS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("TOSS_BASE_URL", raising=False)
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            {
                "providers": {
                    "toss": {
                        "client_id": "client",
                        "client_secret": "secret",
                        "base_url": "https://openapi.tossinvest.com",
                    }
                }
            }
        )
    )

    credentials = load_toss_credentials(secrets)

    assert credentials["client_id"] == "client"
    assert credentials["client_secret"] == "secret"


def test_normalize_weekly_and_technical_indicators() -> None:
    raw = [
        {
            "timestamp": f"2026-01-{day:02d}T09:00:00+09:00",
            "openPrice": str(100 + day),
            "highPrice": str(102 + day),
            "lowPrice": str(99 + day),
            "closePrice": str(101 + day),
            "volume": "10",
        }
        for day in range(1, 29)
    ]
    daily = normalize_candles(reversed(raw))
    technical = add_technicals(daily)
    weekly = weekly_candles(daily)

    assert daily[0]["date"] == "2026-01-01"
    assert technical[18]["ma20"] is None
    assert technical[19]["ma20"] is not None
    assert technical[19]["bb_upper"] > technical[19]["bb_lower"]
    assert len(weekly) == 5
    assert weekly[0]["open"] == daily[0]["open"]

    ichimoku = add_technicals(make_candles(60), ichimoku=True)
    assert ichimoku[8]["ichimoku_tenkan"] is not None
    assert ichimoku[25]["ichimoku_kijun"] is not None
    assert ichimoku[25]["ichimoku_span_a"] is not None
    assert ichimoku[51]["ichimoku_span_b"] is not None


def test_build_index_candles_uses_shared_dates_and_fred_close() -> None:
    fred = [
        {"date": "2026-01-02", "value": 100.0},
        {"date": "2026-01-03", "value": 110.0},
        {"date": "2026-01-04", "value": 120.0},
    ]
    etf = [
        {"date": "2026-01-02", "open": 9.0, "high": 12.0, "low": 8.0, "close": 10.0},
        # This row is omitted because it has no valid denominator.
        {"date": "2026-01-03", "open": 10.0, "high": 11.0, "low": 9.0, "close": 0.0},
        # This date is not present in FRED and must not be fabricated.
        {"date": "2026-01-05", "open": 20.0, "high": 21.0, "low": 19.0, "close": 20.0},
    ]

    candles = build_index_candles(fred, etf)

    assert [row["date"] for row in candles] == ["2026-01-02"]
    assert candles[0]["close"] == 100.0
    assert candles[0]["open"] == 90.0
    assert candles[0]["high"] == 120.0
    assert candles[0]["low"] == 80.0
    assert candles[0]["volume"] == 0


def test_ichimoku_render_has_expected_series_and_legend(monkeypatch) -> None:
    series_colors: list[str] = []
    legend_items: list[tuple[str, str]] = []

    def capture_series(_draw, _values, *, color: str, **_kwargs) -> None:
        series_colors.append(color)

    def capture_legend(_draw, *, items, **_kwargs) -> None:
        legend_items.extend(items)

    monkeypatch.setattr(render_module, "_draw_series", capture_series)
    monkeypatch.setattr(render_module, "_draw_legend_grid", capture_legend)
    image, draw = render_module._new_canvas()
    render_module.draw_market_chart(
        draw,
        (
            render_module.MARGIN,
            render_module.MARGIN,
            render_module.WIDTH - render_module.MARGIN,
            render_module.MARGIN + render_module.CARD_HEIGHT,
        ),
        {
            "title": "KOSPI (주)",
            "updated_date": "2026-08-08",
            "source": "test",
            "unit": "pt",
            "precision": 2,
            "kind": "line",
            "ichimoku": True,
            "data": add_technicals(make_candles(60), ichimoku=True),
        },
    )

    assert {
        render_module.ICHIMOKU_TENKAN,
        render_module.ICHIMOKU_KIJUN,
        render_module.ICHIMOKU_SPAN_A,
        render_module.ICHIMOKU_SPAN_B,
    }.issubset(series_colors)
    assert len(series_colors) == 10
    assert [label for label, _color in legend_items] == [
        "MA20",
        "MA60",
        "MA120",
        "BB20",
        "전환선",
        "기준선",
        "구름",
    ]
    image.close()


def test_flow_series_builds_cumulative_values_and_four_week_average() -> None:
    rows = build_flow_series(make_investor_records(6))

    assert rows[0]["foreigner_cumulative"] == -1_000
    assert rows[3]["foreigner_ma4"] is not None
    assert rows[-1]["individual_cumulative"] > 0
    assert rows[-1]["pension_cumulative"] > 0


def test_build_and_render_individual_chart_images(tmp_path: Path) -> None:
    report = build_report(
        FakeToss(),
        fred_loader=fake_fred,
        now=datetime(2026, 8, 8, 18, 0, tzinfo=KST),
    )

    paths = render_report(report, tmp_path)

    assert report["policy"] == "fixed_sources_no_fallback"
    assert len(report["kr_charts"]) == 5
    assert len(report["us_charts"]) == 4
    assert len(report["macro_charts"]) == 5
    assert [chart["id"] for chart in report["us_charts"]] == [
        "nasdaq_daily",
        "nasdaq_weekly",
        "sp500_daily",
        "sp500_weekly",
    ]
    assert all(chart["kind"] == "candles" for chart in report["us_charts"])
    assert all(chart["market"] == "us" for chart in report["us_charts"])
    assert report["us_charts"][0]["source"] == "FRED NASDAQCOM 종가 · Toss ONEQ OHLC 합성"
    assert report["us_charts"][2]["source"] == "FRED SP500 종가 · Toss SPY OHLC 합성"
    weekly_charts = [
        chart
        for group in (report["kr_charts"], report["us_charts"], report["macro_charts"])
        for chart in group
        if chart["timeframe"] == "weekly"
    ]
    assert len(weekly_charts) == 6
    ichimoku_charts = [chart for chart in weekly_charts if chart["ichimoku"]]
    assert [chart["id"] for chart in ichimoku_charts] == [
        "kospi_weekly",
        "nasdaq_weekly",
        "sp500_weekly",
    ]
    assert all(
        "ichimoku_span_b" in chart["data"][-1]
        for chart in ichimoku_charts
    )
    assert all(
        "ichimoku_tenkan" not in chart["data"][-1]
        for chart in weekly_charts
        if not chart["ichimoku"]
    )
    assert "ichimoku_tenkan" not in report["kr_charts"][0]["data"][-1]
    assert [path.name for path in paths] == [
        "indicator_tracker.20260808.01_foreigner_flow.png",
        "indicator_tracker.20260808.02_investor_flow.png",
        "indicator_tracker.20260808.03_kospi_daily.png",
        "indicator_tracker.20260808.04_kospi_weekly.png",
        "indicator_tracker.20260808.05_kosdaq.png",
        "indicator_tracker.20260808.06_samsung.png",
        "indicator_tracker.20260808.07_sk_hynix.png",
        "indicator_tracker.20260808.08_nasdaq_daily.png",
        "indicator_tracker.20260808.09_nasdaq_weekly.png",
        "indicator_tracker.20260808.10_sp500_daily.png",
        "indicator_tracker.20260808.11_sp500_weekly.png",
        "indicator_tracker.20260808.12_usdkrw.png",
        "indicator_tracker.20260808.13_usdjpy.png",
        "indicator_tracker.20260808.14_us10y.png",
        "indicator_tracker.20260808.15_kr3y.png",
        "indicator_tracker.20260808.16_gold.png",
    ]
    assert (OUTPUT_WIDTH, OUTPUT_HEIGHT) == (1206, 1407)
    for path in paths:
        assert path.stat().st_size > 10_000
        with Image.open(path) as image:
            assert image.size == (OUTPUT_WIDTH, OUTPUT_HEIGHT)


def test_discord_batches_group_domestic_us_indices_and_macro() -> None:
    paths = [Path(f"chart-{index}.png") for index in range(16)]

    batches = split_delivery_batches(paths)

    assert [(label, len(batch)) for label, batch in batches] == [
        ("수급·국내시장", 7),
        ("미국 주가지수", 4),
        ("환율·금리·금", 5),
    ]


def test_load_discord_webhook_url_from_openclaw_secrets(tmp_path: Path) -> None:
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            {
                "providers": {
                    "discord": {
                        "indicator_tracker_webhook_url": "https://discord.com/api/webhooks/123/secret"
                    }
                }
            }
        )
    )

    assert load_discord_webhook_url(secrets) == (
        "https://discord.com/api/webhooks/123/secret"
    )


def test_load_discord_webhook_url_has_no_environment_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv(
        "DISCORD_WEBHOOK_URL",
        "https://discord.com/api/webhooks/123/environment-secret",
    )

    with pytest.raises(DiscordDeliveryError, match="시크릿"):
        load_discord_webhook_url(tmp_path / "missing.json")


def test_send_discord_batch_adds_wait_true_without_clobbering_query(
    tmp_path: Path, monkeypatch
) -> None:
    image = tmp_path / "chart.png"
    image.write_bytes(b"png")
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return b'{"id":"message-id"}'

    def fake_urlopen(request, *, timeout: int):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("indicator_tracker_discord.urllib.request.urlopen", fake_urlopen)

    assert send_discord_batch(
        [image],
        message="report",
        webhook_url="https://discord.com/api/webhooks/123/secret?thread_id=9",
    ) == "message-id"
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(captured["url"]).query)
    assert query == {"thread_id": ["9"], "wait": ["true"]}
