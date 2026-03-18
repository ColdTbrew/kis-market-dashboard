#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${KIS_DASHBOARD_OUT_DIR:-$ROOT/tmp}"
JSON_OUT="$OUT_DIR/kis_market_dashboard.json"
PNG="$OUT_DIR/kis_market_dashboard.png"
PYTHON_BIN="${KIS_DASHBOARD_PYTHON:-$ROOT/.venv/bin/python}"
mkdir -p "$OUT_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python runtime not found: $PYTHON_BIN" >&2
  echo "Create it with: uv sync" >&2
  exit 1
fi

KIS_DASHBOARD_JSON="$JSON_OUT" "$PYTHON_BIN" "$ROOT/scripts/kis_market_dashboard_data.py"
KIS_DASHBOARD_JSON="$JSON_OUT" KIS_DASHBOARD_PNG="$PNG" "$PYTHON_BIN" "$ROOT/scripts/kis_market_dashboard_render.py"

if [ -n "${OPENCLAW_TARGET:-}" ]; then
  openclaw message send --channel "${OPENCLAW_CHANNEL:-telegram}" --account "${OPENCLAW_ACCOUNT:-default}" --target "$OPENCLAW_TARGET" --message "KR 마켓 대시보드" --media "$PNG"
else
  echo "$PNG"
fi
