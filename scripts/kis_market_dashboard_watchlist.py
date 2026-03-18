#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = Path(os.getenv("KIS_DASHBOARD_WATCHLIST", ROOT / "config" / "watchlist.json"))


def load_watchlist():
    if not WATCHLIST_PATH.exists():
        return []
    return json.loads(WATCHLIST_PATH.read_text())


def save_watchlist(watchlist):
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(watchlist, ensure_ascii=False, indent=2))


def list_items(_args):
    watchlist = load_watchlist()
    if not watchlist:
        print("watchlist is empty")
        return
    for item in watchlist:
        print(f"{item['code']}\t{item['name']}")


def add_item(args):
    watchlist = load_watchlist()
    code = args.code.strip()
    if any(item.get("code") == code for item in watchlist):
        print(f"already exists: {code}")
        return
    item = {
        "type": "stock",
        "name": args.name.strip(),
        "code": code,
        "market": code,
    }
    watchlist.append(item)
    save_watchlist(watchlist)
    print(f"added: {code}\t{args.name.strip()}")


def remove_item(args):
    watchlist = load_watchlist()
    code = args.code.strip()
    filtered = [item for item in watchlist if item.get("code") != code]
    if len(filtered) == len(watchlist):
        print(f"not found: {code}")
        return
    save_watchlist(filtered)
    print(f"removed: {code}")


def build_parser():
    parser = argparse.ArgumentParser(description="Manage dashboard watchlist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Show current watchlist")
    list_parser.set_defaults(func=list_items)

    add_parser = subparsers.add_parser("add", help="Add a stock to watchlist")
    add_parser.add_argument("code", help="6-digit stock code")
    add_parser.add_argument("name", help="Display name")
    add_parser.set_defaults(func=add_item)

    remove_parser = subparsers.add_parser("remove", help="Remove a stock from watchlist")
    remove_parser.add_argument("code", help="6-digit stock code")
    remove_parser.set_defaults(func=remove_item)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
