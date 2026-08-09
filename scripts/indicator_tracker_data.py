#!/usr/bin/env python3
"""Collect and normalize the fixed-source indicator tracker dataset."""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
DEFAULT_SECRETS_PATH = Path("~/.openclaw/secrets.json").expanduser()
DEFAULT_TOSS_BASE_URL = "https://openapi.tossinvest.com"
ALLOWED_TOSS_HOSTS = {"openapi.tossinvest.com"}
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
DAILY_POINTS = 180
WEEKLY_SOURCE_POINTS = 780


class DataSourceError(RuntimeError):
    """Raised when a fixed report data source cannot be read."""


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise DataSourceError(f"숫자 변환 실패: {value!r}") from exc


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 30,
) -> bytes:
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("User-Agent", "kis-market-dashboard/indicator-tracker")
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    delays = (1.0, 2.0, 4.0)
    for attempt in range(len(delays) + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raw_body = exc.read()
            if exc.headers.get("Content-Encoding", "").lower() == "gzip" or raw_body.startswith(b"\x1f\x8b"):
                try:
                    raw_body = gzip.decompress(raw_body)
                except OSError:
                    pass
            body = raw_body.decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt < len(delays):
                retry_after = exc.headers.get("Retry-After", "")
                try:
                    wait_seconds = max(delays[attempt], float(retry_after))
                except ValueError:
                    wait_seconds = delays[attempt]
                time.sleep(wait_seconds)
                continue
            if exc.code == 403 and "IP address not allowed" in body:
                raise DataSourceError(
                    "Toss가 현재 공인 IP를 허용하지 않았습니다. "
                    "Toss WTS > 설정 > Open API > 허용 IP에 현재 IP를 등록하세요."
                ) from exc
            raise DataSourceError(f"HTTP {exc.code} ({url}): {body[:500]}") from exc
        except urllib.error.URLError as exc:
            if attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            raise DataSourceError(f"네트워크 요청 실패 ({url}): {exc.reason}") from exc

    raise AssertionError("unreachable")


def load_toss_credentials(secrets_path: Path = DEFAULT_SECRETS_PATH) -> dict[str, str]:
    provider: dict[str, Any] = {}
    if secrets_path.exists():
        try:
            root = json.loads(secrets_path.read_text(encoding="utf-8"))
            provider = root.get("providers", {}).get("toss", {})
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise DataSourceError(f"Toss 시크릿 파일을 읽을 수 없습니다: {secrets_path}") from exc

    client_id = os.getenv("TOSS_CLIENT_ID", "").strip() or str(provider.get("client_id", "")).strip()
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip() or str(
        provider.get("client_secret", "")
    ).strip()
    base_url = (
        os.getenv("TOSS_BASE_URL", "").strip()
        or str(provider.get("base_url", "")).strip()
        or DEFAULT_TOSS_BASE_URL
    ).rstrip("/")

    if not client_id or not client_secret:
        raise DataSourceError(
            "Toss 키가 없습니다. ~/.openclaw/secrets.json의 "
            "providers.toss.client_id/client_secret에 입력하세요."
        )

    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_TOSS_HOSTS:
        raise DataSourceError(f"허용되지 않은 Toss API 주소입니다: {base_url}")
    return {"client_id": client_id, "client_secret": client_secret, "base_url": base_url}


class TossClient:
    def __init__(self, credentials: dict[str, str]):
        self.client_id = credentials["client_id"]
        self.client_secret = credentials["client_secret"]
        self.base_url = credentials["base_url"]
        self._access_token = ""

    def issue_token(self) -> str:
        form = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        body = _request(
            f"{self.base_url}/oauth2/token",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=form,
        )
        try:
            payload = json.loads(body)
            token = str(payload["access_token"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DataSourceError("Toss 토큰 응답 형식이 올바르지 않습니다.") from exc
        self._access_token = token
        return token

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._access_token:
            self.issue_token()
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{self.base_url}{path}?{query}"
        body = _request(url, headers={"Authorization": f"Bearer {self._access_token}"})
        try:
            payload = json.loads(body)
            result = payload["result"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise DataSourceError(f"Toss 응답 형식이 올바르지 않습니다: {path}") from exc
        if not isinstance(result, dict):
            raise DataSourceError(f"Toss result 형식이 올바르지 않습니다: {path}")
        return result

    def candles(self, symbol: str, *, count: int, indicator: bool = False) -> list[dict[str, Any]]:
        path = (
            f"/api/v1/market-indicators/{symbol}/candles"
            if indicator
            else "/api/v1/candles"
        )
        rows: dict[str, dict[str, Any]] = {}
        before: str | None = None
        while len(rows) < count:
            page_size = min(200, count - len(rows) + (1 if rows else 0))
            params: dict[str, Any] = {
                "interval": "1d",
                "count": page_size,
                "before": before,
            }
            if not indicator:
                params.update({"symbol": symbol, "adjusted": "true"})
            result = self.get(path, params)
            candles = result.get("candles", [])
            if not isinstance(candles, list):
                raise DataSourceError(f"Toss 캔들 목록 형식 오류: {symbol}")
            for candle in candles:
                timestamp = str(candle.get("timestamp", ""))
                if timestamp:
                    rows[timestamp] = candle
            next_before = result.get("nextBefore")
            if not next_before or next_before == before or not candles:
                break
            before = str(next_before)
        normalized = normalize_candles(rows.values())
        if not normalized:
            raise DataSourceError(f"Toss 캔들 데이터가 비어 있습니다: {symbol}")
        return normalized[-count:]

    def investor_trading(self, symbol: str = "KOSPI", *, count: int = 100) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        until: str | None = None
        while len(rows) < count:
            result = self.get(
                f"/api/v1/market-indicators/{symbol}/investor-trading",
                {"interval": "1w", "count": min(100, count), "until": until},
            )
            records = result.get("records", [])
            if not isinstance(records, list):
                raise DataSourceError("Toss 투자자 수급 응답 형식 오류")
            for record in records:
                record_date = str(record.get("date", ""))
                if record_date:
                    rows[record_date] = record
            next_until = result.get("nextUntil")
            if not next_until or next_until == until or not records:
                break
            until = str(next_until)
        records = [rows[key] for key in sorted(rows)][-count:]
        if not records:
            raise DataSourceError("Toss 투자자 수급 데이터가 비어 있습니다.")
        return records


def normalize_candles(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        timestamp = str(row.get("timestamp", ""))
        if not timestamp:
            continue
        normalized[timestamp] = {
            "timestamp": timestamp,
            "date": _parse_timestamp(timestamp).date().isoformat(),
            "open": _as_float(row.get("openPrice")),
            "high": _as_float(row.get("highPrice")),
            "low": _as_float(row.get("lowPrice")),
            "close": _as_float(row.get("closePrice")),
            "volume": _as_float(row.get("volume", 0)),
        }
    return [normalized[key] for key in sorted(normalized)]


def weekly_candles(candles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for candle in sorted(candles, key=lambda item: item["date"]):
        parsed = date.fromisoformat(candle["date"])
        iso = parsed.isocalendar()
        groups.setdefault((iso.year, iso.week), []).append(candle)

    output: list[dict[str, Any]] = []
    for group in groups.values():
        output.append(
            {
                "timestamp": group[-1]["timestamp"],
                "date": group[-1]["date"],
                "open": group[0]["open"],
                "high": max(item["high"] for item in group),
                "low": min(item["low"] for item in group),
                "close": group[-1]["close"],
                "volume": sum(item.get("volume", 0) for item in group),
            }
        )
    return output


def _range_midpoint(
    candles: list[dict[str, Any]],
    index: int,
    period: int,
) -> float | None:
    window = candles[max(0, index - period + 1) : index + 1]
    if len(window) < period:
        return None
    return (
        max(float(candle["high"]) for candle in window)
        + min(float(candle["low"]) for candle in window)
    ) / 2


def add_technicals(
    candles: Iterable[dict[str, Any]],
    *,
    ichimoku: bool = False,
) -> list[dict[str, Any]]:
    output = [dict(candle) for candle in candles]
    closes = [float(candle["close"]) for candle in output]
    for index, candle in enumerate(output):
        for period in (20, 60, 120):
            window = closes[max(0, index - period + 1) : index + 1]
            candle[f"ma{period}"] = fmean(window) if len(window) == period else None
        bollinger = closes[max(0, index - 19) : index + 1]
        if len(bollinger) == 20:
            center = fmean(bollinger)
            deviation = pstdev(bollinger)
            candle["bb_upper"] = center + deviation * 2
            candle["bb_lower"] = center - deviation * 2
        else:
            candle["bb_upper"] = None
            candle["bb_lower"] = None
        if ichimoku:
            tenkan = _range_midpoint(output, index, 9)
            kijun = _range_midpoint(output, index, 26)
            candle["ichimoku_tenkan"] = tenkan
            candle["ichimoku_kijun"] = kijun
            candle["ichimoku_span_a"] = (
                (tenkan + kijun) / 2
                if tenkan is not None and kijun is not None
                else None
            )
            candle["ichimoku_span_b"] = _range_midpoint(output, index, 52)
    return output


def fetch_fred_series(series_id: str, *, count: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"id": series_id})
    body = _request(f"{FRED_CSV_URL}?{query}")
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or series_id not in reader.fieldnames:
        raise DataSourceError(f"FRED CSV 형식 오류: {series_id}")
    date_column = "DATE" if "DATE" in reader.fieldnames else "observation_date"
    rows: list[dict[str, Any]] = []
    for row in reader:
        raw = str(row.get(series_id, "")).strip()
        if not raw or raw == ".":
            continue
        row_date = str(row.get(date_column, ""))
        if not row_date:
            continue
        value = _as_float(raw)
        rows.append({"date": row_date, "value": value})
    if not rows:
        raise DataSourceError(f"FRED 데이터가 비어 있습니다: {series_id}")
    return rows[-count:]


def scalar_candles(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": f"{row['date']}T00:00:00+00:00",
            "date": row["date"],
            "open": row["value"],
            "high": row["value"],
            "low": row["value"],
            "close": row["value"],
            "volume": 0,
        }
        for row in rows
    ]


def build_index_candles(
    fred_rows: Iterable[dict[str, Any]],
    etf_candles: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build index OHLC candles from FRED closes and matching ETF price ratios."""

    etf_by_date: dict[str, dict[str, Any]] = {}
    for candle in etf_candles:
        candle_date = str(candle.get("date", "")).strip()
        if candle_date:
            etf_by_date[candle_date] = candle

    output: list[dict[str, Any]] = []
    fred_by_date: dict[str, dict[str, Any]] = {}
    for row in fred_rows:
        row_date = str(row.get("date", "")).strip()
        if row_date:
            fred_by_date[row_date] = row

    for row_date in sorted(fred_by_date):
        etf = etf_by_date.get(row_date)
        if etf is None:
            continue
        try:
            fred_close = _as_float(fred_by_date[row_date].get("value"))
            etf_open = _as_float(etf.get("open"))
            etf_high = _as_float(etf.get("high"))
            etf_low = _as_float(etf.get("low"))
            etf_close = _as_float(etf.get("close"))
        except DataSourceError:
            # Skip bad rows instead of inventing prices.
            continue
        if (
            not all(math.isfinite(value) for value in (fred_close, etf_open, etf_high, etf_low, etf_close))
            or etf_close == 0
        ):
            continue

        output.append(
            {
                "timestamp": f"{row_date}T00:00:00+00:00",
                "date": row_date,
                "open": fred_close * etf_open / etf_close,
                "high": fred_close * etf_high / etf_close,
                "low": fred_close * etf_low / etf_close,
                "close": fred_close,
                # ETF volume is not index volume.
                "volume": 0,
            }
        )
    return output


def _net_amount(item: dict[str, Any]) -> float:
    return _as_float(item.get("buyAmount")) - _as_float(item.get("sellAmount"))


def build_flow_series(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    cumulative = {"foreigner": 0.0, "individual": 0.0, "institution": 0.0, "pension": 0.0}
    output: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item["date"]):
        institution = record["institution"]
        pension = institution["breakdown"]["pensionFund"]
        weekly = {
            "foreigner": _net_amount(record["foreigner"]),
            "individual": _net_amount(record["individual"]),
            "institution": _net_amount(institution),
            "pension": _net_amount(pension),
        }
        for key, value in weekly.items():
            cumulative[key] += value
        point = {"date": record["date"], "updated_at": record.get("updatedAt", ""), **weekly}
        point.update({f"{key}_cumulative": value for key, value in cumulative.items()})
        output.append(point)

    foreigner_cumulative = [row["foreigner_cumulative"] for row in output]
    for index, row in enumerate(output):
        window = foreigner_cumulative[max(0, index - 3) : index + 1]
        row["foreigner_ma4"] = fmean(window) if len(window) == 4 else None
    return output


def _chart(
    chart_id: str,
    title: str,
    source: str,
    unit: str,
    candles: list[dict[str, Any]],
    *,
    precision: int = 2,
    kind: str = "candles",
    timeframe: str = "daily",
    ichimoku: bool = False,
    market: str | None = None,
) -> dict[str, Any]:
    if len(candles) < 2:
        raise DataSourceError(f"차트 데이터가 부족합니다: {chart_id}")
    chart = {
        "id": chart_id,
        "title": title,
        "source": source,
        "unit": unit,
        "precision": precision,
        "kind": kind,
        "timeframe": timeframe,
        "ichimoku": ichimoku,
        "updated_date": candles[-1]["date"],
        "data": add_technicals(candles, ichimoku=ichimoku),
    }
    if market:
        chart["market"] = market
    return chart


def _daily_weekly_lines(
    chart_id: str,
    title: str,
    source: str,
    candles: list[dict[str, Any]],
    *,
    kind: str = "line",
    market: str | None = None,
) -> list[dict[str, Any]]:
    return [
        _chart(
            f"{chart_id}_daily",
            f"{title} (일)",
            source,
            "pt",
            candles[-DAILY_POINTS:],
            kind=kind,
            market=market,
        ),
        _chart(
            f"{chart_id}_weekly",
            f"{title} (주)",
            source,
            "pt",
            weekly_candles(candles),
            kind=kind,
            timeframe="weekly",
            ichimoku=True,
            market=market,
        ),
    ]


def build_report(
    toss: TossClient,
    *,
    fred_loader: Callable[..., list[dict[str, Any]]] = fetch_fred_series,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (now or datetime.now(KST)).astimezone(KST)

    investor = build_flow_series(toss.investor_trading("KOSPI", count=100))
    if len(investor) < 4:
        raise DataSourceError("수급 차트를 그릴 데이터가 부족합니다.")

    kospi_daily = toss.candles("KOSPI", count=WEEKLY_SOURCE_POINTS, indicator=True)
    kr_charts = [
        _chart(
            "kospi_daily",
            "코스피 (일)",
            "Toss KOSPI",
            "pt",
            kospi_daily[-DAILY_POINTS:],
        ),
        _chart(
            "kospi_weekly",
            "코스피 (주)",
            "Toss KOSPI",
            "pt",
            weekly_candles(kospi_daily),
            timeframe="weekly",
            ichimoku=True,
        ),
        _chart(
            "kosdaq",
            "코스닥 (일)",
            "Toss KOSDAQ",
            "pt",
            toss.candles("KOSDAQ", count=DAILY_POINTS, indicator=True),
        ),
        _chart(
            "samsung",
            "삼성전자 (일)",
            "Toss 005930",
            "원",
            toss.candles("005930", count=DAILY_POINTS),
            precision=0,
        ),
        _chart(
            "sk_hynix",
            "SK하이닉스 (일)",
            "Toss 000660",
            "원",
            toss.candles("000660", count=DAILY_POINTS),
            precision=0,
        ),
    ]

    nasdaq_daily = build_index_candles(
        fred_loader("NASDAQCOM", count=WEEKLY_SOURCE_POINTS),
        toss.candles("ONEQ", count=WEEKLY_SOURCE_POINTS),
    )
    sp500_daily = build_index_candles(
        fred_loader("SP500", count=WEEKLY_SOURCE_POINTS),
        toss.candles("SPY", count=WEEKLY_SOURCE_POINTS),
    )
    us_charts = [
        *_daily_weekly_lines(
            "nasdaq",
            "나스닥 종합",
            "FRED NASDAQCOM 종가 · Toss ONEQ OHLC 합성",
            nasdaq_daily,
            kind="candles",
            market="us",
        ),
        *_daily_weekly_lines(
            "sp500",
            "S&P 500",
            "FRED SP500 종가 · Toss SPY OHLC 합성",
            sp500_daily,
            kind="candles",
            market="us",
        ),
    ]

    usdkrw = scalar_candles(fred_loader("DEXKOUS", count=DAILY_POINTS))
    usdjpy = scalar_candles(fred_loader("DEXJPUS", count=DAILY_POINTS))
    us10y = weekly_candles(
        scalar_candles(fred_loader("DGS10", count=WEEKLY_SOURCE_POINTS))
    )
    kr3y = weekly_candles(toss.candles("KR_BOND_3Y", count=520, indicator=True))
    gold = weekly_candles(toss.candles("GLD", count=520))

    macro_charts = [
        _chart("usdkrw", "원/달러 환율 (일)", "FRED DEXKOUS", "원", usdkrw, kind="line"),
        _chart("usdjpy", "달러/엔 (일)", "FRED DEXJPUS", "엔", usdjpy, kind="line"),
        _chart(
            "us10y",
            "미국채 10년 금리 (주)",
            "FRED DGS10",
            "%",
            us10y,
            timeframe="weekly",
        ),
        _chart(
            "kr3y",
            "국고채 3년 금리 (주)",
            "Toss KR_BOND_3Y",
            "%",
            kr3y,
            timeframe="weekly",
        ),
        _chart(
            "gold",
            "금 (GLD·주)",
            "Toss GLD",
            "$",
            gold,
            timeframe="weekly",
        ),
    ]

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "policy": "fixed_sources_no_fallback",
        "flows": {
            "title": "코스피 투자자 수급 (주)",
            "source": "Toss KOSPI investor-trading",
            "updated_date": investor[-1]["date"],
            "data": investor,
        },
        "kr_charts": kr_charts,
        "us_charts": us_charts,
        "macro_charts": macro_charts,
    }
