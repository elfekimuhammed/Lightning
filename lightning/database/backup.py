"""Backups: a consistent copy of the single database file.

Files are named ``lightning_yyyy-mm-dd_HHMM.db`` and the newest ``keep`` are retained.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .connection import Database


def backup(db: Database, folder: str | Path, keep: int = 30) -> Path | None:
    if db.path == ":memory:" or not Path(db.path).exists():
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    target = folder / f"lightning_{stamp}.db"
    counter = 1
    while target.exists():
        counter += 1
        target = folder / f"lightning_{stamp}_{counter}.db"
    dest = sqlite3.connect(target)
    try:
        db.conn.backup(dest)
    finally:
        dest.close()
    backups = sorted(folder.glob("lightning_*.db"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
    return target
