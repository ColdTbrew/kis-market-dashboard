#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${KIS_DASHBOARD_PYTHON:-$ROOT/.venv/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python runtime not found: $PYTHON_BIN" >&2
  echo "Create it with: uv sync" >&2
  exit 1
fi

"$PYTHON_BIN" "$ROOT/kis_market_dashboard.py" watchlist "$@"
