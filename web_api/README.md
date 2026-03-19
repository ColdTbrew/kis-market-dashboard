# KIS Command Center Web API

This is a separate web dashboard app that sits alongside the existing CLI without modifying it.

## Run

```bash
cd web_api
uv run uvicorn app.main:create_app --factory --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Environment

- `KIS_WEB_DASHBOARD_PASSWORD`: required password for login
- `KIS_WEB_DASHBOARD_SESSION_SECRET`: session signing secret

The API shells out to the existing root CLI:

```bash
uv run python kis_market_dashboard.py generate ...
```

That keeps the current CLI/data/render path untouched.

## Tests

```bash
cd web_api
uv run pytest tests/test_api.py -q
```
