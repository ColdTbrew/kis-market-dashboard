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
CONFIG_DIR = ROOT / "config"
LEGACY_WATCHLIST_PATH = CONFIG_DIR / "watchlist.json"

sys.path.insert(0, str(SCRIPTS_DIR))

import kis_market_dashboard_data as data_module
import kis_market_dashboard_render as render_module


def normalize_market(value):
    return (value or "kr").strip().lower()


def watchlist_path_for_market(market):
    override = os.getenv("KIS_DASHBOARD_WATCHLIST")
    if override:
        return Path(override)

    normalized = normalize_market(market)
    path = CONFIG_DIR / f"watchlist.{normalized}.json"
    if normalized == "kr" and not path.exists() and LEGACY_WATCHLIST_PATH.exists():
        return LEGACY_WATCHLIST_PATH
    return path


def load_watchlist(market):
    path = watchlist_path_for_market(market)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_watchlist(watchlist, market):
    normalized = normalize_market(market)
    path = CONFIG_DIR / f"watchlist.{normalized}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2))


def default_json_path(out_dir, market):
    return out_dir / f"kis_market_dashboard.{normalize_market(market)}.json"


def default_png_path(out_dir, market):
    return out_dir / f"kis_market_dashboard.{normalize_market(market)}.png"


def market_message_title(market):
    return "KR 마켓 대시보드" if normalize_market(market) == "kr" else "US 마켓 대시보드"


def exchange_label(excd):
    return {
        "NAS": "NASDAQ",
        "NYS": "NYSE",
        "AMS": "AMEX",
    }.get((excd or "").strip().upper(), (excd or "").strip().upper())


def cmd_generate(args):
    market = normalize_market(args.market)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    json_out = Path(args.json_out) if args.json_out else default_json_path(out_dir, market)
    png_out = Path(args.png_out) if args.png_out else default_png_path(out_dir, market)
    watchlist_path = watchlist_path_for_market(market)
    out_dir.mkdir(parents=True, exist_ok=True)

    previous_json = os.environ.get("KIS_DASHBOARD_JSON")
    previous_png = os.environ.get("KIS_DASHBOARD_PNG")
    previous_market = os.environ.get("KIS_DASHBOARD_MARKET")
    previous_watchlist = os.environ.get("KIS_DASHBOARD_WATCHLIST")
    previous_interval = os.environ.get("KIS_DASHBOARD_INTERVAL_MINUTES")
    previous_candle_width = os.environ.get("KIS_DASHBOARD_CANDLE_WIDTH_SCALE")
    previous_width = os.environ.get("KIS_DASHBOARD_WIDTH_PX")
    previous_height = os.environ.get("KIS_DASHBOARD_HEIGHT_PX")
    previous_render_scale = os.environ.get("KIS_DASHBOARD_RENDER_SCALE")
    try:
        os.environ["KIS_DASHBOARD_JSON"] = str(json_out)
        os.environ["KIS_DASHBOARD_MARKET"] = market
        os.environ["KIS_DASHBOARD_WATCHLIST"] = str(watchlist_path)
        os.environ["KIS_DASHBOARD_INTERVAL_MINUTES"] = str(args.interval_minutes)
        os.environ["KIS_DASHBOARD_CANDLE_WIDTH_SCALE"] = str(args.candle_width_scale)
        os.environ["KIS_DASHBOARD_WIDTH_PX"] = str(args.width_px)
        os.environ["KIS_DASHBOARD_RENDER_SCALE"] = str(args.render_scale)
        if args.height_px:
            os.environ["KIS_DASHBOARD_HEIGHT_PX"] = str(args.height_px)
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
                    market_message_title(market),
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

        if previous_market is None:
            os.environ.pop("KIS_DASHBOARD_MARKET", None)
        else:
            os.environ["KIS_DASHBOARD_MARKET"] = previous_market

        if previous_watchlist is None:
            os.environ.pop("KIS_DASHBOARD_WATCHLIST", None)
        else:
            os.environ["KIS_DASHBOARD_WATCHLIST"] = previous_watchlist

        if previous_interval is None:
            os.environ.pop("KIS_DASHBOARD_INTERVAL_MINUTES", None)
        else:
            os.environ["KIS_DASHBOARD_INTERVAL_MINUTES"] = previous_interval

        if previous_candle_width is None:
            os.environ.pop("KIS_DASHBOARD_CANDLE_WIDTH_SCALE", None)
        else:
            os.environ["KIS_DASHBOARD_CANDLE_WIDTH_SCALE"] = previous_candle_width

        if previous_width is None:
            os.environ.pop("KIS_DASHBOARD_WIDTH_PX", None)
        else:
            os.environ["KIS_DASHBOARD_WIDTH_PX"] = previous_width

        if previous_height is None:
            os.environ.pop("KIS_DASHBOARD_HEIGHT_PX", None)
        else:
            os.environ["KIS_DASHBOARD_HEIGHT_PX"] = previous_height

        if previous_render_scale is None:
            os.environ.pop("KIS_DASHBOARD_RENDER_SCALE", None)
        else:
            os.environ["KIS_DASHBOARD_RENDER_SCALE"] = previous_render_scale


def cmd_watchlist_list(args):
    market = normalize_market(args.market)
    watchlist = load_watchlist(market)
    if not watchlist:
        print("watchlist is empty")
        return
    for item in watchlist:
        if market == "us":
            excd = item.get("excd", "")
            print(f"{item['code']}\t{item['name']}\t{excd}\t{item.get('market', '')}")
            continue
        print(f"{item['code']}\t{item['name']}\t{item.get('market', '')}")


def cmd_watchlist_add(args):
    market = normalize_market(args.market)
    watchlist = load_watchlist(market)
    code = args.code.strip().upper() if market == "us" else args.code.strip()
    if any(str(item.get("code", "")).upper() == code.upper() for item in watchlist):
        print(f"already exists: {code}")
        return

    if market == "us":
        excd = (args.excd or "NAS").strip().upper()
        item = {
            "type": "stock",
            "name": args.name.strip(),
            "code": code,
            "market": args.market_label.strip() if args.market_label else exchange_label(excd),
            "excd": excd,
        }
    else:
        item = {
            "type": "stock",
            "name": args.name.strip(),
            "code": code,
            "market": args.market_label.strip() if args.market_label else code,
        }

    watchlist.append(item)
    save_watchlist(watchlist, market)
    print(f"added: {code}\t{item['name']}")


def cmd_watchlist_remove(args):
    market = normalize_market(args.market)
    watchlist = load_watchlist(market)
    code = args.code.strip().upper() if market == "us" else args.code.strip()
    filtered = [item for item in watchlist if str(item.get("code", "")).upper() != code.upper()]
    if len(filtered) == len(watchlist):
        print(f"not found: {code}")
        return
    save_watchlist(filtered, market)
    print(f"removed: {code}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate the KIS market dashboard image and manage market-specific stock watchlists."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Fetch market data and render the dashboard image.")
    generate.add_argument(
        "--market",
        choices=["kr", "us"],
        default="kr",
        help="Dashboard market. Uses market-specific summary cards and watchlist.",
    )
    generate.add_argument("--out-dir", help="Directory for generated files. Default: ./tmp")
    generate.add_argument("--json-out", help="Explicit JSON output path. Overrides --out-dir.")
    generate.add_argument("--png-out", help="Explicit PNG output path. Overrides --out-dir.")
    generate.add_argument(
        "--width-px",
        type=int,
        default=1080,
        help="Final PNG width in pixels. Default: 1080",
    )
    generate.add_argument(
        "--height-px",
        type=int,
        help="Optional final PNG height in pixels. If omitted, content height is used.",
    )
    generate.add_argument(
        "--render-scale",
        type=float,
        default=2.0,
        help="Internal supersampling scale for sharper output. Default: 2.0",
    )
    generate.add_argument(
        "--interval-minutes",
        type=int,
        default=10,
        help="Candlestick interval in minutes. Default: 10",
    )
    generate.add_argument(
        "--candle-width-scale",
        type=float,
        default=1.0,
        help="Render-time candle width scale. Smaller values draw thinner candles. Default: 1.0",
    )
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

    watchlist = subparsers.add_parser("watchlist", help="Inspect or modify a market-specific stock watchlist.")
    watchlist_subparsers = watchlist.add_subparsers(dest="watchlist_command", required=True)

    watchlist_list = watchlist_subparsers.add_parser("list", help="Print the current watchlist.")
    watchlist_list.add_argument("--market", choices=["kr", "us"], default="kr", help="Watchlist market.")
    watchlist_list.set_defaults(func=cmd_watchlist_list)

    watchlist_add = watchlist_subparsers.add_parser("add", help="Add a stock to the watchlist.")
    watchlist_add.add_argument("--market", choices=["kr", "us"], default="kr", help="Watchlist market.")
    watchlist_add.add_argument("code", help="KR 6-digit code or US ticker symbol.")
    watchlist_add.add_argument("name", help="Display name shown on the dashboard.")
    watchlist_add.add_argument(
        "--market-label",
        help="Optional card pill label. KR defaults to the code, US defaults to the exchange label.",
    )
    watchlist_add.add_argument(
        "--excd",
        help="US exchange code for KIS, for example NAS or NYS. Ignored for KR. Default: NAS",
    )
    watchlist_add.set_defaults(func=cmd_watchlist_add)

    watchlist_remove = watchlist_subparsers.add_parser("remove", help="Remove a stock from the watchlist.")
    watchlist_remove.add_argument("--market", choices=["kr", "us"], default="kr", help="Watchlist market.")
    watchlist_remove.add_argument("code", help="KR 6-digit code or US ticker symbol to remove.")
    watchlist_remove.set_defaults(func=cmd_watchlist_remove)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
