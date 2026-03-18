#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

SECRETS_PATH = Path(os.path.expanduser("~/.openclaw/secrets.json"))
APPKEY = os.getenv("KIS_APPKEY", "")
APPSECRET = os.getenv("KIS_APPSECRET", "")
BASE_URL = os.getenv("KIS_BASE_URL", "") or "https://openapi.koreainvestment.com:9443"
CANO = os.getenv("KIS_CANO", "")
ACNT_PRDT_CD = os.getenv("KIS_ACNT_PRDT_CD", "")
OUT = Path(os.getenv("KIS_DASHBOARD_JSON", "./tmp/kis_market_dashboard.json"))
TOKEN_CACHE = OUT.parent / ".kis_access_token.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

WATCHLIST = [
    {"type": "stock", "name": "Samsung Elec.", "code": "005930", "market": "005930"},
    {"type": "stock", "name": "SK Hynix", "code": "000660", "market": "000660"},
    {"type": "stock", "name": "SK Telecom", "code": "017670", "market": "017670"},
    {"type": "stock", "name": "Hyundai Motor", "code": "005380", "market": "005380"},
]

SUMMARY_ITEMS = [
    {"type": "kr_index", "name": "KOSPI", "code": "0001", "market": "KOSPI"},
    {"type": "kr_index", "name": "KOSDAQ", "code": "1001", "market": "KOSDAQ"},
    {"type": "overseas_index", "name": "NASDAQ", "code": "NDX", "market": "NASDAQ-100", "label": "전일 종가", "price_digits": 2},
    {"type": "fx", "name": "USD/KRW", "market": "FX", "label": "환율", "price_digits": 2, "anchor_excd": "NAS", "anchor_symb": "AAPL"},
    {"type": "commodity", "name": "WTI", "code": "CL", "market": "NYMEX", "label": "유가", "price_digits": 2},
]

if SECRETS_PATH.exists() and (not APPKEY or not APPSECRET):
    try:
        secret_obj = json.loads(SECRETS_PATH.read_text())
        kis = secret_obj.get("providers", {}).get("kis", {})
        APPKEY = APPKEY or kis.get("appkey", "")
        APPSECRET = APPSECRET or kis.get("appsecret", "")
        BASE_URL = os.getenv("KIS_BASE_URL", "") or kis.get("baseUrl", "") or BASE_URL
        CANO = CANO or str(kis.get("cano", ""))
        ACNT_PRDT_CD = ACNT_PRDT_CD or str(kis.get("acnt_prdt_cd", ""))
    except Exception:
        pass

if not APPKEY or not APPSECRET:
    print("KIS credentials missing: set KIS_APPKEY and KIS_APPSECRET", file=sys.stderr)
    sys.exit(1)


def http_json(url, method="GET", headers=None, payload=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()

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


def read_cached_token():
    if not TOKEN_CACHE.exists():
        return None
    try:
        cache = json.loads(TOKEN_CACHE.read_text())
    except Exception:
        return None

    token = cache.get("access_token")
    expires_at = cache.get("expires_at")
    if not token or not expires_at:
        return None

    expires_dt = datetime.fromisoformat(expires_at)
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=UTC)

    if datetime.now(UTC) >= expires_dt:
        return None
    return token


def write_cached_token(token, expires_in):
    expires_at = datetime.now(UTC) + timedelta(seconds=max(0, int(expires_in) - 60))
    TOKEN_CACHE.write_text(json.dumps({
        "access_token": token,
        "expires_at": expires_at.isoformat(),
    }))


def get_token():
    cached = read_cached_token()
    if cached:
        return cached

    body = http_json(
        f"{BASE_URL}/oauth2/tokenP",
        method="POST",
        headers={"content-type": "application/json"},
        payload={
            "grant_type": "client_credentials",
            "appkey": APPKEY,
            "appsecret": APPSECRET,
        },
    )
    token = body["access_token"]
    write_cached_token(token, body.get("expires_in", 0))
    return token


def kis_get(token, path, params, tr_id):
    query = urllib.parse.urlencode(params)
    return http_json(
        f"{BASE_URL}{path}?{query}",
        headers={
            "authorization": f"Bearer {token}",
            "appkey": APPKEY,
            "appsecret": APPSECRET,
            "tr_id": tr_id,
            "custtype": "P",
        },
    )


def parse_int(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_number(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value):
    number = parse_int(value)
    return "-" if number is None else f"{number:,}"


def format_decimal(value, digits=2):
    number = parse_number(value)
    return "-" if number is None else f"{number:,.{digits}f}"


def format_diff(value, sign_code=None):
    number = parse_int(value)
    if number is None:
        return "-"
    negative = sign_code in {"4", "5"}
    neutral = sign_code == "3" or number == 0
    body = f"{abs(number):,}"
    if neutral:
        return body
    return f"-{body}" if negative else f"+{body}"


def format_pct(value, sign_code=None):
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


def previous_tick(hhmmss):
    value = f"{hhmmss:0>6}"[:6]
    dt = datetime.strptime(value, "%H%M%S")
    return (dt - timedelta(seconds=1)).strftime("%H%M%S")


def quote_card(token, code):
    data = kis_get(
        token,
        "/uapi/domestic-stock/v1/quotations/inquire-price",
        {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
        },
        "FHKST01010100",
    )
    out = data.get("output", {})
    sign_code = out.get("prdy_vrss_sign")
    return {
        "price": format_number(out.get("stck_prpr")),
        "diff": format_diff(out.get("prdy_vrss"), sign_code),
        "pct": format_pct(out.get("prdy_ctrt"), sign_code),
        "raw_price": parse_int(out.get("stck_prpr")) or 0,
    }


def index_quote_card(token, code):
    data = kis_get(
        token,
        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
        {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": code,
        },
        "FHPUP02100000",
    )
    out = data.get("output", {})
    sign_code = out.get("prdy_vrss_sign")
    return {
        "price": format_decimal(out.get("bstp_nmix_prpr")),
        "diff": format_pct_or_diff_decimal(out.get("bstp_nmix_prdy_vrss"), sign_code),
        "pct": format_pct(out.get("bstp_nmix_prdy_ctrt"), sign_code),
        "raw_price": parse_number(out.get("bstp_nmix_prpr")) or 0.0,
    }


def format_pct_or_diff_decimal(value, sign_code=None, digits=2):
    number = parse_number(value)
    if number is None:
        return "-"
    negative = sign_code in {"4", "5"}
    neutral = sign_code == "3" or number == 0
    body = f"{abs(number):,.{digits}f}"
    if neutral:
        return body
    return f"-{body}" if negative else f"+{body}"


def normalize_chart_row(row, session):
    price = parse_int(row.get("stck_prpr"))
    open_price = parse_int(row.get("stck_oprc"))
    high_price = parse_int(row.get("stck_hgpr"))
    low_price = parse_int(row.get("stck_lwpr"))
    time_raw = str(row.get("stck_cntg_hour") or "").strip()
    if None in (price, open_price, high_price, low_price) or not is_valid_time_raw(time_raw):
        return None
    return {
        "time": f"{time_raw[:2]}:{time_raw[2:4]}",
        "time_raw": time_raw,
        "price": price,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": price,
        "volume": parse_int(row.get("cntg_vol")) or 0,
        "session": session,
    }


def normalize_index_chart_row(row, session):
    price = parse_number(row.get("bstp_nmix_prpr"))
    open_price = parse_number(row.get("bstp_nmix_oprc"))
    high_price = parse_number(row.get("bstp_nmix_hgpr"))
    low_price = parse_number(row.get("bstp_nmix_lwpr"))
    time_raw = str(row.get("stck_cntg_hour") or "").strip()
    if None in (price, open_price, high_price, low_price) or not is_valid_time_raw(time_raw):
        return None
    return {
        "time": f"{time_raw[:2]}:{time_raw[2:4]}",
        "time_raw": time_raw,
        "price": price,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": price,
        "volume": parse_int(row.get("cntg_vol")) or 0,
        "session": session,
    }


def is_valid_time_raw(value):
    if len(value) != 6 or not value.isdigit():
        return False
    hour = int(value[:2])
    minute = int(value[2:4])
    second = int(value[4:6])
    return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59


def fetch_session_series(token, code, market_code, session_name, date_str):
    cursor = "235959"
    collected = []
    seen_times = set()
    errors = []

    for _ in range(12):
        try:
            data = kis_get(
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
            normalized = normalize_chart_row(row, session_name)
            if not normalized:
                continue
            if normalized["time_raw"] in seen_times:
                continue
            seen_times.add(normalized["time_raw"])
            page.append(normalized)

        if not page:
            break

        collected.extend(page)
        earliest = min(item["time_raw"] for item in page)
        next_cursor = previous_tick(earliest)
        if next_cursor >= cursor or earliest <= "000000":
            break
        cursor = next_cursor

        if len(rows) < 120:
            break

    collected.sort(key=lambda item: item["time_raw"])
    return collected, errors


def fetch_index_series(token, code, interval_seconds="300"):
    try:
        data = kis_get(
            token,
            "/uapi/domestic-stock/v1/quotations/inquire-time-indexchartprice",
            {
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_ETC_CLS_CODE": "0",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_HOUR_1": interval_seconds,
                "FID_PW_DATA_INCU_YN": "N",
            },
            "FHKUP03500200",
        )
    except RuntimeError as exc:
        return [], [str(exc)]

    rows = data.get("output2") or []
    collected = []
    for row in rows:
        normalized = normalize_index_chart_row(row, "KRX")
        if normalized:
            collected.append(normalized)
    collected.sort(key=lambda item: item["time_raw"])
    return collected, []


def fetch_intraday_chart(token, code):
    date_str = datetime.now().strftime("%Y%m%d")
    segments = []
    warnings = []

    nxt_points, nxt_errors = fetch_session_series(token, code, "NX", "NXT", date_str)
    if nxt_errors:
        warnings.append(f"NXT: {nxt_errors[-1]}")

    if nxt_points:
        pre_nxt = [point for point in nxt_points if point["time_raw"] < "090000"]
        post_nxt = [point for point in nxt_points if point["time_raw"] > "153000"]

        if pre_nxt:
            segments.append({
                "session": "NXT Pre",
                "color": "#0ea5e9",
                "points": pre_nxt,
            })

    krx_points, krx_errors = fetch_session_series(token, code, "J", "KRX", date_str)
    if krx_points:
        segments.append({
            "session": "KRX",
            "color": "#f97316",
            "points": krx_points,
        })
    elif krx_errors:
        warnings.append(f"KRX: {krx_errors[-1]}")

    if nxt_points:
        post_nxt = [point for point in nxt_points if point["time_raw"] > "153000"]
        if post_nxt:
            segments.append({
                "session": "NXT Post",
                "color": "#14b8a6",
                "points": post_nxt,
            })

    if not segments:
        fallback, errors = fetch_session_series(token, code, "UN", "Unified", date_str)
        if fallback:
            segments.append({
                "session": "Unified",
                "color": "#64748b",
                "points": fallback,
            })
        elif errors:
            warnings.append(f"Unified: {errors[-1]}")

    return {
        "segments": segments,
        "warnings": warnings,
    }


def aggregate_segment_points(points, minutes=5):
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


def aggregate_chart(chart, minutes=5):
    aggregated_segments = []
    for segment in chart.get("segments", []):
        points = aggregate_segment_points(segment.get("points", []), minutes=minutes)
        if points:
            aggregated_segments.append({
                **segment,
                "points": points,
            })
    return {
        "segments": aggregated_segments,
        "warnings": chart.get("warnings", []),
        "interval_minutes": minutes,
    }


def build_stock_card(token, name, code, market):
    quote = quote_card(token, code)
    chart = aggregate_chart(fetch_intraday_chart(token, code), minutes=5)
    return {
        "name": name,
        "market": market,
        "price": quote["price"],
        "diff": quote["diff"],
        "pct": quote["pct"],
        "chart": chart,
    }


def build_index_card(token, name, code, market):
    quote = index_quote_card(token, code)
    points, errors = fetch_index_series(token, code, interval_seconds="300")
    chart = {
        "segments": [{
            "session": "KRX",
            "color": "#f97316",
            "points": points,
        }] if points else [],
        "warnings": errors,
        "interval_minutes": 5,
    }
    return {
        "name": name,
        "market": market,
        "price": quote["price"],
        "diff": quote["diff"],
        "pct": quote["pct"],
        "chart": chart,
    }


def overseas_index_quote_card(token, code, digits=2):
    data = kis_get(
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
    raw_price = parse_number(out.get("ovrs_nmix_prpr"))
    return {
        "price": format_decimal(raw_price, digits=digits),
        "diff": format_pct_or_diff_decimal(out.get("ovrs_nmix_prdy_vrss"), out.get("prdy_vrss_sign"), digits=digits),
        "pct": format_pct(out.get("prdy_ctrt"), out.get("prdy_vrss_sign")),
        "raw_price": raw_price or 0.0,
        "name": out.get("hts_kor_isnm", ""),
    }


def commodity_quote_card(token, code, digits=2):
    data = kis_get(
        token,
        "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice",
        {
            "FID_COND_MRKT_DIV_CODE": "N",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": (datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": datetime.now().strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
        },
        "FHKST03030100",
    )
    out = data.get("output1", {})
    raw_price = parse_number(out.get("ovrs_nmix_prpr"))
    sign_code = out.get("prdy_vrss_sign")
    return {
        "price": format_decimal(raw_price, digits=digits),
        "diff": format_pct_or_diff_decimal(out.get("ovrs_nmix_prdy_vrss"), sign_code, digits=digits),
        "pct": format_pct(out.get("prdy_ctrt"), sign_code),
        "raw_price": raw_price or 0.0,
    }


def fx_quote_card_from_price_detail(token, excd, symb, digits=2):
    data = kis_get(
        token,
        "/uapi/overseas-price/v1/quotations/price-detail",
        {
            "AUTH": "",
            "EXCD": excd,
            "SYMB": symb,
        },
        "HHDFS76200200",
    )
    out = data.get("output", {})
    rate = parse_number(out.get("t_rate"))
    previous = parse_number(out.get("p_rate"))
    diff = None if previous is None or rate is None else rate - previous
    sign_code = "2" if diff and diff > 0 else "5" if diff and diff < 0 else "3"
    pct = None if previous in (None, 0) or rate is None else (diff / previous) * 100.0
    return {
        "price": format_decimal(rate, digits=digits),
        "diff": "-" if diff is None else format_pct_or_diff_decimal(diff, sign_code, digits=digits),
        "pct": "-" if pct is None else format_pct(pct, sign_code),
        "raw_price": rate or 0.0,
    }


def paymt_stdr_fx_rate(token, base_date):
    data = kis_get(
        token,
        "/uapi/overseas-stock/v1/trading/inquire-paymt-stdr-balance",
        {
            "CANO": CANO,
            "ACNT_PRDT_CD": ACNT_PRDT_CD,
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
    return parse_number(summary.get("bass_exrt")) or parse_number(details.get("frst_bltn_exrt"))


def fx_quote_card_from_account(token, digits=2):
    if not CANO or not ACNT_PRDT_CD:
        return None

    today = datetime.now().date()
    current = paymt_stdr_fx_rate(token, today)
    if current is None:
        return None

    previous = None
    for days_back in range(1, 8):
        candidate = paymt_stdr_fx_rate(token, today - timedelta(days=days_back))
        if candidate is not None:
            previous = candidate
            break

    diff = None if previous is None else current - previous
    sign_code = "2" if diff and diff > 0 else "5" if diff and diff < 0 else "3"
    pct = None if previous in (None, 0) else (diff / previous) * 100.0
    return {
        "price": format_decimal(current, digits=digits),
        "diff": "-" if diff is None else format_pct_or_diff_decimal(diff, sign_code, digits=digits),
        "pct": "-" if pct is None else format_pct(pct, sign_code),
        "raw_price": current,
    }


def unavailable_summary_card(item, detail):
    return {
        "name": item["name"],
        "market": item["market"],
        "label": item.get("label", ""),
        "price": "-",
        "diff": detail,
        "pct": "",
        "status": "unavailable",
    }


def build_summary_card(token, item):
    if item["type"] == "kr_index":
        quote = index_quote_card(token, item["code"])
        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": quote["price"],
            "diff": quote["diff"],
            "pct": quote["pct"],
        }

    if item["type"] == "overseas_index":
        quote = overseas_index_quote_card(token, item["code"], digits=item.get("price_digits", 2))
        if quote["raw_price"] == 0:
            return unavailable_summary_card(item, "KIS 시세 없음")
        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": quote["price"],
            "diff": quote["diff"],
            "pct": quote["pct"],
        }

    if item["type"] == "fx":
        quote = fx_quote_card_from_account(token, digits=item.get("price_digits", 2))
        if quote is None:
            quote = fx_quote_card_from_price_detail(
                token,
                item.get("anchor_excd", "NAS"),
                item.get("anchor_symb", "AAPL"),
                digits=item.get("price_digits", 2),
            )
        if quote["raw_price"] == 0:
            return unavailable_summary_card(item, "KIS 환율 없음")
        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": quote["price"],
            "diff": quote["diff"],
            "pct": quote["pct"],
        }

    if item["type"] == "commodity":
        quote = commodity_quote_card(token, item["code"], digits=item.get("price_digits", 2))
        if quote["raw_price"] == 0:
            return unavailable_summary_card(item, "KIS 시세 없음")
        return {
            "name": item["name"],
            "market": item["market"],
            "label": item.get("label", ""),
            "price": quote["price"],
            "diff": quote["diff"],
            "pct": quote["pct"],
        }

    return {
        "name": item["name"],
        "market": item["market"],
        "label": item.get("label", ""),
        "price": "-",
        "diff": "미지원",
        "pct": "",
    }


def build_stock_entry(token, item):
    return build_stock_card(token, item["name"], item["code"], item["market"])


def main():
    token = get_token()
    result = {
        "title": "KR Market Dashboard",
        "subtitle": "KIS intraday · macro snapshot + stock session flow",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary_cards": [build_summary_card(token, item) for item in SUMMARY_ITEMS],
        "stock_cards": [build_stock_entry(token, item) for item in WATCHLIST],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(str(OUT))


if __name__ == "__main__":
    main()
