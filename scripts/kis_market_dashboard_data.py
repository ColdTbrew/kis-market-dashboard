#!/usr/bin/env python3
import json, os, re, subprocess, sys, urllib.request, urllib.parse
from pathlib import Path

APPKEY = os.getenv("KIS_APPKEY", "")
APPSECRET = os.getenv("KIS_APPSECRET", "")
BASE_URL = os.getenv("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
OUT = Path(os.getenv("KIS_DASHBOARD_JSON", "./tmp/kis_market_dashboard.json"))
OUT.parent.mkdir(parents=True, exist_ok=True)

if not APPKEY or not APPSECRET:
    print("KIS credentials missing", file=sys.stderr)
    sys.exit(1)

def http_json(url, method="GET", headers=None, payload=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())

def get_token():
    return http_json(
        f"{BASE_URL}/oauth2/tokenP",
        method="POST",
        headers={"content-type": "application/json"},
        payload={
            "grant_type": "client_credentials",
            "appkey": APPKEY,
            "appsecret": APPSECRET,
        },
    )["access_token"]

def stock_quote(token, code):
    params = urllib.parse.urlencode({
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
    })
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price?{params}"
    data = http_json(url, headers={
        "authorization": f"Bearer {token}",
        "appkey": APPKEY,
        "appsecret": APPSECRET,
        "tr_id": "FHKST01010100",
        "custtype": "P",
    })
    out = data.get("output", {})
    return {
        "price": out.get("stck_prpr", "-"),
        "diff": out.get("prdy_vrss", "-"),
        "pct": out.get("prdy_ctrt", "-"),
    }

def fetch_text(url):
    raw = subprocess.check_output(["curl", "-s", "-H", "User-Agent: Mozilla/5.0", url])
    for enc in ("euc-kr", "utf-8"):
        try:
            return raw.decode(enc, "ignore")
        except Exception:
            pass
    return raw.decode("utf-8", "ignore")

def kospi_quote():
    html = fetch_text("https://finance.naver.com/sise/sise_index.nhn?code=KOSPI")
    now = re.search(r'<em id="now_value">([^<]+)</em>', html)
    chg = re.search(r'<span class="fluc" id="change_value_and_rate"><span>([^<]+)</span>\s*([+\-]?[0-9.]+%)', html)
    return {
        "price": now.group(1).strip() if now else "-",
        "diff": chg.group(1).strip() if chg else "-",
        "pct": chg.group(2).strip() if chg else "-",
    }

token = get_token()
result = {
    "cards": [
        {"name": "KOSPI", "chart": "https://ssl.pstatic.net/imgstock/chart3/day90/KOSPI.png", **kospi_quote()},
        {"name": "Samsung Elec.", "chart": "https://ssl.pstatic.net/imgfinance/chart/item/area/day/005930.png", **stock_quote(token, "005930")},
        {"name": "SK Hynix", "chart": "https://ssl.pstatic.net/imgfinance/chart/item/area/day/000660.png", **stock_quote(token, "000660")},
        {"name": "SK Telecom", "chart": "https://ssl.pstatic.net/imgfinance/chart/item/area/day/017670.png", **stock_quote(token, "017670")},
    ]
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(str(OUT))
