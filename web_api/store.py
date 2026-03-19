from __future__ import annotations

import json
import mimetypes
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .settings import Settings

Market = Literal["kr", "us"]


def normalize_market(value: str | None) -> Market:
    return "us" if (value or "kr").strip().lower() == "us" else "kr"


def exchange_label(excd: str | None) -> str:
    normalized = (excd or "").strip().upper()
    return {"NAS": "NASDAQ", "NYS": "NYSE", "AMS": "AMEX"}.get(normalized, normalized)


def watchlist_path(settings: Settings, market: Market) -> Path:
    return settings.config_dir / f"watchlist.{market}.json"


def load_watchlist(settings: Settings, market: Market) -> list[dict]:
    path = watchlist_path(settings, market)
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text())
    except Exception:
        return []
    return value if isinstance(value, list) else []


def save_watchlist(settings: Settings, market: Market, items: list[dict]) -> None:
    path = watchlist_path(settings, market)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2))


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    id: str
    market: Market
    created_at: str
    directory: Path
    metadata_path: Path
    json_path: Path
    image_path: Path
    command: list[str]

    def to_response(self) -> dict:
        return {
            "artifact_id": self.id,
            "market": self.market,
            "created_at": self.created_at,
            "directory": str(self.directory),
            "json": {
                "path": str(self.json_path),
                "name": self.json_path.name,
                "content_type": "application/json",
            },
            "image": {
                "path": str(self.image_path),
                "name": self.image_path.name,
                "content_type": mimetypes.guess_type(self.image_path.name)[0] or "application/octet-stream",
            },
            "command": self.command,
        }


def artifact_directory(settings: Settings, artifact_id: str) -> Path:
    return settings.artifact_dir / artifact_id


def artifact_metadata_path(settings: Settings, artifact_id: str) -> Path:
    return artifact_directory(settings, artifact_id) / "metadata.json"


def create_artifact_record(
    settings: Settings,
    market: Market,
    command: list[str],
) -> ArtifactRecord:
    artifact_id = uuid4().hex
    directory = artifact_directory(settings, artifact_id)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"kis_market_dashboard.{market}.json"
    image_path = directory / f"kis_market_dashboard.{market}.png"
    created_at = datetime.now(UTC).isoformat()
    record = ArtifactRecord(
        id=artifact_id,
        market=market,
        created_at=created_at,
        directory=directory,
        metadata_path=directory / "metadata.json",
        json_path=json_path,
        image_path=image_path,
        command=command,
    )
    record.metadata_path.write_text(json.dumps(record.to_response(), ensure_ascii=False, indent=2))
    return record


def store_artifact_metadata(record: ArtifactRecord) -> None:
    record.metadata_path.write_text(json.dumps(record.to_response(), ensure_ascii=False, indent=2))


def load_artifact(settings: Settings, artifact_id: str) -> ArtifactRecord | None:
    metadata_path = artifact_metadata_path(settings, artifact_id)
    if not metadata_path.exists():
        return None
    try:
        payload = json.loads(metadata_path.read_text())
    except Exception:
        return None

    directory = metadata_path.parent
    return ArtifactRecord(
        id=payload.get("artifact_id", artifact_id),
        market=normalize_market(payload.get("market")),
        created_at=str(payload.get("created_at", "")),
        directory=directory,
        metadata_path=metadata_path,
        json_path=Path(str(payload.get("json", {}).get("path", directory / "kis_market_dashboard.kr.json"))),
        image_path=Path(str(payload.get("image", {}).get("path", directory / "kis_market_dashboard.kr.png"))),
        command=list(payload.get("command", [])),
    )


def list_artifacts(settings: Settings) -> list[ArtifactRecord]:
    if not settings.artifact_dir.exists():
        return []
    records: list[ArtifactRecord] = []
    for metadata_path in sorted(settings.artifact_dir.glob("*/metadata.json"), reverse=True):
        record = load_artifact(settings, metadata_path.parent.name)
        if record:
            records.append(record)
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records
