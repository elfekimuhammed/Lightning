"""python -m tools.market collect|backfill|pack ... (see tools/market/__init__.py)."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lightning.market.bundle import MarketFileError
from lightning.market.packs import PACKS, pack_release, publishable, read_zip
from lightning.market.update import DEFAULT_URL, update_packs

from .alarm import alarms
from .collect import backfill, collect
from .http import Polite


def release_bundle(out: Path, url: str, required: bool) -> int:
    """Download the default packs and zip them for the app, checking the result reads back whole."""
    defaults = publishable(p.id for p in PACKS.values() if p.default)  # we ship only what we may republish
    with tempfile.TemporaryDirectory(prefix="lightning-market-") as folder:
        try:
            _, missing = update_packs(Path(folder), defaults, url)
            if missing:
                raise MarketFileError(f"Not published yet: {', '.join(missing)}.")
            out.parent.mkdir(parents=True, exist_ok=True)
            pack_release(Path(folder), out, defaults)
            packs = read_zip(out.read_bytes())
        except MarketFileError as exc:
            out.unlink(missing_ok=True)
            print(f"{'error' if required else 'warning'}: no price files for this build: {exc}", file=sys.stderr)
            return 1 if required else 0
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB): "
          + ", ".join(f"{p} of {m.created_at[:10]}" for p, m in sorted(packs.items())))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.market")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("collect", help="today's prices for the packs whose market traded")
    run.add_argument("--root", default="market")
    run.add_argument("--packs", default=",".join(PACKS))
    history = sub.add_parser("backfill", help="whole history for some instruments")
    history.add_argument("--root", default="market")
    history.add_argument("keys", nargs="+")
    zipped = sub.add_parser("pack", help="zip packs for a release (the default packs unless named)")
    zipped.add_argument("--root", default="market")
    zipped.add_argument("--out", default="market.zip")
    zipped.add_argument("--packs", default=",".join(p.id for p in PACKS.values() if p.default))
    zipped.add_argument("--daily-months", type=int, default=13)
    release = sub.add_parser("release", help="the default packs the release ZIP carries, downloaded from the "
                                             "published price files (lightning/market/market.zip)")
    release.add_argument("--out", default="lightning/market/market.zip")
    release.add_argument("--url", default=DEFAULT_URL)
    release.add_argument("--required", action="store_true",
                         help="fail when the price files cannot be had (a tagged release); otherwise warn")
    alarm = sub.add_parser("alarm", help="sources failing twice in a row, and those that recovered (JSON)")
    alarm.add_argument("--root", default="market")
    args = parser.parse_args(argv)
    if args.command == "release":
        return release_bundle(Path(args.out), args.url, args.required)
    if args.command == "alarm":
        print(json.dumps(alarms(Path(args.root)), indent=2))
        return 0
    now = datetime.now(timezone.utc)
    today, created_at = now.date().isoformat(), now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.command == "pack":
        print(pack_release(Path(args.root), Path(args.out), args.packs.split(","), args.daily_months))
        return 0
    session = Polite()
    if args.command == "collect":
        report = collect(Path(args.root), session, today, created_at, tuple(args.packs.split(",")))
    else:
        report = backfill(Path(args.root), session, args.keys, today, created_at)
    print(json.dumps(report, indent=2, sort_keys=True))
    failing = [f"{pack}/{name}" for pack, health in report.items() if not pack.startswith("_")
               for name, entry in health.items() if not name.startswith("_") and not entry.get("ok", True)]
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
