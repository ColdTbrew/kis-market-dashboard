#!/usr/bin/env python3
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "tmp"
DEFAULT_WATCHLIST_PATH = ROOT / "config" / "watchlist.json"

sys.path.insert(0, str(SCRIPTS_DIR))

import kis_market_dashboard_data as data_module
import kis_market_dashboard_render as render_module


def watchlist_path_from_env():
    return Path(os.getenv("KIS_DASHBOARD_WATCHLIST", DEFAULT_WATCHLIST_PATH))


def load_watchlist():
    path = watchlist_path_from_env()
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_watchlist(watchlist):
    path = watchlist_path_from_env()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2))


def cmd_generate(args):
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    json_out = Path(args.json_out) if args.json_out else out_dir / "kis_market_dashboard.json"
    png_out = Path(args.png_out) if args.png_out else out_dir / "kis_market_dashboard.png"
    out_dir.mkdir(parents=True, exist_ok=True)

    previous_json = os.environ.get("KIS_DASHBOARD_JSON")
    previous_png = os.environ.get("KIS_DASHBOARD_PNG")
    try:
        os.environ["KIS_DASHBOARD_JSON"] = str(json_out)
        if args.render:
            os.environ["KIS_DASHBOARD_PNG"] = str(png_out)

        with contextlib.redirect_stdout(io.StringIO()):
            data_module.main()
        if args.render:
            with contextlib.redirect_stdout(io.StringIO()):
                render_module.main()

        if args.send:
            target = args.target or os.getenv("OPENCLAW_TARGET", "")
            if not target:
                raise SystemExit("--send requires --target or OPENCLAW_TARGET")
            channel = args.channel or os.getenv("OPENCLAW_CHANNEL", "telegram")
            account = args.account or os.getenv("OPENCLAW_ACCOUNT", "default")
            subprocess.run(
                [
                    "openclaw",
                    "message",
                    "send",
                    "--channel",
                    channel,
                    "--account",
                    account,
                    "--target",
                    target,
                    "--message",
                    "KR 마켓 대시보드",
                    "--media",
                    str(png_out),
                ],
                check=True,
            )

        print(str(png_out if args.render else json_out))
    finally:
        if previous_json is None:
            os.environ.pop("KIS_DASHBOARD_JSON", None)
        else:
            os.environ["KIS_DASHBOARD_JSON"] = previous_json

        if previous_png is None:
            os.environ.pop("KIS_DASHBOARD_PNG", None)
        else:
            os.environ["KIS_DASHBOARD_PNG"] = previous_png


def cmd_watchlist_list(_args):
    watchlist = load_watchlist()
    if not watchlist:
        print("watchlist is empty")
        return
    for item in watchlist:
        print(f"{item['code']}\t{item['name']}")


def cmd_watchlist_add(args):
    watchlist = load_watchlist()
    code = args.code.strip()
    if any(item.get("code") == code for item in watchlist):
        print(f"already exists: {code}")
        return
    item = {
        "type": "stock",
        "name": args.name.strip(),
        "code": code,
        "market": args.market.strip() if args.market else code,
    }
    watchlist.append(item)
    save_watchlist(watchlist)
    print(f"added: {code}\t{item['name']}")


def cmd_watchlist_remove(args):
    watchlist = load_watchlist()
    code = args.code.strip()
    filtered = [item for item in watchlist if item.get("code") != code]
    if len(filtered) == len(watchlist):
        print(f"not found: {code}")
        return
    save_watchlist(filtered)
    print(f"removed: {code}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate the KIS market dashboard image and manage the stock watchlist."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Fetch market data and render the dashboard image.")
    generate.add_argument("--out-dir", help="Directory for generated files. Default: ./tmp")
    generate.add_argument("--json-out", help="Explicit JSON output path. Overrides --out-dir.")
    generate.add_argument("--png-out", help="Explicit PNG output path. Overrides --out-dir.")
    generate.add_argument(
        "--no-render",
        dest="render",
        action="store_false",
        help="Fetch data only and skip PNG rendering.",
    )
    generate.add_argument(
        "--send",
        action="store_true",
        help="Send the rendered PNG through openclaw message send.",
    )
    generate.add_argument("--target", help="openclaw target. Defaults to OPENCLAW_TARGET.")
    generate.add_argument("--channel", help="openclaw channel. Defaults to OPENCLAW_CHANNEL or telegram.")
    generate.add_argument("--account", help="openclaw account. Defaults to OPENCLAW_ACCOUNT or default.")
    generate.set_defaults(func=cmd_generate, render=True)

    watchlist = subparsers.add_parser("watchlist", help="Inspect or modify the dashboard stock watchlist.")
    watchlist_subparsers = watchlist.add_subparsers(dest="watchlist_command", required=True)

    watchlist_list = watchlist_subparsers.add_parser("list", help="Print the current watchlist.")
    watchlist_list.set_defaults(func=cmd_watchlist_list)

    watchlist_add = watchlist_subparsers.add_parser("add", help="Add a stock to the watchlist.")
    watchlist_add.add_argument("code", help="6-digit stock code, for example 000270.")
    watchlist_add.add_argument("name", help="Display name shown on the dashboard.")
    watchlist_add.add_argument("--market", help="Optional market pill label. Defaults to the stock code.")
    watchlist_add.set_defaults(func=cmd_watchlist_add)

    watchlist_remove = watchlist_subparsers.add_parser("remove", help="Remove a stock from the watchlist.")
    watchlist_remove.add_argument("code", help="6-digit stock code to remove.")
    watchlist_remove.set_defaults(func=cmd_watchlist_remove)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
