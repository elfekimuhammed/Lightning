"""Baseline writer inventory and two-node gate contract for multi-device work.

Task 01 of docs/proposals/multiple_devices.md. This is intentionally a small
deterministic fixture: Task 06 can replace the direct read-only connection with
the role-aware session API while keeping the same one-writer assertions.
"""

from __future__ import annotations

import shutil

import pytest

from lightning.bootstrap import build


# Keep this inventory tied to the existing entry points. Anything adding a
# write path should add it here and route it through the profile operation gate.
WRITE_LIFECYCLE_INVENTORY = {
    "profile creation / unlock": (
        "lightning/runtime/session.py:ProfileSession.confirm, unlock",
        "lightning/bootstrap.py:build",
        "backup, inspect_schema, migrate, seed, migrate_legacy_ownership",
    ),
    "migrations and seed": (
        "lightning/database/migrator.py:migrate",
        "lightning/database/seed.py:seed",
        "lightning/ownership_migration.py:migrate_legacy_ownership",
    ),
    "prices and revaluations": (
        "lightning/assets/service.py:AssetService.set_price",
        "lightning/assets/market_data.py:refresh_market_prices, refresh_reevaluation_prices",
        "lightning/reevaluations.py:ReevaluationService.record_manual_price",
    ),
    "imports": (
        "lightning/bank_imports.py:BankImportService stage/review/post paths",
        "lightning/database/staging.py:stage_database (candidate file lifecycle)",
    ),
    "settings and finance services": (
        "lightning/database/settings.py:SettingsStore.set",
        "service/repository writes through Database.execute / transaction",
    ),
    "backups": (
        "lightning/bootstrap.py:Container.backup_now",
        "lightning/database/backup.py:backup (database snapshot to a new file)",
    ),
    "shutdown": (
        "lightning/runtime/session.py:ProfileSession.close",
        "lightning/database/connection.py:Database.close",
        "close DB successfully before releasing InstanceLock; no implicit commit/backup",
    ),
}

# Contract for the eventual shared profile operation gate: acquire before any
# mutation-capable lifecycle action; serialize gate changes; reject new work
# before draining active DB transactions; wait for background writers; then
# close/reopen the connection in the selected role. A rejected operation must
# leave rows and authority state unchanged. Shutdown closes successfully before
# releasing the profile lock. The gate is process-local coordination, so durable
# authority state and the OS profile lock remain separate requirements.
OPERATION_GATE_REQUIREMENTS = (
    "all mutating paths listed above use one per-profile gate",
    "read-only role opens a SQLite read-only connection before bootstrap writes",
    "close gate to new writes, drain in-flight transactions, then publish role change",
    "gate transitions and role changes are serialized on the DB-owning thread",
    "denial leaves financial rows and durable authority state unchanged",
    "background price jobs and shutdown obey the same gate and profile lock",
)


@pytest.fixture
def two_nodes(tmp_path):
    """Two deterministic node databases, initially identical and independent."""
    home_path = tmp_path / "home" / "lightning.db"
    home_path.parent.mkdir()
    home = build(home_path)
    home.db.close()

    borrower_path = tmp_path / "borrower" / "lightning.db"
    borrower_path.parent.mkdir()
    shutil.copyfile(home_path, borrower_path)

    # Reopen home writable and the borrower through the reader build (task 06a): SQLite's actual
    # read-only mode, with no backup, migration or seed on open.
    home = build(home_path)
    borrower = build(borrower_path, read_only=True).db
    try:
        yield home, borrower
    finally:
        borrower.close()
        home.db.close()


def test_inventory_covers_required_lifecycle_paths():
    required = {
        "profile creation / unlock", "migrations and seed", "prices and revaluations",
        "imports", "settings and finance services", "backups", "shutdown",
    }
    assert set(WRITE_LIFECYCLE_INVENTORY) == required
    assert all(WRITE_LIFECYCLE_INVENTORY.values())
    assert len(OPERATION_GATE_REQUIREMENTS) == 6


def test_two_node_fixture_has_one_writable_node(two_nodes):
    home, borrower = two_nodes

    # Current home path remains writable. The borrower must be opened read-only;
    # SQLite itself is the first enforcement layer, before service-level gates.
    home.db.execute(
        "INSERT INTO settings(key, value, updated_at) VALUES ('sync_gate_probe', 'home', '2026-10-04')"
    )
    assert home.db.scalar("SELECT value FROM settings WHERE key='sync_gate_probe'") == "home"
    assert borrower.conn.execute("SELECT value FROM settings WHERE key='sync_gate_probe'").fetchone() is None
    with pytest.raises(borrower.OperationalError):
        borrower.conn.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES ('sync_gate_probe', 'borrower', '2026-10-04')"
        )
