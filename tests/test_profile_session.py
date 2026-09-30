import json
import sqlite3

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
