from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from app.dashboard_service import DashboardService

Market = Literal["kr", "us"]


class LoginRequest(BaseModel):
    password: str


class WatchlistItemInput(BaseModel):
    market: Market
    code: str
    name: str
    market_label: str | None = None
    excd: str | None = None


def create_app(
    root_dir: Path | None = None,
    dashboard_service: DashboardService | object | None = None,
) -> FastAPI:
    repo_root = (root_dir or Path(__file__).resolve().parents[2]).resolve()
    web_ui_dir = repo_root / "web_ui"
    config_dir = repo_root / "config"

    password = require_env("KIS_WEB_DASHBOARD_PASSWORD")
    session_secret = require_env("KIS_WEB_DASHBOARD_SESSION_SECRET")
    allow_insecure_http = os.getenv("KIS_WEB_DASHBOARD_INSECURE_HTTP") == "1"

    app = FastAPI(title="KIS Command Center")
    app.state.repo_root = repo_root
    app.state.web_ui_dir = web_ui_dir
    app.state.config_dir = config_dir
    app.state.dashboard_password = password
    app.state.dashboard_service = dashboard_service or DashboardService(repo_root)
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=not allow_insecure_http,
        session_cookie="kis-web-session",
        max_age=60 * 60 * 12,
    )
    app.mount("/static", StaticFiles(directory=web_ui_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((web_ui_dir / "index.html").read_text(encoding="utf-8"))

    @app.post("/api/login")
    def login(payload: LoginRequest, request: Request) -> dict[str, object]:
        if payload.password != app.state.dashboard_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
        request.session["authenticated"] = True
        request.session["csrf_token"] = secrets.token_urlsafe(24)
        return {"authenticated": True, "csrf_token": request.session["csrf_token"]}

    @app.post("/api/logout")
    def logout(request: Request) -> dict[str, object]:
        request.session.clear()
        return {"authenticated": False}

    @app.get("/api/session")
    def session(request: Request, _: bool = Depends(require_auth)) -> dict[str, object]:
        return {"authenticated": True, "csrf_token": request.session.get("csrf_token")}

    @app.get("/api/dashboard")
    def dashboard(
        market: Market = Query(default="kr"),
        interval_minutes: int = Query(default=10, ge=1, le=240),
        _: bool = Depends(require_auth),
    ) -> dict[str, object]:
        return app.state.dashboard_service.build_dashboard(market, interval_minutes)

    @app.get("/api/watchlist")
    def get_watchlist(
        market: Market = Query(default="kr"), _: bool = Depends(require_auth)
    ) -> dict[str, object]:
        items = load_watchlist(config_dir, market)
        return {"market": market, "items": items}

    @app.post("/api/watchlist")
    def add_watchlist(
        payload: WatchlistItemInput, _: bool = Depends(require_auth_and_csrf)
    ) -> dict[str, object]:
        items = load_watchlist(config_dir, payload.market)
        normalized_code = payload.code.strip().upper() if payload.market == "us" else payload.code.strip()
        if any(str(item.get("code", "")).upper() == normalized_code.upper() for item in items):
            raise HTTPException(status_code=409, detail="already exists")
        item = build_watchlist_item(payload)
        items.append(item)
        save_watchlist(config_dir, payload.market, items)
        return {"market": payload.market, "items": items}

    @app.delete("/api/watchlist/{code}")
    def remove_watchlist(
        code: str, market: Market = Query(default="kr"), _: bool = Depends(require_auth_and_csrf)
    ) -> dict[str, object]:
        normalized_code = code.strip().upper() if market == "us" else code.strip()
        items = load_watchlist(config_dir, market)
        filtered = [item for item in items if str(item.get("code", "")).upper() != normalized_code.upper()]
        save_watchlist(config_dir, market, filtered)
        return {"market": market, "items": filtered}

    return app


def require_auth(request: Request) -> bool:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
    return True


def require_auth_and_csrf(request: Request) -> bool:
    require_auth(request)
    expected = request.session.get("csrf_token")
    received = request.headers.get("X-CSRF-Token")
    if not expected or not received or not secrets.compare_digest(str(expected), str(received)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf check failed")
    return True


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def load_watchlist(config_dir: Path, market: Market) -> list[dict[str, object]]:
    path = config_dir / f"watchlist.{market}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_watchlist(config_dir: Path, market: Market, items: list[dict[str, object]]) -> None:
    path = config_dir / f"watchlist.{market}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def build_watchlist_item(payload: WatchlistItemInput) -> dict[str, object]:
    if payload.market == "us":
        excd = (payload.excd or "NAS").strip().upper()
        market_label = payload.market_label.strip() if payload.market_label else excd
        return {
            "type": "stock",
            "code": payload.code.strip().upper(),
            "name": payload.name.strip(),
            "market": market_label,
            "excd": excd,
        }
    market_label = payload.market_label.strip() if payload.market_label else payload.code.strip()
    return {
        "type": "stock",
        "code": payload.code.strip(),
        "name": payload.name.strip(),
        "market": market_label,
    }
