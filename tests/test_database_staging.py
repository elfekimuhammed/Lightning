from __future__ import annotations

import sqlite3

import pytest

from lightning.bootstrap import build
from lightning.database.connection import Database
from lightning.database.staging import stage_database

KEY = bytes(range(32))
OTHER_KEY = bytes(reversed(range(32)))


@pytest.mark.parametrize("source_key", [None, KEY])
def test_staged_import_or_recovery_preserves_source(tmp_path, source_key):
    source = tmp_path / "original.db"
    c = build(source, key=source_key)
    account = c.account_flows.open_account("Savings", "CASH", "2026-09-01", "321.09")
    expected = c.reporting.account_balance(account.id)
    c.db.close()
    original = source.read_bytes()
    staged = stage_database(source, tmp_path / "stage", destination_key=OTHER_KEY, source_key=source_key)
    assert staged.schema_version == 37
    assert source.read_bytes() == original
    assert staged.path.suffix == ".partial"
    restored = build(staged.path, key=OTHER_KEY)
    assert restored.reporting.account_balance(account.id) == expected
    restored.db.close()
    standard = sqlite3.connect(staged.path)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            standard.execute("SELECT * FROM accounts")
    finally:
        standard.close()


def test_plaintext_import_includes_committed_wal_rows(tmp_path):
    source = tmp_path / "original.db"
    c = build(source)
    c.db.execute("PRAGMA journal_mode=WAL")
    c.db.execute("PRAGMA wal_autocheckpoint=0")
    c.db.execute("INSERT INTO settings VALUES ('test_wal','committed','today')")
    original = source.read_bytes()
    wal = source.with_name(source.name + "-wal").read_bytes()
    staged = stage_database(source, tmp_path / "stage", destination_key=KEY)
    db = Database(staged.path, key=KEY, read_only=True)
    assert db.scalar("SELECT value FROM settings WHERE key='test_wal'") == "committed"
    assert source.read_bytes() == original
    assert source.with_name(source.name + "-wal").read_bytes() == wal
    db.close()
    c.db.close()


def test_staging_failure_preserves_source_and_cleans_own_output(tmp_path, monkeypatch):
    source = tmp_path / "original.db"
    c = build(source)
    c.db.close()
    original = source.read_bytes()
    from lightning.database import snapshot
    def fail(*args, **kwargs):
        raise ValueError("injected validation failure")
    monkeypatch.setattr(snapshot, "verify_connection", fail)
    with pytest.raises(ValueError, match="validation failure"):
        stage_database(source, tmp_path / "stage", destination_key=KEY)
    assert source.read_bytes() == original
    assert not list((tmp_path / "stage").iterdir())


def test_unrecognized_or_newer_source_rejected_without_output(tmp_path):
    source = tmp_path / "original.db"
    c = build(source)
    c.db.execute("INSERT INTO schema_migrations VALUES(9999,'future','APPLIED','today')")
    c.db.close()
    with pytest.raises(ValueError, match="newer or unknown"):
        stage_database(source, tmp_path / "stage", destination_key=KEY)
    assert not (tmp_path / "stage").exists()


def test_staging_does_not_delete_an_unowned_collision(tmp_path, monkeypatch):
    from lightning.database import staging
    source = tmp_path / "original.db"
    build(source).db.close()
    def collision(conn, target, **kwargs):
        target.write_bytes(b"belongs to another operation")
        raise FileExistsError(target)
    monkeypatch.setattr(staging, "export_snapshot", collision)
    with pytest.raises(FileExistsError):
        stage_database(source, tmp_path / "stage", destination_key=KEY)
    assert [p.read_bytes() for p in (tmp_path / "stage").iterdir()] == [b"belongs to another operation"]
