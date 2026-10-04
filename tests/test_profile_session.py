import json
import os
import sqlite3
from pathlib import Path

import pytest

from lightning.runtime.instance import InstanceAlreadyRunning, InstanceLock
from lightning.runtime.paths import discover_profiles
from lightning.runtime.session import ProfileError, ProfileSession, write_slot


PASSWORD = "a correct long passphrase"
NEW_PASSWORD = "another correct long passphrase"


def created(tmp_path):
    session = ProfileSession(tmp_path / "Documents" / "Lightning")
    pending = session.prepare("Home", PASSWORD, PASSWORD)
    session.confirm(True)
    return session, pending


def test_setup_is_explicit_and_encrypted_and_reopens(tmp_path):
    session = ProfileSession(tmp_path / "profiles")
    pending = session.prepare("Home", PASSWORD, PASSWORD)
    assert not session.root.exists()
    with pytest.raises(ProfileError, match="Save"):
        session.confirm(False)
    session.confirm(True)
    path = session.paths.db_path
    session.container.settings.set("test_marker", "private data")
    with pytest.raises(InstanceAlreadyRunning):
        InstanceLock(session.paths.lock_path).acquire()
    assert b"private data" not in path.read_bytes()
    with sqlite3.connect(path) as connection:
        with pytest.raises(sqlite3.DatabaseError):
            connection.execute("SELECT * FROM sqlite_master").fetchall()
    old_container = session.container
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        old_container.db.conn
    session.unlock(str(path), PASSWORD)
    assert session.container.settings.get("test_marker") == "private data"
    assert list(session.paths.backups_dir.glob("*.db"))
    session.close()


def test_recovery_preserves_database_and_rejects_wrong_key(tmp_path):
    session, pending = created(tmp_path)
    path, slot = session.paths.db_path, session.paths.keys_path
    session.close()
    before_db, before_slot = path.read_bytes(), slot.read_bytes()
    with pytest.raises(ProfileError):
        session.recover(str(path), "bad key", NEW_PASSWORD, NEW_PASSWORD)
    assert slot.read_bytes() == before_slot
    session.retry_at = 0
    session.recover(str(path), pending.recovery, NEW_PASSWORD, NEW_PASSWORD)
    assert path.read_bytes() == before_db
    assert slot.read_bytes() != before_slot
    with pytest.raises(ProfileError, match="incorrect"):
        session.unlock(str(path), PASSWORD)
    session.retry_at = 0
    session.unlock(str(path), NEW_PASSWORD)
    session.close()


def test_missing_slot_recovers_and_changes_password(tmp_path):
    session, pending = created(tmp_path)
    path, slot = session.paths.db_path, session.paths.keys_path
    session.close()
    slot.unlink()
    session.recover(str(path), pending.recovery, PASSWORD, PASSWORD)
    session.unlock(str(path), PASSWORD)
    session.change_password(PASSWORD, NEW_PASSWORD, NEW_PASSWORD)
    session.close()
    session.unlock(str(path), NEW_PASSWORD)
    session.close()


def test_profiles_stay_separate_and_do_not_overwrite(tmp_path):
    session, first = created(tmp_path)
    first_path = session.paths.db_path
    session.close()
    second = session.prepare("Home", NEW_PASSWORD, NEW_PASSWORD)
    session.confirm(True)
    assert first_path != session.paths.db_path
    assert len(discover_profiles(session.root)) == 2
    assert first.paths.profile.sequence == 1
    assert second.paths.profile.sequence == 2
    session.close()


def test_plaintext_and_backups_not_opened_as_live_profiles(tmp_path):
    source = tmp_path / "old.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE example (id)")
    before = source.read_bytes()
    session = ProfileSession(tmp_path / "profiles")
    with pytest.raises(ProfileError, match="legacy"):
        session.unlock(str(source), PASSWORD)
    assert source.read_bytes() == before
    assert not (tmp_path / ".old.db.lightning").exists()
    session, _ = created(tmp_path)
    snapshot = session.container.backup_now()
    session.close()
    with pytest.raises(ProfileError, match="backup"):
        session.unlock(str(snapshot), PASSWORD)


def test_pending_expires_and_slot_publication_is_non_destructive(tmp_path):
    session = ProfileSession(tmp_path / "profiles")
    pending = session.prepare("Home", PASSWORD, PASSWORD)
    pending.expires = 0
    with pytest.raises(ProfileError, match="expired"):
        session.confirm(True)
    assert not session.root.exists()
    slot = tmp_path / "keys.json"
    write_slot(slot, {"old": True})
    with pytest.raises(FileExistsError):
        write_slot(slot, {"new": True})
    assert json.loads(slot.read_text()) == {"old": True}
    assert not list(tmp_path.glob("*.partial"))


def test_failed_setup_is_not_discovered_or_reused(tmp_path, monkeypatch):
    from lightning.runtime import session as module
    session = ProfileSession(tmp_path / "profiles")
    pending = session.prepare("Home", PASSWORD, PASSWORD)
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic disk failure")
    monkeypatch.setattr(module, "build", fail)
    with pytest.raises(RuntimeError):
        session.confirm(True)
    assert not discover_profiles(session.root)
    assert pending.paths.keys_path.exists()
    with InstanceLock(pending.paths.lock_path):
        pass
    next_pending = session.prepare("Home", PASSWORD, PASSWORD)
    assert next_pending.paths.profile.sequence == 2


def test_restore_backup_keeps_source_and_pre_restore_copy_and_reopens(tmp_path):
    session, _ = created(tmp_path)
    live = session.paths.db_path
    backups_dir = session.paths.backups_dir
    slot = session.paths.keys_path
    session.container.settings.set("restore_marker", "old checkpoint")
    selected = session.container.backup_now()
    source_before = selected.read_bytes()
    session.container.settings.set("restore_marker", "current live")
    live_before = live.read_bytes()
    slot_before = slot.read_bytes()
    session.close()

    session.restore_backup(str(live), str(selected), PASSWORD)
    assert session.container is None
    assert session.lock is None
    assert selected.read_bytes() == source_before
    preserved = list(backups_dir.glob(".lightning-restore-source-*.db"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == source_before
    assert slot.read_bytes() == slot_before
    assert live.read_bytes() != live_before
    assert len(list(backups_dir.glob("*_upgrade_*.db"))) >= 1
    session.unlock(str(live), PASSWORD)
    assert session.container.settings.get("restore_marker") == "old checkpoint"
    from lightning.database.backup import backup
    backup(session.container.db, backups_dir, keep=1)
    assert not selected.exists()
    assert preserved[0].read_bytes() == source_before
    session.close()
    fresh = ProfileSession(session.root)
    fresh.unlock(str(live), PASSWORD)
    assert fresh.container.settings.get("restore_marker") == "old checkpoint"
    fresh.close()


def test_completed_restore_blocks_if_previous_checkpoint_is_missing(tmp_path):
    session, _ = created(tmp_path)
    live, data_dir = session.paths.db_path, session.paths.data_dir
    selected = session.container.backup_now()
    session.close()
    session.restore_backup(str(live), str(selected), PASSWORD)
    previous = next(data_dir.glob(".lightning-restore-*.previous.db"))
    previous.unlink()
    fresh = ProfileSession(session.root)
    with pytest.raises(ProfileError, match="pre-restore checkpoint"):
        fresh.unlock(str(live), PASSWORD)


def test_completed_restore_blocks_if_previous_checkpoint_is_corrupt(tmp_path):
    session, _ = created(tmp_path)
    live, data_dir = session.paths.db_path, session.paths.data_dir
    selected = session.container.backup_now()
    session.close()
    session.restore_backup(str(live), str(selected), PASSWORD)
    previous = next(data_dir.glob(".lightning-restore-*.previous.db"))
    with previous.open("r+b") as handle:
        handle.seek(128)
        byte = handle.read(1)
        handle.seek(128)
        handle.write(bytes([byte[0] ^ 0x40]))
    fresh = ProfileSession(session.root)
    with pytest.raises(ProfileError, match="does not match its journal"):
        fresh.unlock(str(live), PASSWORD)


@pytest.mark.parametrize("evidence", [
    "source_copy_missing", "source_copy_corrupt", "pre_restore_missing",
    "pre_restore_corrupt", "source_backup_corrupt", "malformed_manifest",
])
def test_completed_restore_blocks_when_manifest_evidence_is_missing_or_corrupt(tmp_path, evidence):
    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    selected = session.container.backup_now()
    session.close()
    session.restore_backup(str(live), str(selected), PASSWORD)
    manifest = next(paths.data_dir.glob(".lightning-restore-*.state"))
    if evidence.startswith("source_copy"):
        protected = next(paths.backups_dir.glob(".lightning-restore-source-*.db"))
        if evidence.endswith("missing"):
            protected.unlink()
        else:
            with protected.open("r+b") as handle:
                handle.seek(128)
                byte = handle.read(1)
                handle.seek(128)
                handle.write(bytes([byte[0] ^ 0x20]))
    elif evidence.startswith("pre_restore"):
        pre_restore = next(paths.backups_dir.glob("*_upgrade_*.db"))
        if evidence.endswith("missing"):
            pre_restore.unlink()
        else:
            with pre_restore.open("r+b") as handle:
                handle.seek(128)
                byte = handle.read(1)
                handle.seek(128)
                handle.write(bytes([byte[0] ^ 0x20]))
    elif evidence == "source_backup_corrupt":
        with selected.open("r+b") as handle:
            handle.seek(128)
            byte = handle.read(1)
            handle.seek(128)
            handle.write(bytes([byte[0] ^ 0x20]))
    else:
        manifest.write_bytes(b'{"schema_version":1,"state":"COMPLETE"}')
    fresh = ProfileSession(session.root)
    with pytest.raises(ProfileError, match="manifest|source copy|retained restore backup"):
        fresh.unlock(str(live), PASSWORD)


def test_restore_manifest_rejects_unknown_schema_and_noncanonical_names():
    from dataclasses import replace
    from lightning.runtime.restore import RestoreManifest

    digest = "a" * 64
    manifest = RestoreManifest(
        state="PENDING", operation_id="1" * 32, profile_id="profile-1",
        live_name="profile.db", old_checkpoint_id="restore-base-" + digest[:32],
        old_sha256=digest, candidate_name="candidate.partial",
        new_checkpoint_id="restore-" + "2" * 32, candidate_sha256="b" * 64,
        previous_name=f".lightning-restore-{'1' * 32}.previous.db",
        source_backup_name="profile_backup_2030-01-01_001_1234abcd.db",
        source_sha256="c" * 64,
        source_copy_name=f".lightning-restore-source-{'1' * 32}.db",
        source_copy_sha256="c" * 64,
        pre_restore_name="profile_upgrade_2030-01-01_001_1234abcd.db",
        pre_restore_sha256="d" * 64,
    )
    record = json.loads(manifest.to_bytes())
    record["schema_version"] = 2
    with pytest.raises(ValueError, match="Unsupported"):
        RestoreManifest.from_bytes(json.dumps(record).encode())
    with pytest.raises(ValueError, match="sibling basenames"):
        replace(manifest, candidate_name="../candidate.partial")


def test_unlock_verifies_retained_encrypted_copies_with_profile_key(tmp_path, monkeypatch):
    from lightning.runtime.restore import EncryptedBackupRestorer

    session, _ = created(tmp_path)
    live = session.paths.db_path
    selected = session.container.backup_now()
    session.close()
    session.restore_backup(str(live), str(selected), PASSWORD)

    original_verify = EncryptedBackupRestorer._verify_file

    def refuse_protected_source(cls, path, key):
        if path.name.startswith(".lightning-restore-source-"):
            raise ValueError("injected encrypted-copy verification failure")
        return original_verify(path, key)

    monkeypatch.setattr(EncryptedBackupRestorer, "_verify_file",
                        classmethod(refuse_protected_source))
    with pytest.raises(ProfileError, match="retained restore backup"):
        ProfileSession(session.root).unlock(str(live), PASSWORD)


def test_restore_completed_marker_without_journal_blocks_unlock(tmp_path):
    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    session.container.settings.set("restore_marker", "before")
    selected = session.container.backup_now()
    session.container.settings.set("restore_marker", "after")
    session.close()
    session.restore_backup(str(live), str(selected), PASSWORD)
    for journal in paths.data_dir.glob(".lightning-restore-*.sqlite"):
        journal.unlink()
    fresh = ProfileSession(session.root)
    with pytest.raises(ProfileError, match="manifest has no complete matching journal"):
        fresh.unlock(str(live), PASSWORD)


@pytest.mark.parametrize("damage", ["wrong_key", "corrupt", "newer_schema"])
def test_restore_rejects_unusable_backup_without_changing_live_or_source(tmp_path, damage):
    from lightning.database.connection import Database
    from lightning.database.staging import stage_database

    session, pending = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    session.container.settings.set("restore_marker", "keep current")
    session.close()
    if damage == "wrong_key":
        # Produce a structurally valid ciphertext backup encrypted under a
        # different key, then give it an exact in-profile backup filename.
        staged = stage_database(live, paths.data_dir, destination_key=b"z" * 32,
                                source_key=pending.key)
        candidate = staged.path
    else:
        staged = stage_database(live, paths.data_dir, destination_key=pending.key,
                                source_key=pending.key)
        candidate = staged.path
        if damage == "corrupt":
            with candidate.open("r+b") as handle:
                handle.seek(128)
                value = handle.read(1)
                handle.seek(128)
                handle.write(bytes([value[0] ^ 0x80]))
        else:
            db = Database(candidate, key=pending.key)
            try:
                db.execute("UPDATE schema_migrations SET version=999 WHERE version=(SELECT MAX(version) FROM schema_migrations)")
            finally:
                db.close()
    backup_path = paths.backups_dir / f"{live.stem}_backup_2030-01-01_999_1234abcd.db"
    os.replace(candidate, backup_path)
    source_before, live_before, slot_before = backup_path.read_bytes(), live.read_bytes(), paths.keys_path.read_bytes()
    with pytest.raises(ProfileError, match="damaged|another key|newer"):
        session.restore_backup(str(live), str(backup_path), PASSWORD)
    assert backup_path.read_bytes() == source_before
    assert live.read_bytes() == live_before
    assert paths.keys_path.read_bytes() == slot_before
    with InstanceLock(paths.lock_path):
        pass


def test_restore_rejects_live_sidecars_without_touching_any_database(tmp_path):
    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    selected = session.container.backup_now()
    selected_before, live_before = selected.read_bytes(), live.read_bytes()
    session.close()
    sidecar = Path(str(live) + "-wal")
    sidecar.write_bytes(b"uncheckpointed evidence")
    with pytest.raises(ProfileError, match="sidecars"):
        session.restore_backup(str(live), str(selected), PASSWORD)
    assert selected.read_bytes() == selected_before
    assert live.read_bytes() == live_before
    assert sidecar.read_bytes() == b"uncheckpointed evidence"
    sidecar.unlink()


def test_restore_rejects_backup_sidecars_and_preserves_both_files(tmp_path):
    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    selected = session.container.backup_now()
    source_before, live_before = selected.read_bytes(), live.read_bytes()
    session.close()
    sidecar = Path(str(selected) + "-journal")
    sidecar.write_bytes(b"backup journal evidence")
    with pytest.raises(ProfileError, match="sidecars"):
        session.restore_backup(str(live), str(selected), PASSWORD)
    assert selected.read_bytes() == source_before
    assert live.read_bytes() == live_before
    assert sidecar.read_bytes() == b"backup journal evidence"
    sidecar.unlink()


def test_interrupted_restore_marker_blocks_fresh_unlock(tmp_path, monkeypatch):
    from lightning.database.promotion import CandidatePromotionService, PromotionBlocked

    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    session.container.settings.set("restore_marker", "current")
    selected = session.container.backup_now()
    session.close()

    def fail_after_prepare(self, **kwargs):
        raise PromotionBlocked("injected publication failure")

    monkeypatch.setattr(CandidatePromotionService, "promote", fail_after_prepare)
    with pytest.raises(ProfileError, match="repair|failed safely"):
        session.restore_backup(str(live), str(selected), PASSWORD)
    # A missing journal cannot make an interrupted operation look standalone.
    for journal in paths.data_dir.glob(".lightning-restore-*.sqlite"):
        journal.unlink()
    fresh = ProfileSession(session.root)
    with pytest.raises(ProfileError, match="interrupted restore"):
        fresh.unlock(str(live), PASSWORD)
    assert not fresh.container


@pytest.mark.parametrize("boundary", ["P1", "P2", "P3", "P4"])
def test_resume_interrupted_restore_advances_durable_phases(tmp_path, monkeypatch, boundary):
    from lightning.database.promotion import PromotionPhase, SqlitePromotionJournalStore
    from lightning.runtime.restore import EncryptedBackupRestorer

    session, _ = created(tmp_path)
    live, paths = session.paths.db_path, session.paths
    session.container.settings.set("restore_marker", "current")
    selected = session.container.backup_now()
    session.close()

    def inject_once(method, predicate=lambda *args, **kwargs: True):
        original = getattr(SqlitePromotionJournalStore, method)
        tripped = {"value": False}

        def wrapper(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            if not tripped["value"] and predicate(*args, **kwargs):
                tripped["value"] = True
                raise OSError(f"injected {boundary} interruption")
            return result

        monkeypatch.setattr(SqlitePromotionJournalStore, method, wrapper)
        return tripped

    if boundary == "P1":
        inject_once("prepare")
    elif boundary == "P2":
        inject_once("advance", lambda _old, new: new.phase is PromotionPhase.PREVIOUS_PROTECTED)
    elif boundary == "P3":
        if os.name == "nt":
            from lightning.database.promotion_windows import WindowsPromotionFileOps as FileOps
        else:
            from lightning.database.promotion import PosixPromotionFileOps as FileOps
        original = FileOps.atomic_replace
        tripped = {"value": False}

        def replace_then_fail(self, source, destination):
            result = original(self, source, destination)
            if not tripped["value"]:
                tripped["value"] = True
                raise OSError("injected P3 interruption")
            return result

        monkeypatch.setattr(FileOps, "atomic_replace", replace_then_fail)
    else:
        inject_once("commit_authority")

    with pytest.raises(ProfileError):
        session.restore_backup(str(live), str(selected), PASSWORD)
    assert session.container is None and session.lock is None
    # The interruption hook is one-shot; recovery uses the durable journal and
    # verifies encrypted candidate/previous files before advancing further.
    if boundary == "P3":
        monkeypatch.setattr(FileOps, "atomic_replace", original)
    session.retry_at = 0.0
    EncryptedBackupRestorer(session).resume_interrupted_restore(str(live), PASSWORD)
    assert session.container is None and session.lock is None
    assert len(list(paths.data_dir.glob(".lightning-restore-*.state"))) == 1
    session.unlock(str(live), PASSWORD)
    assert session.container.settings.get("restore_marker") == "current"
    session.close()
