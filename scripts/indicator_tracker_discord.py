#!/usr/bin/env python3
"""Send indicator chart images through one Discord webhook."""

from __future__ import annotations

import json
import mimetypes
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

DISCORD_ATTACHMENT_LIMIT = 10


class DiscordDeliveryError(RuntimeError):
    """Raised when a Discord chart batch cannot be sent."""


def load_discord_webhook_url(secrets_path: Path) -> str:
    try:
        root = json.loads(secrets_path.read_text(encoding="utf-8"))
        webhook = root["providers"]["discord"]["indicator_tracker_webhook_url"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DiscordDeliveryError(
            f"Discord 웹훅 시크릿을 읽을 수 없습니다: {secrets_path}"
        ) from exc
    if not isinstance(webhook, str):
        raise DiscordDeliveryError("Discord 웹훅 URL 형식이 올바르지 않습니다.")
    webhook = webhook.strip()
    parsed = urllib.parse.urlsplit(webhook)
    path_parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "discord.com"
        or parsed.fragment
        or len(path_parts) != 4
        or path_parts[:2] != ["api", "webhooks"]
        or not path_parts[2].isdigit()
        or not path_parts[3]
    ):
        raise DiscordDeliveryError("Discord 웹훅 URL 형식이 올바르지 않습니다.")
    return webhook


def _webhook_wait_url(webhook_url: str) -> str:
    parsed = urllib.parse.urlsplit(webhook_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["wait"] = "true"
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))


def split_delivery_batches(paths: list[Path]) -> list[tuple[str, list[Path]]]:
    if len(paths) == 16:
        return [
            ("수급·국내시장", paths[:7]),
            ("미국 주가지수", paths[7:11]),
            ("환율·금리·금", paths[11:]),
        ]
    return [
        (f"차트 {index // DISCORD_ATTACHMENT_LIMIT + 1}", paths[index : index + DISCORD_ATTACHMENT_LIMIT])
        for index in range(0, len(paths), DISCORD_ATTACHMENT_LIMIT)
    ]


def _multipart_payload(message: str, paths: list[Path]) -> tuple[str, bytes]:
    if not paths or len(paths) > DISCORD_ATTACHMENT_LIMIT:
        raise DiscordDeliveryError(
            f"Discord 첨부파일은 메시지당 1~{DISCORD_ATTACHMENT_LIMIT}개여야 합니다."
        )
    boundary = f"----indicator-tracker-{secrets.token_hex(16)}"
    payload = {
        "content": message,
        "attachments": [
            {"id": index, "filename": path.name}
            for index, path in enumerate(paths)
        ],
    }
    chunks: list[bytes] = []

    def add_field(name: str, value: bytes, *, filename: str | None = None, content_type: str) -> None:
        chunks.append(f"--{boundary}\r\n".encode())
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            disposition += f'; filename="{filename}"'
        chunks.append(f"{disposition}\r\n".encode())
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        chunks.append(value)
        chunks.append(b"\r\n")

    add_field(
        "payload_json",
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json; charset=utf-8",
    )
    for index, path in enumerate(paths):
        if not path.is_file():
            raise DiscordDeliveryError(f"첨부 이미지가 없습니다: {path}")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        add_field(
            f"files[{index}]",
            path.read_bytes(),
            filename=path.name,
            content_type=content_type,
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def send_discord_batch(
    paths: list[Path],
    *,
    message: str,
    webhook_url: str,
) -> str:
    boundary, body = _multipart_payload(message, paths)
    request = urllib.request.Request(
        _webhook_wait_url(webhook_url),
        method="POST",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "kis-market-dashboard/indicator-tracker",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result: dict[str, Any] = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DiscordDeliveryError(f"Discord HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise DiscordDeliveryError("Discord 전송 네트워크 오류가 발생했습니다.") from exc
    except json.JSONDecodeError as exc:
        raise DiscordDeliveryError("Discord 전송 응답을 해석할 수 없습니다.") from exc
    message_id = str(result.get("id", ""))
    if not message_id:
        raise DiscordDeliveryError("Discord 전송 응답에 message id가 없습니다.")
    return message_id


def send_indicator_charts(
    paths: list[Path],
    *,
    webhook_url: str,
    generated_at: str,
) -> list[str]:
    date_label = datetime.fromisoformat(generated_at).strftime("%Y-%m-%d")
    message_ids = []
    for label, batch in split_delivery_batches(paths):
        message_ids.append(
            send_discord_batch(
                batch,
                message=f"지표 추적자 {date_label} · {label} ({len(batch)}장)",
                webhook_url=webhook_url,
            )
        )
    return message_ids
