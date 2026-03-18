#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${KIS_DASHBOARD_OUT_DIR:-$ROOT/tmp}"
JSON_OUT="$OUT_DIR/kis_market_dashboard.json"
RENDER_DATA_DIR="$ROOT/renderer/data"
RENDER_JSON="$RENDER_DATA_DIR/latest.json"
HTML="$ROOT/renderer/index.html"
PNG="$OUT_DIR/kis_market_dashboard.png"
mkdir -p "$OUT_DIR" "$RENDER_DATA_DIR"

KIS_DASHBOARD_JSON="$JSON_OUT" python3 "$ROOT/scripts/kis_market_dashboard_data.py"
cp "$JSON_OUT" "$RENDER_JSON"

agent-browser open "file://$HTML" >/dev/null || agent-browser open "file://$HTML" >/dev/null
agent-browser wait 1500 >/dev/null || true
agent-browser screenshot "$PNG" >/dev/null
agent-browser close >/dev/null 2>&1 || true

if [ -n "${OPENCLAW_TARGET:-}" ]; then
  openclaw message send --channel "${OPENCLAW_CHANNEL:-telegram}" --account "${OPENCLAW_ACCOUNT:-default}" --target "$OPENCLAW_TARGET" --message "KR 마켓 대시보드" --media "$PNG"
else
  echo "$PNG"
fi
