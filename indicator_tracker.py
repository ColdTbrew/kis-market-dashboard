#!/usr/bin/env python3
"""Generate and optionally send the daily fixed-source indicator tracker."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "tmp"
sys.path.insert(0, str(SCRIPTS_DIR))

from indicator_tracker_data import (  # noqa: E402
    DEFAULT_SECRETS_PATH,
    DataSourceError,
    TossClient,
    build_report,
    load_toss_credentials,
)
from indicator_tracker_discord import (  # noqa: E402
    DiscordDeliveryError,
    load_discord_webhook_url,
    send_indicator_charts,
)
from indicator_tracker_render import render_report  # noqa: E402


def save_report(report: dict[str, object], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cmd_generate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else DEFAULT_OUT_DIR
    secrets_path = Path(args.secrets_path).expanduser()
    report = build_report(TossClient(load_toss_credentials(secrets_path)))

    date_slug = datetime.fromisoformat(report["generated_at"]).strftime("%Y%m%d")
    json_path = out_dir / f"indicator_tracker.{date_slug}.json"
    save_report(report, json_path)
    image_paths = [] if args.no_render else render_report(report, out_dir)

    if args.send:
        if args.no_render:
            raise SystemExit("--send cannot be combined with --no-render")
        message_ids = send_indicator_charts(
            image_paths,
            webhook_url=load_discord_webhook_url(secrets_path),
            generated_at=report["generated_at"],
        )
        for message_id in message_ids:
            print(f"Discord message: {message_id}")

    print(json_path)
    for path in image_paths:
        print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Toss/FRED fixed-source daily indicator tracker (no provider fallback)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Fetch, render, and optionally send the report.")
    generate.add_argument("--out-dir", help="Output directory. Default: ./tmp")
    generate.add_argument(
        "--secrets-path",
        default=str(DEFAULT_SECRETS_PATH),
        help="OpenClaw secrets JSON path.",
    )
    generate.add_argument("--no-render", action="store_true", help="Write JSON without PNG files.")
    generate.add_argument(
        "--send",
        action="store_true",
        help="Send all chart PNGs as Discord multi-attachment messages.",
    )
    generate.set_defaults(func=cmd_generate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except DataSourceError as exc:
        print(f"indicator tracker failed: {exc}", file=sys.stderr)
        return 1
    except DiscordDeliveryError as exc:
        print(f"Discord delivery failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
