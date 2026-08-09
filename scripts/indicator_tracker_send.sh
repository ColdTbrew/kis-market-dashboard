#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="${INDICATOR_TRACKER_OUT_DIR:-$ROOT/tmp}"

mkdir -p "$OUT_DIR"
cd "$ROOT"

exec uv run python indicator_tracker.py generate \
  --out-dir "$OUT_DIR" \
  --send \
  "$@"
