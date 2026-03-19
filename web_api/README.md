# KIS Command Center Web API

This is a separate web dashboard app that sits alongside the existing CLI without modifying it.

The web backend now queries KIS directly at request time. It does not shell out to
`kis_market_dashboard.py`, and it does not generate dashboard artifact JSON files
for the web flow.

## Run

```bash
cd web_api
uv run uvicorn app.main:create_app --factory --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Environment

- `KIS_WEB_DASHBOARD_PASSWORD`: required password for login
- `KIS_WEB_DASHBOARD_SESSION_SECRET`: session signing secret
- `KIS_WEB_DASHBOARD_INSECURE_HTTP=1`: optional for local `http://127.0.0.1` cookie testing
- Runtime market data envs are loaded dynamically from the repo root `.env`
  - `KIS_APP_KEY` or `KIS_APPKEY`
  - `KIS_APP_SECRET` or `KIS_APPSECRET`
  - `KIS_BASE_URL`
  - `KIS_CANO`
  - `KIS_ACNT_PRDT_CD`
  - `apiKey` or `ALPHAVANTAGE_API_KEY`

The backend loads those values at runtime with `python-dotenv`, so the web server can
query KIS directly without us manually reading `.env`.

## API Surface

- `POST /api/login`
- `POST /api/logout`
- `GET /api/session`
- `GET /api/dashboard?market=kr|us&interval_minutes=10`
- `GET /api/watchlist?market=kr|us`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{code}?market=kr|us`

`/api/dashboard` returns a live payload for the web UI:
- summary cards
- stock cards
- intraday candle/volume series

Watchlists still live in local `config/watchlist.kr.json` and `config/watchlist.us.json`.
If those files do not exist, the backend creates default watchlists.

## Tests

```bash
cd web_api
uv run pytest tests/test_api.py -q
```
