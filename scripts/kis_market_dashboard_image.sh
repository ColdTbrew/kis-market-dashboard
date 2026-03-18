#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${KIS_DASHBOARD_OUT_DIR:-$ROOT/tmp}"
JSON="$OUT_DIR/kis_market_dashboard.json"
HTML="$OUT_DIR/kis_market_dashboard.html"
PNG="$OUT_DIR/kis_market_dashboard.png"
mkdir -p "$OUT_DIR"

KIS_DASHBOARD_JSON="$JSON" python3 "$ROOT/scripts/kis_market_dashboard_data.py"

python3 - "$JSON" <<'PY' > "$HTML"
import json, html as h, sys
from pathlib import Path
cards = json.loads(Path(sys.argv[1]).read_text())["cards"]
print("""<!doctype html><html><head><meta charset='utf-8'><style>
body{margin:0;background:#0b0f14;color:#eef2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif}
.wrap{width:1200px;height:1600px;padding:28px;box-sizing:border-box;background:linear-gradient(180deg,#0b0f14,#121923)}
.h1{font-size:40px;font-weight:800;margin-bottom:8px}.sub{color:#9fb0c3;margin-bottom:22px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.card{background:#161e29;border:1px solid #263244;border-radius:22px;padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.name{font-size:28px;font-weight:700;margin-bottom:10px}.price{font-size:42px;font-weight:800;margin-bottom:8px}.meta{font-size:22px;color:#c8d4e3;margin-bottom:14px}.chart{width:100%;height:250px;object-fit:cover;background:#fff;border-radius:14px}
.footer{margin-top:18px;color:#7f90a6;font-size:18px}
</style></head><body><div class='wrap'>""")
print("<div class='h1'>KR Market Dashboard</div><div class='sub'>KIS + KOSPI 기준 · 전일 종가 대비</div><div class='grid'>")
for c in cards:
    pct = str(c['pct'])
    if pct and not pct.endswith('%'):
        pct += '%'
    print(f"<div class='card'><div class='name'>{h.escape(c['name'])}</div><div class='price'>{h.escape(str(c['price']))}</div><div class='meta'>Δ {h.escape(str(c['diff']))} · {h.escape(pct)}</div><img class='chart' src='{h.escape(c['chart'])}'><div class='footer'>{h.escape(c['name'])}</div></div>")
print("</div></div></body></html>")
PY

agent-browser open "file://$HTML" >/dev/null || agent-browser open "file://$HTML" >/dev/null
agent-browser wait 1500 >/dev/null || true
agent-browser screenshot "$PNG" >/dev/null
agent-browser close >/dev/null 2>&1 || true

if [ -n "${OPENCLAW_TARGET:-}" ]; then
  openclaw message send --channel "${OPENCLAW_CHANNEL:-telegram}" --account "${OPENCLAW_ACCOUNT:-default}" --target "$OPENCLAW_TARGET" --message "KR 마켓 대시보드" --media "$PNG"
else
  echo "$PNG"
fi
