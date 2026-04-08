---
name: kis-market-dashboard
description: Generate and send the KIS market dashboard from this repo using the built-in CLI and an optional workspace wrapper. Use when the user asks for KR/US market dashboard generation, image delivery to Discord/Telegram via OpenClaw, watchlist updates, cron registration, or debugging this dashboard pipeline.
---

# KIS Market Dashboard

Use this repo's CLI as the source of truth for data fetch, rendering, watchlist management, and delivery.

## Preferred workflow

1. If the environment already has a wrapper script for this repo, use that first.
2. Otherwise run this repo CLI directly from the repo root.
3. Keep generated artifacts in a workspace-local `tmp/` directory.

## Direct repo commands

From the repo root:

```bash
uv run python kis_market_dashboard.py generate --market kr
uv run python kis_market_dashboard.py generate --market us
uv run python kis_market_dashboard.py watchlist list --market kr
```

## Optional wrapper pattern

Many OpenClaw workspaces use a small wrapper script so cron jobs and agent prompts have a stable entrypoint.

Typical wrapper behavior:

- set `KIS_DASHBOARD_MARKET`
- set `OPENCLAW_TARGET`, `OPENCLAW_CHANNEL`, `OPENCLAW_ACCOUNT` when needed
- call:

```bash
uv run python kis_market_dashboard.py generate --market "$MARKET" --out-dir "$OUT_DIR" --send
```

## Useful overrides

- Market:
  `KIS_DASHBOARD_MARKET=kr` or `KIS_DASHBOARD_MARKET=us`
- Output dir:
  `KIS_DASHBOARD_OUT_DIR=/ABS/PATH/TO/workspace/tmp`
- Delivery target:
  `OPENCLAW_TARGET=<TARGET_ID_OR_CHANNEL>`
- Delivery channel:
  `OPENCLAW_CHANNEL=discord` or `OPENCLAW_CHANNEL=telegram`

## Cron scheduling guide

When registering recurring OpenClaw jobs for this dashboard, keep schedules in `Asia/Seoul`.

- KR dashboard:
  weekdays from `08:00` to `20:00`, every `30` minutes
- US dashboard:
  weekdays from `17:00` to `00:00`, every `60` minutes

Recommended exec commands:

```bash
KIS_DASHBOARD_MARKET=kr bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh
KIS_DASHBOARD_MARKET=us bash /ABS/PATH/TO/workspace/scripts/kis_market_dashboard_send.sh
```

If no wrapper exists, run the repo CLI directly instead.

## Notes

- Prefer this repo CLI over legacy ad-hoc dashboard scripts.
- KIS credentials come from environment variables or `~/.openclaw/secrets.json` in environments that use OpenClaw.
- If a wrapper already performs delivery, avoid duplicate cron announce messages unless the user explicitly wants them.
