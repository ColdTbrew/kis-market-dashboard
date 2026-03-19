from __future__ import annotations

import json
import os
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

Market = Literal["kr", "us"]
ImageFormat = Literal["png", "webp"]


class LoginRequest(BaseModel):
    password: str


class WatchlistItemInput(BaseModel):
    market: Market
    code: str
    name: str
    market_label: str | None = None
    excd: str | None = None


class GenerateRequest(BaseModel):
    market: Market = "kr"
    format: ImageFormat = "png"
    interval_minutes: int = Field(default=10, ge=1, le=240)
    candle_width_scale: float = Field(default=1.0, gt=0, le=2)
    width_px: int = Field(default=1080, ge=480, le=4096)
    height_px: int | None = Field(default=None, ge=480, le=8192)
    render_scale: float = Field(default=2.0, ge=1.0, le=4.0)
    webp_quality: int = Field(default=90, ge=1, le=100)


def create_app(root_dir: Path | None = None) -> FastAPI:
    repo_root = (root_dir or Path(__file__).resolve().parents[2]).resolve()
    web_ui_dir = repo_root / "web_ui"
    config_dir = repo_root / "config"
    artifacts_root = repo_root / "tmp" / "web-artifacts"

    password = require_env("KIS_WEB_DASHBOARD_PASSWORD")
    session_secret = require_env("KIS_WEB_DASHBOARD_SESSION_SECRET")
    allow_insecure_http = os.getenv("KIS_WEB_DASHBOARD_INSECURE_HTTP") == "1"

    app = FastAPI(title="KIS Command Center")
    app.state.repo_root = repo_root
    app.state.web_ui_dir = web_ui_dir
    app.state.config_dir = config_dir
    app.state.artifacts_root = artifacts_root
    app.state.dashboard_password = password
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

    @app.post("/api/generate")
    def generate_dashboard(
        payload: GenerateRequest, _: bool = Depends(require_auth_and_csrf)
    ) -> dict[str, object]:
        artifact = run_generate(repo_root, artifacts_root, payload)
        return {"artifact": artifact}

    @app.get("/api/artifacts")
    def list_artifacts(_: bool = Depends(require_auth)) -> dict[str, list[dict[str, object]]]:
        artifacts = []
        if artifacts_root.exists():
            for path in sorted(artifacts_root.iterdir(), reverse=True):
                metadata = path / "metadata.json"
                if metadata.exists():
                    artifacts.append(json.loads(metadata.read_text()))
        return {"artifacts": artifacts}

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str, _: bool = Depends(require_auth)) -> dict[str, object]:
        return {"artifact": read_metadata(artifacts_root / artifact_id)}

    @app.get("/api/artifacts/{artifact_id}/download")
    def download_artifact(artifact_id: str, _: bool = Depends(require_auth)) -> Response:
        metadata = read_metadata(artifacts_root / artifact_id)
        artifact_dir = artifacts_root / artifact_id
        image_path = artifact_dir / metadata["image_name"]
        return FileResponse(image_path, media_type=metadata["media_type"], filename=image_path.name)

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


def run_generate(repo_root: Path, artifacts_root: Path, payload: GenerateRequest) -> dict[str, object]:
    artifact_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    artifact_dir = artifacts_root / artifact_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_out = artifact_dir / "dashboard.json"
    image_name = f"dashboard.{payload.format}"
    image_out = artifact_dir / image_name

    command = [
        "uv",
        "run",
        "python",
        "kis_market_dashboard.py",
        "generate",
        "--market",
        payload.market,
        "--json-out",
        str(json_out),
        "--image-out",
        str(image_out),
        "--format",
        payload.format,
        "--interval-minutes",
        str(payload.interval_minutes),
        "--candle-width-scale",
        str(payload.candle_width_scale),
        "--width-px",
        str(payload.width_px),
        "--render-scale",
        str(payload.render_scale),
        "--webp-quality",
        str(payload.webp_quality),
    ]
    if payload.height_px:
        command.extend(["--height-px", str(payload.height_px)])

    try:
        subprocess.run(command, cwd=repo_root, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "dashboard generation failed"
        raise HTTPException(status_code=502, detail=detail[-500:]) from exc
    data = json.loads(json_out.read_text(encoding="utf-8"))
    metadata = {
        "id": artifact_id,
        "market": payload.market,
        "format": payload.format,
        "interval_minutes": payload.interval_minutes,
        "candle_width_scale": payload.candle_width_scale,
        "width_px": payload.width_px,
        "height_px": payload.height_px,
        "render_scale": payload.render_scale,
        "webp_quality": payload.webp_quality,
        "created_at": datetime.now(UTC).isoformat(),
        "image_name": image_name,
        "json_name": json_out.name,
        "media_type": "image/webp" if payload.format == "webp" else "image/png",
        "preview_url": f"/api/artifacts/{artifact_id}/download",
        "summary_count": len(data.get("summary_cards", [])),
        "stock_count": len(data.get("stocks", [])),
    }
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def read_metadata(path: Path) -> dict[str, object]:
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return json.loads(metadata_path.read_text(encoding="utf-8"))
