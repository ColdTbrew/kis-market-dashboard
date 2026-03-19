# Web API

This package provides the new FastAPI backend for the dashboard.

## Run locally

```bash
export KIS_DASHBOARD_ADMIN_PASSWORD="..."
export KIS_DASHBOARD_SESSION_SECRET="..."
uv run uvicorn web_api.main:app --reload
```

The API stores generated artifacts under `tmp/artifacts/<id>/` by default and uses
`config/watchlist.kr.json` / `config/watchlist.us.json` for watchlist state.
