from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import contextmanager

import pytest

from lightning.bootstrap import build
from lightning.database.connection import Database
from lightning.database.migrator import inspect_schema
from lightning.database.promotion import (
    CandidatePromotionService, PosixPromotionFileOps,
    PromotionBlocked,
    PromotionPhase,
    SqlitePromotionJournalStore,
)
from lightning.database.promotion_windows import WindowsPromotionFileOps
from lightning.database.snapshot import verify_connection
from lightning.database.staging import stage_database


KEY = bytes(range(32))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MemoryFiles:
    """Deterministic file-operation fake with controllable crash boundaries."""

    def __init__(self, files):
        self.files = dict(files)
        self.fail_copy = False
        self.fail_replace_before = False
        self.fail_replace_after = False

    def sha256(self, name):
        value = self.files.get(name)
        return None if value is None else digest(value)

    def copy_exclusive(self, source, destination):
        if self.fail_copy:
            raise OSError("injected full disk before previous-copy publication")
        if destination in self.files:
            raise FileExistsError(destination)
        self.files[destination] = bytes(self.files[source])

    def atomic_replace(self, source, destination):
        if self.fail_replace_before:
            raise OSError("injected replacement failure before rename")
        self.files[destination] = self.files.pop(source)
        if self.fail_replace_after:
            raise OSError("injected flush failure after rename")

    def unlink(self, name):
        del self.files[name]


class Gate:
    """Test gate proves the service never calls activation outside quiescence."""

    def __init__(self):
        self.quiesced = False

    def __enter__(self):
        assert not self.quiesced
        self.quiesced = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.quiesced = False


@pytest.fixture
def harness(tmp_path):
    old = b"encrypted old database fixture"
    new = b"encrypted candidate database fixture"
    files = MemoryFiles({"profile.db": old, "candidate.partial": new})
    gate = Gate()
    store = SqlitePromotionJournalStore(tmp_path / "device-control" / "promotion.sqlite")
    store.initialize_accepted("home-1", digest(old))
    service = CandidatePromotionService(files, store)
    verified = []
    activated = []

    def verify(name):
        # The real caller supplies SQLCipher + schema + identity checks. This
        # fixture confirms only the expected dummy bytes and call ordering.
        assert files.files[name] in (old, new)
        verified.append(name)

    def activate(checkpoint_id, live_name):
        assert gate.quiesced
        current = store.read_state().accepted
        assert current is not None
        assert files.sha256(live_name) == current.sha256
        activated.append((checkpoint_id, live_name))

    args = dict(
        operation_id="operation-1",
        old_checkpoint_id="home-1",
        new_checkpoint_id="home-2",
        live_name="profile.db",
        candidate_name="candidate.partial",
        previous_name="previous.db",
        operation_gate=gate,
        verify_database=verify,
        activate=activate,
    )
    return files, store, service, gate, verified, activated, args, old, new


def test_success_publishes_new_file_then_accepts_and_activates(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    result = service.promote(**args)

    state = store.read_state()
    assert result.checkpoint_id == "home-2"
    assert result.sha256 == digest(new)
    assert result.phase is PromotionPhase.ACTIVATED
    assert state.accepted.checkpoint_id == "home-2"
    assert state.journal.phase is PromotionPhase.ACTIVATED
    assert files.files["profile.db"] == new
    assert files.files["previous.db"] == old
    assert "candidate.partial" not in files.files
    assert activated == [("home-2", "profile.db")]
    assert not gate.quiesced
    assert "previous.db" in verified and "profile.db" in verified


def test_invalid_staged_candidate_stays_p0_and_preserves_both_copies(harness):
    files, store, service, gate, verified, activated, args, old, new = harness

    def reject_candidate(name):
        if name == "candidate.partial":
            raise ValueError("wrong key or corrupt candidate")
        verified.append(name)

    with pytest.raises(ValueError, match="wrong key"):
        service.promote(**{**args, "verify_database": reject_candidate})
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    assert store.read_state().journal is None
    assert store.read_state().accepted.sha256 == digest(old)
    assert activated == []


def test_p1_copy_failure_keeps_old_live_and_candidate_then_restart_completes(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.fail_copy = True
    with pytest.raises(OSError, match="full disk"):
        service.promote(**args)
    assert store.read_state().journal.phase is PromotionPhase.PREPARED
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    assert "previous.db" not in files.files
    files.fail_copy = False

    result = service.recover(
        live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
        activate=args["activate"],
    )
    assert result.phase is PromotionPhase.ACTIVATED
    assert files.files["previous.db"] == old
    assert files.files["profile.db"] == new
    assert activated == [("home-2", "profile.db")]


def test_p2_commit_response_loss_reuses_durable_previous_checkpoint(harness, monkeypatch):
    files, store, service, gate, verified, activated, args, old, new = harness
    original_advance = store.advance

    def commit_then_lose_response(expected, updated):
        result = original_advance(expected, updated)
        if updated.phase is PromotionPhase.PREVIOUS_PROTECTED:
            raise RuntimeError("simulated lost P2 commit response")
        return result

    monkeypatch.setattr(store, "advance", commit_then_lose_response)
    with pytest.raises(RuntimeError, match="lost P2"):
        service.promote(**args)
    assert store.read_state().journal.phase is PromotionPhase.PREVIOUS_PROTECTED
    assert files.files["previous.db"] == old
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    monkeypatch.setattr(store, "advance", original_advance)

    result = service.recover(
        live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
        activate=args["activate"],
    )
    assert result.phase is PromotionPhase.ACTIVATED
    assert files.files["previous.db"] == old


def test_p2_replace_failure_retains_live_candidate_and_previous(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.fail_replace_before = True
    with pytest.raises(OSError, match="before rename"):
        service.promote(**args)
    state = store.read_state()
    assert state.journal.phase is PromotionPhase.PREVIOUS_PROTECTED
    assert state.accepted.sha256 == digest(old)
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    assert files.files["previous.db"] == old
    assert activated == []


def test_p2_crash_after_replace_is_inferred_and_records_p3(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.fail_replace_after = True
    with pytest.raises(OSError, match="after rename"):
        service.promote(**args)
    state = store.read_state()
    assert state.journal.phase is PromotionPhase.PREVIOUS_PROTECTED
    assert state.accepted.sha256 == digest(old)
    assert files.files["profile.db"] == new
    assert files.files["previous.db"] == old


def test_p3_is_durable_before_authority_commit_and_recovery_finishes(harness, monkeypatch):
    files, store, service, gate, verified, activated, args, old, new = harness
    commit = store.commit_authority

    def crash_before_p4(expected):
        raise RuntimeError("simulated crash at durable P3")

    monkeypatch.setattr(store, "commit_authority", crash_before_p4)
    with pytest.raises(RuntimeError, match="durable P3"):
        service.promote(**args)
    state = store.read_state()
    assert state.journal.phase is PromotionPhase.FILE_PUBLISHED
    assert state.accepted.sha256 == digest(old)
    assert files.files["profile.db"] == new
    assert files.files["previous.db"] == old
    monkeypatch.setattr(store, "commit_authority", commit)

    result = service.recover(
        live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
        activate=args["activate"],
    )
    assert result.phase is PromotionPhase.ACTIVATED
    assert store.read_state().accepted.sha256 == digest(new)
    assert "candidate.partial" not in files.files


def test_p3_record_with_rolled_back_rename_republishes_before_acceptance(harness, monkeypatch):
    files, store, service, gate, verified, activated, args, old, new = harness
    original_commit = store.commit_authority

    def stop_at_p3(expected):
        raise RuntimeError("stop at P3")

    monkeypatch.setattr(store, "commit_authority", stop_at_p3)
    with pytest.raises(RuntimeError, match="stop at P3"):
        service.promote(**args)
    assert store.read_state().journal.phase is PromotionPhase.FILE_PUBLISHED
    assert store.read_state().accepted.sha256 == digest(old)
    # Model a filesystem whose rename metadata was lost across power loss.
    files.files["candidate.partial"] = files.files["profile.db"]
    files.files["profile.db"] = old
    monkeypatch.setattr(store, "commit_authority", original_commit)

    result = service.recover(
        live_name="profile.db", operation_gate=gate,
        verify_database=args["verify_database"], activate=args["activate"],
    )
    assert result.phase is PromotionPhase.ACTIVATED
    assert files.files["profile.db"] == new
    assert files.files["previous.db"] == old
    assert store.read_state().accepted.sha256 == digest(new)


def test_p4_activation_error_keeps_new_authority_and_retries_activation(harness):
    files, store, service, gate, verified, activated, args, old, new = harness

    def fail_activation(checkpoint_id, live_name):
        assert gate.quiesced
        assert store.read_state().accepted.sha256 == digest(new)
        raise RuntimeError("simulated crash before P5")

    with pytest.raises(RuntimeError, match="before P5"):
        service.promote(**{**args, "activate": fail_activation})
    state = store.read_state()
    assert state.journal.phase is PromotionPhase.AUTHORITY_PUBLISHED
    assert state.accepted.checkpoint_id == "home-2"
    assert files.files["profile.db"] == new
    assert files.files["previous.db"] == old
    assert activated == []

    result = service.recover(
        live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
        activate=args["activate"],
    )
    assert result.phase is PromotionPhase.ACTIVATED
    assert activated == [("home-2", "profile.db")]


def test_p4_commit_response_loss_replays_accepted_authority(harness, monkeypatch):
    files, store, service, gate, verified, activated, args, old, new = harness
    original = store.commit_authority

    def commit_then_lose_reply(expected):
        original(expected)
        raise RuntimeError("P4 commit reply lost")

    monkeypatch.setattr(store, "commit_authority", commit_then_lose_reply)
    with pytest.raises(RuntimeError, match="reply lost"):
        service.promote(**args)
    assert store.read_state().journal.phase is PromotionPhase.AUTHORITY_PUBLISHED
    assert store.read_state().accepted.sha256 == digest(new)
    assert activated == []
    result = service.recover(live_name="profile.db", operation_gate=gate,
                             verify_database=args["verify_database"],
                             activate=args["activate"])
    assert result.phase is PromotionPhase.ACTIVATED
    assert activated == [("home-2", "profile.db")]


def test_ambiguous_restart_blocks_and_preserves_evidence(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.fail_replace_before = True
    with pytest.raises(OSError):
        service.promote(**args)
    files.fail_replace_before = False
    files.files["previous.db"] = b"wrong previous checkpoint"

    with pytest.raises(PromotionBlocked, match="journal|match|checkpoint"):
        service.recover(
            live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
            activate=args["activate"],
        )
    assert store.read_state().accepted.sha256 == digest(old)
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    assert files.files["previous.db"] == b"wrong previous checkpoint"
    assert activated == []


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_sidecars_block_publication_without_touching_copies(harness, suffix):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.files["profile.db" + suffix] = b"unresolved sqlite sidecar"
    with pytest.raises(PromotionBlocked, match="sidecar"):
        service.promote(**args)
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new
    assert store.read_state().accepted.sha256 == digest(old)
    assert store.read_state().journal is None
    assert activated == []


def test_no_journal_recovery_activates_only_accepted_live_file(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    result = service.recover(
        live_name="profile.db", operation_gate=gate, verify_database=args["verify_database"],
        activate=args["activate"],
    )
    assert result.operation_id is None
    assert result.checkpoint_id == "home-1"
    assert result.phase is None
    assert activated == [("home-1", "profile.db")]
    assert files.files["candidate.partial"] == new


def test_sqlite_control_store_reopens_with_atomic_accepted_journal_state(harness, tmp_path):
    files, store, service, gate, verified, activated, args, old, new = harness
    service.promote(**args)
    reopened = SqlitePromotionJournalStore(tmp_path / "device-control" / "promotion.sqlite")
    state = reopened.read_state()
    assert state.accepted.checkpoint_id == "home-2"
    assert state.accepted.sha256 == digest(new)
    assert state.journal.phase is PromotionPhase.ACTIVATED


def test_corrupt_control_journal_blocks_before_any_file_action(harness, tmp_path):
    files, store, service, gate, verified, activated, args, old, new = harness
    with sqlite3.connect(tmp_path / "device-control" / "promotion.sqlite") as conn:
        conn.execute("UPDATE promotion_control SET journal_json=? WHERE singleton=1",
                     ('{"operation_id":"one","operation_id":"two"}',))
    with pytest.raises(RuntimeError, match="corrupt"):
        service.recover(live_name="profile.db", operation_gate=gate,
                        verify_database=args["verify_database"], activate=args["activate"])
    assert files.files["profile.db"] == old
    assert activated == []


def test_operation_id_replay_is_idempotent_after_activation(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    service.promote(**args)
    replay = service.promote(**args)
    assert replay.checkpoint_id == "home-2"
    assert replay.phase is PromotionPhase.ACTIVATED
    assert activated == [("home-2", "profile.db"), ("home-2", "profile.db")]


def test_reused_operation_id_with_changed_names_is_blocked(harness):
    files, store, service, gate, verified, activated, args, old, new = harness
    files.fail_copy = True
    with pytest.raises(OSError):
        service.promote(**args)
    with pytest.raises(PromotionBlocked, match="reused"):
        service.promote(**{**args, "candidate_name": "other.partial"})
    assert files.files["profile.db"] == old
    assert files.files["candidate.partial"] == new


def test_real_encrypted_staging_and_publication_preserve_previous(tmp_path):
    live = tmp_path / "profile.db"
    current = build(live, key=KEY)
    first = current.account_flows.open_account("First", "CASH", "2026-09-01", "100")
    current.db.close()
    source = stage_database(live, tmp_path, destination_key=KEY, source_key=KEY).path
    source_bytes = source.read_bytes()
    candidate = stage_database(source, tmp_path, destination_key=KEY, source_key=KEY).path
    current = build(live, key=KEY)
    current.account_flows.open_account("Second", "CASH", "2026-09-02", "200")
    current.db.close()
    previous_bytes = live.read_bytes()

    store = SqlitePromotionJournalStore(tmp_path / "device-control" / "promotion.sqlite")
    store.initialize_accepted("current-checkpoint", digest(previous_bytes))
    adapter = (WindowsPromotionFileOps(tmp_path) if os.name == "nt"
               else PosixPromotionFileOps(tmp_path))

    def verify(name):
        db = Database(tmp_path / name, key=KEY, read_only=True)
        try:
            inspect_schema(db)
            verify_connection(db.conn, encrypted=True)
        finally:
            db.close()

    with adapter:
        service = CandidatePromotionService(adapter, store)
        result = service.promote(
            operation_id="restore-operation", old_checkpoint_id="current-checkpoint",
            new_checkpoint_id="restored-checkpoint", live_name=live.name,
            candidate_name=candidate.name, previous_name="previous.db",
            operation_gate=Gate(), verify_database=verify,
            activate=lambda checkpoint, name: None,
        )
    assert result.phase is PromotionPhase.ACTIVATED
    assert (tmp_path / "previous.db").read_bytes() == previous_bytes
    assert source.read_bytes() == source_bytes
    assert source_bytes != previous_bytes
    assert store.read_state().accepted.sha256 == digest(live.read_bytes())
    restored = Database(live, key=KEY, read_only=True)
    try:
        assert restored.scalar("SELECT count(*) FROM accounts") == 1
        assert restored.scalar("SELECT name FROM accounts WHERE id=?", (first.id,)) == "First"
    finally:
        restored.close()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX process-kill drill")
def test_process_kill_after_p3_recovers_real_files(tmp_path):
    old, new = b"old encrypted fixture", b"new encrypted fixture"
    (tmp_path / "live.db").write_bytes(old)
    (tmp_path / "candidate.db").write_bytes(new)
    store_path = tmp_path / "control.sqlite"
    store = SqlitePromotionJournalStore(store_path)
    store.initialize_accepted("old", digest(old))

    child = os.fork()
    if child == 0:
        try:
            child_store = SqlitePromotionJournalStore(store_path)

            def killed_at_p3(expected):
                os._exit(43)

            child_store.commit_authority = killed_at_p3
            with PosixPromotionFileOps(tmp_path) as files:
                CandidatePromotionService(files, child_store).promote(
                    operation_id="kill-p3", old_checkpoint_id="old",
                    new_checkpoint_id="new", live_name="live.db",
                    candidate_name="candidate.db", previous_name="previous.db",
                    operation_gate=Gate(), verify_database=lambda name: None,
                    activate=lambda checkpoint, name: None,
                )
        except BaseException:
            os._exit(44)
        os._exit(45)

    _, status = os.waitpid(child, 0)
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 43
    reopened = SqlitePromotionJournalStore(store_path)
    assert reopened.read_state().journal.phase is PromotionPhase.FILE_PUBLISHED
    assert reopened.read_state().accepted.sha256 == digest(old)
    with PosixPromotionFileOps(tmp_path) as files:
        result = CandidatePromotionService(files, reopened).recover(
            live_name="live.db", operation_gate=Gate(), verify_database=lambda name: None,
            activate=lambda checkpoint, name: None,
        )
    assert result.phase is PromotionPhase.ACTIVATED
    assert (tmp_path / "live.db").read_bytes() == new
    assert (tmp_path / "previous.db").read_bytes() == old
