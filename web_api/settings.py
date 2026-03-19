from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    return Path(raw) if raw else default


@dataclass(frozen=True, slots=True)
class Settings:
    root: Path
    config_dir: Path
    artifact_dir: Path
    admin_password: str
    session_secret: str
    session_cookie_name: str = "kis_dashboard_session"

    @property
    def cli_entrypoint(self) -> Path:
        return self.root / "kis_market_dashboard.py"


def load_settings() -> Settings:
    root = _env_path("KIS_DASHBOARD_ROOT", Path(__file__).resolve().parents[1])
    return Settings(
        root=root,
        config_dir=_env_path("KIS_DASHBOARD_CONFIG_DIR", root / "config"),
        artifact_dir=_env_path("KIS_DASHBOARD_ARTIFACT_DIR", root / "tmp" / "artifacts"),
        admin_password=os.getenv("KIS_DASHBOARD_ADMIN_PASSWORD", "").strip(),
        session_secret=os.getenv("KIS_DASHBOARD_SESSION_SECRET", "").strip()
        or os.getenv("KIS_DASHBOARD_ADMIN_PASSWORD", "").strip()
        or "kis-dashboard-dev-secret",
    )

