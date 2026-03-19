from __future__ import annotations

import json
import mimetypes
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .settings import Settings, load_settings
from .store import (
    ArtifactRecord,
    exchange_label,
    list_artifacts,
    load_artifact,
    load_watchlist,
    normalize_market,
    save_watchlist,
    store_artifact_metadata,
)

Market = Literal["kr", "us"]


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class WatchlistRequest(BaseModel):
    market: Market = "kr"
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    market_label: str | None = None
    excd: str | None = None


class GenerateRequest(BaseModel):
    market: Market = "kr"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def require_admin(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="authentication required")


def session_payload(request: Request) -> dict:
    return {
        "authenticated": is_authenticated(request),
        "user": "admin" if is_authenticated(request) else None,
    }


def login_payload(request: Request, settings: Settings) -> dict:
    if request.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="invalid password")
    return {"authenticated": True, "user": "admin"}


def build_command(settings: Settings, market: Market, artifact_dir: Path) -> list[str]:
    return [
        "uv",
        "run",
        "python",
        "kis_market_dashboard.py",
        "generate",
        "--market",
        market,
        "--out-dir",
        str(artifact_dir),
    ]


def generate_artifact(settings: Settings, market: Market) -> ArtifactRecord:
    artifact_id = uuid4().hex
    artifact_dir = settings.artifact_dir / artifact_id
    command = build_command(settings, market, artifact_dir)
    record = ArtifactRecord(
        id=artifact_id,
        market=market,
        created_at="",
        directory=artifact_dir,
        metadata_path=artifact_dir / "metadata.json",
        json_path=artifact_dir / f"kis_market_dashboard.{market}.json",
        image_path=artifact_dir / f"kis_market_dashboard.{market}.png",
        command=command,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["KIS_DASHBOARD_OUT_DIR"] = str(record.directory)
    subprocess.run(command, check=True, cwd=str(settings.root), env=env)

    if not record.json_path.exists() or not record.image_path.exists():
        raise HTTPException(status_code=500, detail="generated files missing")

    record = ArtifactRecord(
        id=record.id,
        market=record.market,
        created_at=datetime.now(UTC).isoformat(),
        directory=record.directory,
        metadata_path=record.metadata_path,
        json_path=record.json_path,
        image_path=record.image_path,
        command=record.command,
    )
    store_artifact_metadata(record)
    return record


def watchlist_add(settings: Settings, payload: WatchlistRequest) -> dict:
    market = normalize_market(payload.market)
    items = load_watchlist(settings, market)
    code = payload.code.strip().upper() if market == "us" else payload.code.strip()
    if any(str(item.get("code", "")).upper() == code.upper() for item in items):
        raise HTTPException(status_code=409, detail="watchlist item already exists")

    if market == "us":
        excd = (payload.excd or "NAS").strip().upper()
        item = {
            "type": "stock",
            "name": payload.name.strip(),
            "code": code,
            "market": payload.market_label.strip() if payload.market_label else exchange_label(excd),
            "excd": excd,
        }
    else:
        item = {
            "type": "stock",
            "name": payload.name.strip(),
            "code": code,
            "market": payload.market_label.strip() if payload.market_label else code,
        }

    items.append(item)
    save_watchlist(settings, market, items)
    return item


def watchlist_remove(settings: Settings, market: Market, code: str) -> bool:
    items = load_watchlist(settings, market)
    normalized = code.strip().upper() if market == "us" else code.strip()
    filtered = [item for item in items if str(item.get("code", "")).upper() != normalized.upper()]
    if len(filtered) == len(items):
        return False
    save_watchlist(settings, market, filtered)
    return True


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="KIS Market Dashboard Web API")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        same_site="lax",
        https_only=False,
    )
    app.state.settings = settings

    @app.post("/api/login")
    def login(request: Request, payload: LoginRequest, settings: Settings = Depends(get_settings)):
        if payload.password != settings.admin_password:
            raise HTTPException(status_code=401, detail="invalid password")
        request.session.clear()
        request.session["authenticated"] = True
        request.session["user"] = "admin"
        return session_payload(request)

    @app.post("/api/logout")
    def logout(request: Request):
        request.session.clear()
        return session_payload(request)

    @app.get("/api/session")
    def session(request: Request):
        return session_payload(request)

    @app.get("/api/watchlist")
    def get_watchlist(
        request: Request,
        market: Market = "kr",
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        normalized = normalize_market(market)
        return {"market": normalized, "items": load_watchlist(settings, normalized)}

    @app.post("/api/watchlist", status_code=201)
    def post_watchlist(
        request: Request,
        payload: WatchlistRequest,
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        item = watchlist_add(settings, payload)
        return item

    @app.delete("/api/watchlist/{code}")
    def delete_watchlist(
        request: Request,
        code: str,
        market: Market = "kr",
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        removed = watchlist_remove(settings, normalize_market(market), code)
        if not removed:
            raise HTTPException(status_code=404, detail="watchlist item not found")
        return {"removed": True}

    @app.post("/api/generate")
    def post_generate(
        request: Request,
        payload: GenerateRequest,
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        record = generate_artifact(settings, normalize_market(payload.market))
        return record.to_response()

    @app.get("/api/artifacts")
    def get_artifacts(request: Request, settings: Settings = Depends(get_settings)):
        require_admin(request)
        return {"items": [record.to_response() for record in list_artifacts(settings)]}

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(
        request: Request,
        artifact_id: str,
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        record = load_artifact(settings, artifact_id)
        if not record:
            raise HTTPException(status_code=404, detail="artifact not found")
        return record.to_response()

    @app.get("/api/artifacts/{artifact_id}/download")
    def download_artifact(
        request: Request,
        artifact_id: str,
        settings: Settings = Depends(get_settings),
    ):
        require_admin(request)
        record = load_artifact(settings, artifact_id)
        if not record or not record.image_path.exists():
            raise HTTPException(status_code=404, detail="artifact not found")
        media_type = mimetypes.guess_type(record.image_path.name)[0] or "application/octet-stream"
        return FileResponse(record.image_path, media_type=media_type, filename=record.image_path.name)

    return app


app = create_app()
