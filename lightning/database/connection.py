"""SQLite connection handling.

- One connection per thread, autocommit off by default (explicit transactions only).
- ``with db.transaction():`` groups work atomically; nested calls become savepoints,
  so a workflow can call several services and still commit or roll back as one unit.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: str | Path, *, key: bytes | None = None,
                 read_only: bool = False):
        if key is not None and (not isinstance(key, bytes) or len(key) != 32):
            raise ValueError("The database key must be exactly 32 bytes")
        self.path = str(path)
        self._local = threading.local()
        self.encrypted = key is not None
        self.read_only = read_only
        self._key = bytearray(key) if key is not None else None
        self._owner = threading.current_thread() if self.encrypted else None
        self._closed = False
        self.driver = sqlite3
        if self.encrypted:
            # A missing cipher driver is an error, never a plaintext fallback.
            from sqlcipher3 import dbapi2
            self.driver = dbapi2
        self.OperationalError = self.driver.OperationalError
        self.IntegrityError = self.driver.IntegrityError

    def _check_owner(self) -> None:
        if self.encrypted:
            if self._closed:
                raise RuntimeError("Encrypted database has been closed")
            if self._owner is not None and self._owner is not threading.current_thread():
                raise RuntimeError("Encrypted database must stay on its owning thread")

    # -- connections -------------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        self._check_owner()
        conn = getattr(self._local, "conn", None)
        if conn is None:
            if self.encrypted:
                self._owner = threading.current_thread()
            if self.read_only:
                if self.path == ":memory:":
                    raise ValueError("Read-only databases need a file")
                target = Path(self.path).resolve().as_uri() + "?mode=ro"
            else:
                target = self.path
                if self.path != ":memory:":
                    Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            conn = self.driver.connect(target, uri=self.read_only, isolation_level=None)
            try:
                if self.encrypted:
                    conn.execute("PRAGMA cipher_log_level = NONE")
                    conn.execute(f'PRAGMA key = "x\'{self._key.hex()}\'"')
                    if not conn.execute("PRAGMA cipher_version").fetchone():
                        raise RuntimeError("SQLCipher is unavailable")
                    # Owner decision 2026-10-03: off. Wiping every freed allocation made ledger reads
                    # about 3x slower; SQLCipher still wipes its key material, and Python and the
                    # window keep unwiped copies of the same data anyway (Architecture, threat model).
                    conn.execute("PRAGMA cipher_memory_security = OFF")
                # Forces wrong-key/corrupt-file rejection before migrations/seed.
                conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
                conn.row_factory = self.driver.Row
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA busy_timeout = 5000")
            except BaseException:
                conn.close()
                raise
            self._local.conn = conn
            self._local.depth = 0
        return conn

    def copy_key(self) -> bytes:
        """The data key, to reopen this same file in another session role without asking for the password
        again (multiple devices, task 06). Owning thread only; close() still wipes this object's copy."""
        self._check_owner()
        if self._key is None:
            raise ValueError("This database has no key")
        return bytes(self._key)

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self.encrypted and self._closed:
            return
        self._check_owner()
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
        if self._key is not None:
            # Best effort only: Python/SQLite may have made other memory copies.
            self._key[:] = bytes(len(self._key))
            self._closed = True

    # -- transactions ------------------------------------------------------
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.conn
        depth = self._local.depth
        savepoint = f"sp_{depth}"
        conn.execute("BEGIN IMMEDIATE" if depth == 0 else f"SAVEPOINT {savepoint}")
        self._local.depth = depth + 1
        try:
            yield conn
        except BaseException:
            self._local.depth = depth
            if depth == 0:
                conn.execute("ROLLBACK")
            else:
                conn.execute(f"ROLLBACK TO {savepoint}")
                conn.execute(f"RELEASE {savepoint}")
            raise
        else:
            self._local.depth = depth
            try:
                conn.execute("COMMIT" if depth == 0 else f"RELEASE {savepoint}")
            except BaseException:
                if conn.in_transaction:
                    if depth == 0:
                        conn.execute("ROLLBACK")
                    else:
                        conn.execute(f"ROLLBACK TO {savepoint}")
                        conn.execute(f"RELEASE {savepoint}")
                raise

    # -- helpers -----------------------------------------------------------
    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def one(self, sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: tuple | dict = ()):
        row = self.conn.execute(sql, params).fetchone()
        return None if row is None else row[0]

    def has_table(self, name: str) -> bool:
        return (
            self.scalar("SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table','view')", (name,))
            is not None
        )
