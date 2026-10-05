"""python -m tools.market collect|backfill|pack ... (see tools/market/__init__.py)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lightning.market.bundle import pack

from .collect import MARKETS, backfill, collect
from .http import Polite


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.market")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("collect", help="today's prices from every source")
    run.add_argument("--folder", default="market")
    run.add_argument("--markets", default=",".join(MARKETS))
    history = sub.add_parser("backfill", help="whole history for some instruments")
    history.add_argument("--folder", default="market")
    history.add_argument("keys", nargs="+")
    zipped = sub.add_parser("pack", help="zip the folder for a release")
    zipped.add_argument("--folder", default="market")
    zipped.add_argument("--out", default="market.zip")
    zipped.add_argument("--daily-months", type=int, default=13)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    today, created_at = now.date().isoformat(), now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.command == "pack":
        print(pack(Path(args.folder), Path(args.out), args.daily_months))
        return 0
    session = Polite()
    if args.command == "collect":
        health = collect(Path(args.folder), session, today, created_at, tuple(args.markets.split(",")))
    else:
        health = backfill(Path(args.folder), session, args.keys, today, created_at)
    print(json.dumps(health, indent=2, sort_keys=True))
    failing = [name for name, entry in health.items() if not name.startswith("_") and not entry.get("ok", True)]
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
