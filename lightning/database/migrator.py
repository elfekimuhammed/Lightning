"""Applies numbered SQL files in ``migrations/`` once, in order.

Plain, readable SQL — no ORM. Applied versions are recorded in ``schema_migrations``.
A file whose first line is ``-- @optional`` is skipped (and recorded as SKIPPED)
if SQLite lacks a feature it needs, e.g. FTS5.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from lightning.core.dates import now_iso

from .connection import Database

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILE_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


def _migration_files() -> list[tuple[int, str, Path]]:
    files = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _FILE_RE.match(path.name)
        if match:
            files.append((int(match[1]), match[2], path))
    return files


def migrate(db: Database) -> list[str]:
    """Apply pending migrations. Returns the names applied or skipped this run."""
    conn = db.conn
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied: list[str] = []
    for version, name, path in _migration_files():
        if version in done:
            continue
        sql = path.read_text(encoding="utf-8")
        optional = sql.lstrip().startswith("-- @optional")
        status = "APPLIED"
        try:
            conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
        except sqlite3.OperationalError as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            # SQLite can leave an ALTER TABLE behind if an older process was
            # interrupted after the DDL but before schema_migrations was
            # updated.  Treat an already-present ADD COLUMN as applied and
            # rerun the rest of that migration.
            duplicate = re.search(r"duplicate column name: (\w+)", str(exc), re.IGNORECASE)
            add_column = re.search(r"ALTER TABLE\s+(\w+)\s+ADD COLUMN\s+(\w+)", sql, re.IGNORECASE)
            if duplicate and add_column and duplicate.group(1).casefold() == add_column.group(2).casefold():
                table, column = add_column.groups()
                columns = {row[1].casefold() for row in conn.execute(f"PRAGMA table_info({table})")}
                if column.casefold() in columns:
                    remaining = re.sub(r"ALTER TABLE\s+\w+\s+ADD COLUMN\s+\w+[^;]*;", "", sql,
                                       count=1, flags=re.IGNORECASE)
                    # The interrupted migration may also have completed its
                    # follow-up index before the process died.
                    index_match = re.search(r"CREATE INDEX\s+(\w+)", remaining, re.IGNORECASE)
                    if index_match and conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index_match.group(1),)
                    ).fetchone():
                        remaining = re.sub(r"CREATE INDEX\s+\w+[^;]*;", "", remaining,
                                           count=1, flags=re.IGNORECASE)
                    conn.executescript(f"BEGIN;\n{remaining}\nCOMMIT;")
                else:
                    raise
            elif not optional:
                raise
            else:
                status = "SKIPPED"
        conn.execute(
            "INSERT INTO schema_migrations(version, name, status, applied_at) VALUES (?,?,?,?)",
            (version, name, status, now_iso()),
        )
        applied.append(f"{version:04d}_{name} ({status})")
    return applied
