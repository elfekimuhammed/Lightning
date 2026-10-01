from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from lightning.database.connection import Database
from lightning.database import migrator


def _manifest(monkeypatch, tmp_path, *resources):
    directory = tmp_path / "migrations"
    directory.mkdir()
    for filename, sql in resources:
        (directory / filename).write_text(sql, encoding="utf-8")
    monkeypatch.setattr(migrator, "MIGRATIONS_DIR", directory)
    return directory


def _objects(db):
    return {
        row[0]
        for row in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view','index','trigger')"
        )
    }


@pytest.mark.parametrize(
    ("resource", "message"),
    [
        ((), "No migration resources"),
        ((("oops.sql", "CREATE TABLE sample(id);"),), "Malformed migration filename"),
        ((("0001_comments.sql", "-- only a comment\n/* and another */"),), "empty"),
        ((("0001_incomplete.sql", "CREATE TABLE unfinished(id"),), "Incomplete SQL statement"),
        (
            (("0001_one.sql", "CREATE TABLE sample(id);"), ("0003_three.sql", "CREATE TABLE other(id);")),
            "version gaps",
        ),
        (
            (("0001_one.sql", "CREATE TABLE sample(id);"), ("0001_other.sql", "CREATE TABLE other(id);")),
            "Duplicate migration version",
        ),
        ((("0001_one.sql", "BEGIN; CREATE TABLE sample(id); COMMIT;"),), "Transaction control"),
    ],
)
def test_invalid_manifest_fails_without_database_writes(monkeypatch, tmp_path, resource, message):
    _manifest(monkeypatch, tmp_path, *resource)
    db = Database(":memory:")
    before = _objects(db)
    with pytest.raises((ValueError, FileNotFoundError), match=message):
        migrator.migrate(db)
    assert _objects(db) == before


def test_bundled_manifest_rejects_missing_final_resource_before_writes(monkeypatch, tmp_path):
    directory = _manifest(monkeypatch, tmp_path, ("0001_first.sql", "CREATE TABLE first(id);"))
    monkeypatch.setattr(migrator, "_BUNDLED_MIGRATIONS_DIR", directory)
    monkeypatch.setattr(migrator, "BUNDLED_LATEST_VERSION", 2)
    db = Database(":memory:")
    before = _objects(db)

    with pytest.raises(ValueError, match="expected 0002"):
        migrator.migrate(db)

    assert _objects(db) == before


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE created_by_migration(id INTEGER PRIMARY KEY);",
        "CREATE TABLE altered_by_migration(id INTEGER PRIMARY KEY);",
    ],
)
def test_ddl_and_version_record_roll_back_together_then_retry(monkeypatch, tmp_path, sql):
    resources = [("0001_probe.sql", sql)]
    if sql.startswith("CREATE TABLE altered"):
        resources.append(("0002_add_column.sql", "ALTER TABLE altered_by_migration ADD COLUMN extra TEXT;"))
    _manifest(monkeypatch, tmp_path, *resources)
    db = Database(":memory:")
    db.conn.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "status TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )

    if len(resources) == 1:
        failed_version = 1
        created_name = "created_by_migration"
        expected_column = None
    else:
        db.conn.execute("CREATE TABLE altered_by_migration(id INTEGER PRIMARY KEY)")
        db.conn.execute("INSERT INTO schema_migrations VALUES(1,'probe','APPLIED','old')")
        failed_version = 2
        created_name = "altered_by_migration"
        expected_column = "extra"
    db.conn.execute(
        f"CREATE TRIGGER reject_record BEFORE INSERT ON schema_migrations "
        f"WHEN NEW.version={failed_version} BEGIN SELECT RAISE(ABORT, 'injected record failure'); END"
    )

    with pytest.raises(sqlite3.IntegrityError, match="injected record failure"):
        migrator.migrate(db)

    if failed_version == 1:
        assert created_name not in _objects(db)
    else:
        columns = {row[1] for row in db.conn.execute(f"PRAGMA table_info({created_name})")}
        assert expected_column not in columns
    assert db.conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version=?", (failed_version,)
    ).fetchone() is None

    db.conn.execute("DROP TRIGGER reject_record")
    assert len(migrator.migrate(db)) == len(resources) - failed_version + 1
    assert db.conn.execute(
        "SELECT status FROM schema_migrations WHERE version=?", (failed_version,)
    ).fetchone()[0] == "APPLIED"
    if expected_column:
        assert expected_column in {row[1] for row in db.conn.execute(f"PRAGMA table_info({created_name})")}


def test_optional_fts_failure_rolls_back_ddl_before_recording_skip(monkeypatch, tmp_path):
    _manifest(
        monkeypatch,
        tmp_path,
        ("0001_optional_search.sql", "-- @optional\nCREATE TABLE transient_optional(id);\nCREATE VIRTUAL TABLE search USING fts5(body);"),
    )
    real_db = Database(":memory:")

    class ConnectionProxy:
        def execute(self, sql, *args):
            if "CREATE VIRTUAL TABLE" in sql:
                raise sqlite3.OperationalError("no such module: fts5")
            return real_db.conn.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(real_db.conn, name)

    class DatabaseProxy:
        OperationalError = sqlite3.OperationalError
        conn = ConnectionProxy()

        def transaction(self):
            return real_db.transaction()

    assert migrator.migrate(DatabaseProxy()) == ["0001_optional_search (SKIPPED)"]
    assert "transient_optional" not in _objects(real_db)
    assert tuple(real_db.conn.execute("SELECT name,status FROM schema_migrations").fetchone()) == (
        "optional_search", "SKIPPED"
    )


def test_optional_migration_does_not_hide_unrelated_operational_errors(monkeypatch, tmp_path):
    _manifest(
        monkeypatch,
        tmp_path,
        ("0001_optional_search.sql", "-- @optional\nCREATE TABLE transient_optional(id);\nCREATE VIRTUAL TABLE search USING fts5(body);"),
    )
    real_db = Database(":memory:")

    class ConnectionProxy:
        def execute(self, sql, *args):
            if "CREATE VIRTUAL TABLE" in sql:
                raise sqlite3.OperationalError("disk I/O error")
            return real_db.conn.execute(sql, *args)

    class DatabaseProxy:
        OperationalError = sqlite3.OperationalError
        conn = ConnectionProxy()

        def transaction(self):
            return real_db.transaction()

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        migrator.migrate(DatabaseProxy())
    assert "transient_optional" not in _objects(real_db)
    assert "schema_migrations" not in _objects(real_db)


@pytest.mark.parametrize("bad_row", [(99, "future", "APPLIED"), (1, "wrong_name", "APPLIED"), (1, "first", "BROKEN")])
def test_unsupported_stored_schema_fails_before_writes(monkeypatch, tmp_path, bad_row):
    _manifest(monkeypatch, tmp_path, ("0001_first.sql", "CREATE TABLE should_not_exist(id);"))
    db = Database(":memory:")
    db.conn.execute(
        "CREATE TABLE schema_migrations(version INTEGER, name TEXT, status TEXT, applied_at TEXT)"
    )
    db.conn.execute("INSERT INTO schema_migrations VALUES(?,?,?,'old')", bad_row)
    before = _objects(db)

    with pytest.raises(ValueError):
        migrator.migrate(db)

    assert _objects(db) == before
    assert db.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_inspection_is_read_only_and_reports_backup_requirement(monkeypatch, tmp_path):
    _manifest(monkeypatch, tmp_path, ("0001_first.sql", "CREATE TABLE first(id);"))
    db = Database(":memory:")
    inspection = migrator.inspect_schema(db)
    assert inspection.current_version == 0
    assert inspection.latest_version == 1
    assert inspection.pending == ("0001_first",)
    assert inspection.needs_backup
    assert migrator.pending_migrations(db) == inspection.pending
    assert "schema_migrations" not in _objects(db)


def test_sql_splitter_accepts_comments_after_final_statement(monkeypatch, tmp_path):
    _manifest(
        monkeypatch,
        tmp_path,
        ("0001_comments.sql", "CREATE TABLE after_comment(id);\n-- trailing line comment\n/* trailing block comment */\n"),
    )
    db = Database(":memory:")
    assert migrator.migrate(db) == ["0001_comments (APPLIED)"]
    assert "after_comment" in _objects(db)


def test_sqlcipher_migration_rolls_back_ddl_and_retries(monkeypatch, tmp_path):
    pytest.importorskip("sqlcipher3")
    _manifest(monkeypatch, tmp_path, ("0001_cipher_probe.sql", "CREATE TABLE cipher_probe(id);"))
    db = Database(tmp_path / "encrypted.db", key=bytes(range(32)))
    try:
        db.conn.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "status TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        db.conn.execute(
            "CREATE TRIGGER reject_record BEFORE INSERT ON schema_migrations "
            "BEGIN SELECT RAISE(ABORT, 'injected cipher record failure'); END"
        )
        with pytest.raises(db.IntegrityError, match="injected cipher record failure"):
            migrator.migrate(db)
        assert "cipher_probe" not in _objects(db)
        assert db.conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0

        db.conn.execute("DROP TRIGGER reject_record")
        assert migrator.migrate(db) == ["0001_cipher_probe (APPLIED)"]
        assert "cipher_probe" in _objects(db)
    finally:
        db.close()


def test_sqlcipher_process_exit_during_record_insert_rolls_back_ddl(monkeypatch, tmp_path):
    pytest.importorskip("sqlcipher3")
    directory = _manifest(
        monkeypatch,
        tmp_path,
        ("0001_crash_probe.sql", "CREATE TABLE crash_probe(id);"),
    )
    database_path = tmp_path / "crash-encrypted.db"
    repository = Path(__file__).resolve().parents[1]
    script = """
import os, sys
from pathlib import Path
from lightning.database.connection import Database
from lightning.database import migrator

database = Database(sys.argv[1], key=bytes(range(32)))
migrator.MIGRATIONS_DIR = Path(sys.argv[2])
real_connection = database.conn

class ConnectionProxy:
    def execute(self, sql, *args):
        if sql.lstrip().upper().startswith('INSERT INTO SCHEMA_MIGRATIONS'):
            os._exit(73)
        return real_connection.execute(sql, *args)
    def __getattr__(self, name):
        return getattr(real_connection, name)

class DatabaseProxy:
    conn = ConnectionProxy()
    OperationalError = database.OperationalError
    def transaction(self):
        return database.transaction()

migrator.migrate(DatabaseProxy())
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository) + os.pathsep + environment.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", script, str(database_path), str(directory)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 73, result.stderr

    db = Database(database_path, key=bytes(range(32)))
    try:
        assert "crash_probe" not in _objects(db)
        assert "schema_migrations" not in _objects(db)
    finally:
        db.close()
