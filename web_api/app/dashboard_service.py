from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_WATCHLISTS = {
    "kr": [
        {"type": "stock", "name": "Samsung Elec.", "code": "005930", "market": "005930"},
        {"type": "stock", "name": "SK Hynix", "code": "000660", "market": "000660"},
        {"type": "stock", "name": "SK Telecom", "code": "017670", "market": "017670"},
        {"type": "stock", "name": "Hyundai Motor", "code": "005380", "market": "005380"},
    ],
    "us": [
        {"type": "stock", "name": "Apple", "code": "AAPL", "market": "NASDAQ", "excd": "NAS"},
        {"type": "stock", "name": "Microsoft", "code": "MSFT", "market": "NASDAQ", "excd": "NAS"},
        {"type": "stock", "name": "NVIDIA", "code": "NVDA", "market": "NASDAQ", "excd": "NAS"},
        {"type": "stock", "name": "Tesla", "code": "TSLA", "market": "NASDAQ", "excd": "NAS"},
    ],
}

SUMMARY_ITEMS_BY_MARKET = {
    "kr": [
        {"type": "kr_index", "name": "KOSPI", "code": "0001", "market": "KOSPI"},
        {"type": "kr_index", "name": "KOSDAQ", "code": "1001", "market": "KOSDAQ"},
        {"type": "overseas_index", "name": "NASDAQ", "code": "NDX", "market": "NASDAQ-100", "label": "전일 종가", "price_digits": 2},
        {"type": "fx", "name": "USD/KRW", "market": "FX", "label": "환율", "price_digits": 2, "anchor_excd": "NAS", "anchor_symb": "AAPL"},
        {"type": "commodity", "name": "WTI", "market": "NYMEX", "label": "유가", "price_digits": 2},
    ],
    "us": [
        {"type": "overseas_index", "name": "S&P 500", "code": "SPX", "market": "S&P 500", "label": "전일 종가", "price_digits": 2},
        {"type": "overseas_index", "name": "NASDAQ", "code": "NDX", "market": "NASDAQ-100", "label": "전일 종가", "price_digits": 2},
        {"type": "kr_index", "name": "KOSPI", "code": "0001", "market": "KOSPI"},
        {"type": "fx", "name": "USD/KRW", "market": "FX", "label": "환율", "price_digits": 2, "anchor_excd": "NAS", "anchor_symb": "AAPL"},
        {"type": "commodity", "name": "WTI", "market": "NYMEX", "label": "유가", "price_digits": 2},
    ],
}


class DashboardService:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        load_dotenv(root_dir / ".env", override=False)
        self.config_dir = root_dir / "config"
        self.base_url = os.getenv("KIS_BASE_URL", "").strip() or "https://openapi.koreainvestment.com:9443"
        self.appkey = self._env("KIS_APP_KEY", "KIS_APPKEY")
        self.appsecret = self._env("KIS_APP_SECRET", "KIS_APPSECRET")
        self.cano = self._env("KIS_CANO", default="")
        self.acnt_prdt_cd = self._env("KIS_ACNT_PRDT_CD", default="")
        self.alpha_api_key = self._env("apiKey", "ALPHAVANTAGE_API_KEY", default="").strip()
        self._access_token: str | None = None
        self._access_token_expires_at: datetime | None = None

    def build_dashboard(self, market: str, interval_minutes: int) -> dict[str, object]:
        normalized_market = (market or "kr").strip().lower()
        token = self.get_token()
        watchlist = self.load_watchlist(normalized_market)
        meta = self.dashboard_meta(normalized_market)
        return {
            "market": normalized_market,
            "title": meta["title"],
            "subtitle": meta["subtitle"],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "interval_minutes": interval_minutes,
            "summary_cards": [self.build_summary_card(token, item) for item in SUMMARY_ITEMS_BY_MARKET[normalized_market]],
            "stock_cards": [self.build_stock_entry(token, item, normalized_market, interval_minutes) for item in watchlist],
        }

    def _env(self, *names: str, default: str | None = None) -> str:
        for name in names:
            value = os.getenv(name)
            if value is not None and str(value).strip():
                return str(value)
        if default is not None:
            return default
        raise RuntimeError(f"Missing required environment variable. Tried: {', '.join(names)}")

    def load_watchlist(self, market: str) -> list[dict[str, object]]:
        path = self.config_dir / f"watchlist.{market}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        defaults = DEFAULT_WATCHLISTS[market]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2), encoding="utf-8")
        return defaults

    def dashboard_meta(self, market: str) -> dict[str, str]:
        if market == "us":
            return {
                "title": "US Market Dashboard",
                "subtitle": "Live KIS snapshot · watchlist and macro flow",
            }
        return {
            "title": "KR Market Dashboard",
            "subtitle": "Live KIS snapshot · watchlist and market session flow",
        }

    def get_token(self) -> str:
        if self._access_token and self._access_token_expires_at and datetime.now(UTC) < self._access_token_expires_at:
            return self._access_token
        body = self.http_json(
            f"{self.base_url}/oauth2/tokenP",
            method="POST",
            headers={"content-type": "application/json"},
            payload={
                "grant_type": "client_credentials",
                "appkey": self.appkey,
                "appsecret": self.appsecret,
            },
        )
        self._access_token = body["access_token"]
        self._access_token_expires_at = datetime.now(UTC) + timedelta(seconds=max(0, int(body.get("expires_in", 0)) - 60))
        return self._access_token

    def http_json(self, url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            try:
                detail = json.loads(body)
            except Exception:
                detail = {"message": body}
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    def kis_get(self, token: str, path: str, params: dict[str, str], tr_id: str) -> dict:
        query = urllib.parse.urlencode(params)
        return self.http_json(
            f"{self.base_url}{path}?{query}",
            headers={
                "authorization": f"Bearer {token}",
                "appkey": self.appkey,
                "appsecret": self.appsecret,
                "tr_id": tr_id,
                "custtype": "P",
            },
        )

    @staticmethod
    def parse_int(value) -> int | None:
        text = str(value or "").strip().replace(",", "")
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def parse_number(value) -> float | None:
        text = str(value or "").strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def format_number(self, value) -> str:
        number = self.parse_int(value)
        return "-" if number is None else f"{number:,}"

    def format_decimal(self, value, digits: int = 2) -> str:
        number = self.parse_number(value)
        return "-" if number is None else f"{number:,.{digits}f}"

    def format_diff(self, value, sign_code=None) -> str:
        number = self.parse_int(value)
        if number is None:
            return "-"
        negative = sign_code in {"4", "5"}
        neutral = sign_code == "3" or number == 0
        body = f"{abs(number):,}"
        if neutral:
            return body
        return f"-{body}" if negative else f"+{body}"

    def format_pct(self, value, sign_code=None) -> str:
        text = str(value or "").strip().replace(",", "")
        if not text:
            return "-"
        try:
            number = abs(float(text))
        except ValueError:
            return "-"
        negative = sign_code in {"4", "5"} or text.startswith("-")
        neutral = sign_code == "3" or number == 0
        body = f"{number:.2f}%"
        if neutral:
            return body
        return f"-{body}" if negative else f"+{body}"

    def format_pct_or_diff_decimal(self, value, sign_code=None, digits: int = 2) -> str:
        number = self.parse_number(value)
        if number is None:
            return "-"
        negative = sign_code in {"4", "5"}
        neutral = sign_code == "3" or number == 0
        body = f"{abs(number):,.{digits}f}"
        if neutral:
            return body
        return f"-{body}" if negative else f"+{body}"

    def quote_card(self, token: str, code: str) -> dict[str, object]:
        data = self.kis_get(
            token,
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
            "FHKST01010100",
        )
        out = data.get("output", {})
        sign_code = out.get("prdy_vrss_sign")
        return {
            "price": self.format_number(out.get("stck_prpr")),
            "diff": self.format_diff(out.get("prdy_vrss"), sign_code),
            "pct": self.format_pct(out.get("prdy_ctrt"), sign_code),
            "raw_price": self.parse_int(out.get("stck_prpr")) or 0,
        }

    def us_quote_card(self, token: str, excd: str, symbol: str, digits: int = 2) -> dict[str, object]:
        data = self.kis_get(
            token,
            "/uapi/overseas-price/v1/quotations/price",
            {"AUTH": "", "EXCD": excd, "SYMB": symbol},
            "HHDFS00000300",
        )
        out = data.get("output", {})
        raw_price = self.parse_number(out.get("last"))
        sign_code = out.get("sign")
        return {
            "price": self.format_decimal(raw_price, digits),
            "diff": self.format_pct_or_diff_decimal(out.get("diff"), sign_code, digits),
            "pct": self.format_pct(out.get("rate"), sign_code),
            "raw_price": raw_price or 0.0,
        }

    def index_quote_card(self, token: str, code: str) -> dict[str, object]:
        data = self.kis_get(
            token,
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code},
            "FHPUP02100000",
        )
        out = data.get("output", {})
        sign_code = out.get("prdy_vrss_sign")
        return {
            "price": self.format_decimal(out.get("bstp_nmix_prpr")),
            "diff": self.format_pct_or_diff_decimal(out.get("bstp_nmix_prdy_vrss"), sign_code),
            "pct": self.format_pct(out.get("bstp_nmix_prdy_ctrt"), sign_code),
            "raw_price": self.parse_number(out.get("bstp_nmix_prpr")) or 0.0,
        }

    def overseas_index_quote_card(self, token: str, code: str, digits: int = 2) -> dict[str, object]:
        data = self.kis_get(
            token,
            "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice",
            {
                "FID_COND_MRKT_DIV_CODE": "N",
                "FID_INPUT_ISCD": code,
                "FID_HOUR_CLS_CODE": "0",
                "FID_PW_DATA_INCU_YN": "Y",
            },
            "FHKST03030200",
        )
        out = data.get("output1", {})
        raw_price = self.parse_number(out.get("ovrs_nmix_prpr"))
        return {
            "price": self.format_decimal(raw_price, digits),
            "diff": self.format_pct_or_diff_decimal(out.get("ovrs_nmix_prdy_vrss"), out.get("prdy_vrss_sign"), digits),
            "pct": self.format_pct(out.get("prdy_ctrt"), out.get("prdy_vrss_sign")),
            "raw_price": raw_price or 0.0,
        }

    def fx_quote_card_from_price_detail(self, token: str, excd: str, symb: str, digits: int = 2) -> dict[str, object]:
        data = self.kis_get(
            token,
            "/uapi/overseas-price/v1/quotations/price-detail",
            {"AUTH": "", "EXCD": excd, "SYMB": symb},
            "HHDFS76200200",
        )
        out = data.get("output", {})
        rate = self.parse_number(out.get("t_rate"))
        previous = self.parse_number(out.get("p_rate"))
        diff = None if previous is None or rate is None else rate - previous
        sign_code = "2" if diff and diff > 0 else "5" if diff and diff < 0 else "3"
        pct = None if previous in (None, 0) or rate is None else (diff / previous) * 100.0
        return {
            "price": self.format_decimal(rate, digits),
            "diff": "-" if diff is None else self.format_pct_or_diff_decimal(diff, sign_code, digits),
            "pct": "-" if pct is None else self.format_pct(pct, sign_code),
            "raw_price": rate or 0.0,
        }

    def paymt_stdr_fx_rate(self, token: str, base_date) -> float | None:
        if not self.cano or not self.acnt_prdt_cd:
            return None
        data = self.kis_get(
            token,
            "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance",
            {
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "BASS_DT": base_date.strftime("%Y%m%d"),
                "WCRC_FRCR_DVSN_CD": "01",
                "INQR_DVSN_CD": "00",
            },
            "CTRP6010R",
        )
        output1 = data.get("output1") or []
        output2 = data.get("output2") or []
        summary = output1[0] if isinstance(output1, list) and output1 else {}
        details = output2[0] if isinstance(output2, list) and output2 else {}
        return self.parse_number(summary.get("bass_exrt")) or self.parse_number(details.get("frst_bltn_exrt"))

    def fx_quote_card_from_account(self, token: str, digits: int = 2) -> dict[str, object] | None:
        if not self.cano or not self.acnt_prdt_cd:
            return None
        today = datetime.now().date()
        current = self.paymt_stdr_fx_rate(token, today)
        if current is None:
            return None
        previous = None
        for days_back in range(1, 8):
            candidate = self.paymt_stdr_fx_rate(token, today - timedelta(days=days_back))
            if candidate is not None:
                previous = candidate
                break
        diff = None if previous is None else current - previous
        sign_code = "2" if diff and diff > 0 else "5" if diff and diff < 0 else "3"
        pct = None if previous in (None, 0) else (diff / previous) * 100.0
        return {
            "price": self.format_decimal(current, digits),
            "diff": "-" if diff is None else self.format_pct_or_diff_decimal(diff, sign_code, digits),
            "pct": "-" if pct is None else self.format_pct(pct, sign_code),
            "raw_price": current,
        }

    def fetch_alpha_vantage_wti(self) -> dict[str, object]:
        if not self.alpha_api_key:
            raise RuntimeError("apiKey missing")
        query = urllib.parse.urlencode(
            {"function": "WTI", "interval": "daily", "apikey": self.alpha_api_key}
        )
        payload = self.http_json(f"https://www.alphavantage.co/query?{query}")
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) < 2:
            raise RuntimeError("Alpha Vantage WTI response invalid")
        points = []
        for row in rows:
            value = self.parse_number(row.get("value"))
            date = str(row.get("date") or "").strip()
            if value is not None and date:
                points.append({"date": date, "value": value})
        points.sort(key=lambda item: item["date"], reverse=True)
        latest = points[0]["value"]
        previous = points[1]["value"]
        diff = latest - previous
        sign_code = "2" if diff > 0 else "5" if diff < 0 else "3"
        pct = 0.0 if previous == 0 else (diff / previous) * 100.0
        return {
            "price": self.format_decimal(latest, 2),
            "diff": self.format_pct_or_diff_decimal(diff, sign_code, 2),
            "pct": self.format_pct(pct, sign_code),
            "raw_price": latest,
        }

    def unavailable_summary_card(self, item: dict[str, object], detail: str) -> dict[str, object]:
        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": "-",
            "diff": detail,
            "pct": "",
            "status": "unavailable",
        }

    def build_summary_card(self, token: str, item: dict[str, object]) -> dict[str, object]:
        if item["type"] == "kr_index":
            quote = self.index_quote_card(token, item["code"])
        elif item["type"] == "overseas_index":
            quote = self.overseas_index_quote_card(token, item["code"], digits=item.get("price_digits", 2))
            if quote["raw_price"] == 0:
                return self.unavailable_summary_card(item, "KIS 시세 없음")
        elif item["type"] == "fx":
            quote = self.fx_quote_card_from_account(token, digits=item.get("price_digits", 2))
            if quote is None:
                quote = self.fx_quote_card_from_price_detail(
                    token,
                    item.get("anchor_excd", "NAS"),
                    item.get("anchor_symb", "AAPL"),
                    digits=item.get("price_digits", 2),
                )
            if quote["raw_price"] == 0:
                return self.unavailable_summary_card(item, "KIS 환율 없음")
        elif item["type"] == "commodity":
            try:
                quote = self.fetch_alpha_vantage_wti()
            except RuntimeError as exc:
                return self.unavailable_summary_card(item, str(exc))
        else:
            return self.unavailable_summary_card(item, "미지원")

        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": quote["price"],
            "diff": quote["diff"],
            "pct": quote["pct"],
        }

    def normalize_chart_row(self, row: dict[str, object], session: str) -> dict[str, object] | None:
        price = self.parse_int(row.get("stck_prpr"))
        open_price = self.parse_int(row.get("stck_oprc"))
        high_price = self.parse_int(row.get("stck_hgpr"))
        low_price = self.parse_int(row.get("stck_lwpr"))
        time_raw = str(row.get("stck_cntg_hour") or "").strip()
        if None in (price, open_price, high_price, low_price) or not self.is_valid_time_raw(time_raw):
            return None
        return {
            "time": f"{time_raw[:2]}:{time_raw[2:4]}",
            "time_raw": time_raw,
            "price": price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": price,
            "volume": self.parse_int(row.get("cntg_vol")) or 0,
            "session": session,
        }

    def normalize_index_chart_row(self, row: dict[str, object], session: str) -> dict[str, object] | None:
        price = self.parse_number(row.get("bstp_nmix_prpr"))
        open_price = self.parse_number(row.get("bstp_nmix_oprc"))
        high_price = self.parse_number(row.get("bstp_nmix_hgpr"))
        low_price = self.parse_number(row.get("bstp_nmix_lwpr"))
        time_raw = str(row.get("stck_cntg_hour") or "").strip()
        if None in (price, open_price, high_price, low_price) or not self.is_valid_time_raw(time_raw):
            return None
        return {
            "time": f"{time_raw[:2]}:{time_raw[2:4]}",
            "time_raw": time_raw,
            "price": price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": price,
            "volume": self.parse_int(row.get("cntg_vol")) or 0,
            "session": session,
        }

    def normalize_us_chart_row(self, row: dict[str, object], session: str) -> dict[str, object] | None:
        close_price = self.parse_number(row.get("last"))
        open_price = self.parse_number(row.get("open"))
        high_price = self.parse_number(row.get("high"))
        low_price = self.parse_number(row.get("low"))
        time_raw = str(row.get("khms") or row.get("xhms") or "").strip()
        if None in (close_price, open_price, high_price, low_price) or not self.is_valid_time_raw(time_raw):
            return None
        return {
            "time": f"{time_raw[:2]}:{time_raw[2:4]}",
            "time_raw": time_raw,
            "price": close_price,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": self.parse_int(row.get("evol")) or 0,
            "session": session,
        }

    @staticmethod
    def is_valid_time_raw(value: str) -> bool:
        if len(value) != 6 or not value.isdigit():
            return False
        hour = int(value[:2])
        minute = int(value[2:4])
        second = int(value[4:6])
        return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59

    @staticmethod
    def previous_tick(hhmmss: str) -> str:
        dt = datetime.strptime(f"{hhmmss:0>6}"[:6], "%H%M%S")
        return (dt - timedelta(seconds=1)).strftime("%H%M%S")

    def fetch_session_series(self, token: str, code: str, market_code: str, session_name: str, date_str: str) -> tuple[list[dict[str, object]], list[str]]:
        cursor = "235959"
        collected: list[dict[str, object]] = []
        seen_times: set[str] = set()
        errors: list[str] = []
        for _ in range(12):
            try:
                data = self.kis_get(
                    token,
                    "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                    {
                        "FID_COND_MRKT_DIV_CODE": market_code,
                        "FID_INPUT_ISCD": code,
                        "FID_INPUT_HOUR_1": cursor,
                        "FID_INPUT_DATE_1": date_str,
                        "FID_PW_DATA_INCU_YN": "N",
                        "FID_FAKE_TICK_INCU_YN": "",
                    },
                    "FHKST03010230",
                )
            except RuntimeError as exc:
                errors.append(str(exc))
                break
            rows = data.get("output2") or []
            page = []
            for row in rows:
                normalized = self.normalize_chart_row(row, session_name)
                if not normalized or normalized["time_raw"] in seen_times:
                    continue
                seen_times.add(normalized["time_raw"])
                page.append(normalized)
            if not page:
                break
            collected.extend(page)
            earliest = min(item["time_raw"] for item in page)
            next_cursor = self.previous_tick(earliest)
            if next_cursor >= cursor or earliest <= "000000":
                break
            cursor = next_cursor
            if len(rows) < 120:
                break
        collected.sort(key=lambda item: item["time_raw"])
        return collected, errors

    def fetch_index_series(self, token: str, code: str) -> tuple[list[dict[str, object]], list[str]]:
        try:
            data = self.kis_get(
                token,
                "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice",
                {
                    "FID_COND_MRKT_DIV_CODE": "U",
                    "FID_ETC_CLS_CODE": "0",
                    "FID_INPUT_ISCD": code,
                    "FID_INPUT_HOUR_1": "300",
                    "FID_PW_DATA_INCU_YN": "N",
                },
                "FHKUP03500200",
            )
        except RuntimeError as exc:
            return [], [str(exc)]
        rows = data.get("output2") or []
        collected = []
        for row in rows:
            normalized = self.normalize_index_chart_row(row, "KRX")
            if normalized:
                collected.append(normalized)
        collected.sort(key=lambda item: item["time_raw"])
        return collected, []

    def fetch_intraday_chart(self, token: str, code: str, interval_minutes: int) -> dict[str, object]:
        date_str = datetime.now().strftime("%Y%m%d")
        segments = []
        warnings = []
        nxt_points, nxt_errors = self.fetch_session_series(token, code, "NX", "NXT", date_str)
        if nxt_errors:
            warnings.append(f"NXT: {nxt_errors[-1]}")
        if nxt_points:
            pre_nxt = [point for point in nxt_points if point["time_raw"] < "090000"]
            post_nxt = [point for point in nxt_points if point["time_raw"] > "153000"]
            if pre_nxt:
                segments.append({"session": "NXT Pre", "color": "#2563eb", "points": pre_nxt})
            if post_nxt:
                segments.append({"session": "NXT Post", "color": "#0f766e", "points": post_nxt})
        krx_points, krx_errors = self.fetch_session_series(token, code, "J", "KRX", date_str)
        if krx_points:
            segments.insert(1 if segments else 0, {"session": "KRX", "color": "#f97316", "points": krx_points})
        elif krx_errors:
            warnings.append(f"KRX: {krx_errors[-1]}")
        return self.aggregate_chart({"segments": segments, "warnings": warnings}, interval_minutes)

    def fetch_us_intraday_chart(self, token: str, excd: str, symbol: str, interval_minutes: int) -> dict[str, object]:
        try:
            data = self.kis_get(
                token,
                "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice",
                {
                    "AUTH": "",
                    "EXCD": excd,
                    "SYMB": symbol,
                    "NMIN": str(interval_minutes),
                    "PINC": "0",
                    "NEXT": "",
                    "NREC": "120",
                    "FILL": "",
                    "KEYB": "",
                },
                "HHDFS76950200",
            )
        except RuntimeError as exc:
            return {"segments": [], "warnings": [str(exc)], "interval_minutes": interval_minutes}
        rows = data.get("output2") or []
        points = []
        seen_times = set()
        for row in rows:
            normalized = self.normalize_us_chart_row(row, "US")
            if not normalized or normalized["time_raw"] in seen_times:
                continue
            seen_times.add(normalized["time_raw"])
            points.append(normalized)
        points.sort(key=lambda item: item["time_raw"])
        return {
            "segments": [{"session": "US", "color": "#2563eb", "points": points}] if points else [],
            "warnings": [],
            "interval_minutes": interval_minutes,
        }

    def aggregate_segment_points(self, points: list[dict[str, object]], minutes: int) -> list[dict[str, object]]:
        buckets = []
        current = None
        for point in points:
            hour = int(point["time_raw"][:2])
            minute = int(point["time_raw"][2:4])
            bucket_start = (minute // minutes) * minutes
            bucket_key = f"{hour:02d}{bucket_start:02d}00"
            if current is None or current["time_raw"] != bucket_key:
                if current is not None:
                    buckets.append(current)
                current = {
                    "time": f"{hour:02d}:{bucket_start:02d}",
                    "time_raw": bucket_key,
                    "price": point["close"],
                    "open": point["open"],
                    "high": point["high"],
                    "low": point["low"],
                    "close": point["close"],
                    "volume": point["volume"],
                    "session": point["session"],
                }
                continue
            current["high"] = max(current["high"], point["high"])
            current["low"] = min(current["low"], point["low"])
            current["close"] = point["close"]
            current["price"] = point["close"]
            current["volume"] += point["volume"]
        if current is not None:
            buckets.append(current)
        return buckets

    def aggregate_chart(self, chart: dict[str, object], minutes: int) -> dict[str, object]:
        aggregated_segments = []
        for segment in chart.get("segments", []):
            points = self.aggregate_segment_points(segment.get("points", []), minutes=minutes)
            if points:
                aggregated_segments.append({**segment, "points": points})
        return {"segments": aggregated_segments, "warnings": chart.get("warnings", []), "interval_minutes": minutes}

    def build_stock_card(self, token: str, name: str, code: str, market: str, interval_minutes: int) -> dict[str, object]:
        quote = self.quote_card(token, code)
        chart = self.fetch_intraday_chart(token, code, interval_minutes)
        return {"name": name, "market": market, "price": quote["price"], "diff": quote["diff"], "pct": quote["pct"], "chart": chart}

    def build_us_stock_card(self, token: str, name: str, code: str, market: str, excd: str, interval_minutes: int) -> dict[str, object]:
        quote = self.us_quote_card(token, excd, code, digits=2)
        chart = self.fetch_us_intraday_chart(token, excd, code, interval_minutes)
        return {"name": name, "market": market, "price": quote["price"], "diff": quote["diff"], "pct": quote["pct"], "chart": chart}

    def build_index_card(self, token: str, name: str, code: str, market: str, interval_minutes: int) -> dict[str, object]:
        quote = self.index_quote_card(token, code)
        points, errors = self.fetch_index_series(token, code)
        chart = {
            "segments": [{"session": "KRX", "color": "#f97316", "points": self.aggregate_segment_points(points, interval_minutes)}] if points else [],
            "warnings": errors,
            "interval_minutes": interval_minutes,
        }
        return {"name": name, "market": market, "price": quote["price"], "diff": quote["diff"], "pct": quote["pct"], "chart": chart}

    def build_stock_entry(self, token: str, item: dict[str, object], market: str, interval_minutes: int) -> dict[str, object]:
        if market == "us":
            excd = item.get("excd", "NAS")
            return self.build_us_stock_card(token, item["name"], item["code"], item.get("market", excd), excd, interval_minutes)
        return self.build_stock_card(token, item["name"], item["code"], item["market"], interval_minutes)
