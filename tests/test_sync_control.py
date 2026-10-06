"""Task 05b: the device-local control store keeps authority across restarts and joins promotion at P4."""
from __future__ import annotations

import contextlib
import hashlib
import sqlite3
import uuid

import pytest

from lightning.database.promotion import CandidatePromotionService, PosixPromotionFileOps, PromotionPhase
from lightning.sync.control import ControlCorrupt, ControlStore, Peer, blocks_restore
from lightning.sync.domain import BorrowActivated, BorrowRequest, Compatibility, ReturnBegin
from lightning.sync.state import BorrowerModel, HomeProtocolModel, HomeState, ProtocolError

COMPAT = Compatibility(1, 1, 45, 1, "0123456789abcdef", 1)


def new() -> str:
    return str(uuid.uuid4())


def make_home(folder, borrower):
    store = ControlStore(folder)
    store.create(HomeProtocolModel(profile_id=new(), home_id=new(), lineage_id=new(), checkpoint_id=new(),
                                   checkpoint_sha256="a" * 64, compatibility=COMPAT, paired_devices={borrower}))
    return store


def request_for(home: HomeProtocolModel, borrower: str) -> BorrowRequest:
    return BorrowRequest(new(), new(), home.profile_id, home.home_id, home.lineage_id, borrower,
                         home.checkpoint_id, home.checkpoint_sha256, COMPAT)


def test_changes_survive_a_new_store_object_and_refusals_change_nothing(tmp_path):
    borrower = new()
    store = make_home(tmp_path, borrower)
    request = request_for(store.read("home"), borrower)
    grant = store.home(lambda home: home.borrow(request, authenticated_peer=borrower))
    reopened = ControlStore(tmp_path)  # a restart
    assert reopened.read("home").state is HomeState.LENT
    assert reopened.home(lambda home: home.borrow(request, authenticated_peer=borrower)) == grant  # replay
    before = reopened.read("home").to_record()
    with pytest.raises(ProtocolError):
        reopened.home(lambda home: home.borrow(request_for(home, new()), authenticated_peer=new()))
    assert reopened.read("home").to_record() == before


def test_missing_wrong_role_or_damaged_record_blocks(tmp_path):
    with pytest.raises(ControlCorrupt):
        ControlStore(tmp_path / "empty").read("home")
    store = make_home(tmp_path / "home", new())
    with pytest.raises(ControlCorrupt):
        store.read("borrower")
    with pytest.raises(ControlCorrupt):
        store.create(store.read("home"))  # never replaced
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE authority SET record = '{\"version\": 1}'")
    with pytest.raises(ControlCorrupt):
        store.read("home")
    assert blocks_restore(tmp_path / "home")
    assert not blocks_restore(tmp_path / "none")


def test_peers_are_saved_updated_and_revoked(tmp_path):
    store = ControlStore(tmp_path)
    device = new()
    store.save_peer(Peer(device, "Office PC", "PEM", "", ""))
    store.save_peer(Peer(device, "Office PC", "PEM", "", "", revoked=True))
    assert store.peers() == [Peer(device, "Office PC", "PEM", "", "", revoked=True)]
    with pytest.raises(ValueError):
        store.save_peer(Peer("not-an-id", "x", "", "", ""))


def test_borrower_record(tmp_path):
    store = ControlStore(tmp_path)
    model = BorrowerModel(profile_id=new(), home_id=new(), lineage_id=new(), device_id=new())
    store.create(model)
    store.borrower(lambda pc: pc.prefetched(new(), "c" * 64))
    assert ControlStore(tmp_path).read("borrower").state.value == "PREFETCHED"
    assert blocks_restore(tmp_path)


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextlib.contextmanager
def drained():
    yield


def test_promotion_p4_records_acceptance_in_the_same_store(tmp_path):
    control = tmp_path / "control"
    live_dir = tmp_path / "profile"
    live_dir.mkdir()
    borrower = new()
    store = make_home(control, borrower)
    (live_dir / "live.db").write_bytes(b"old ledger")
    home = store.read("home")
    request = request_for(home, borrower)
    store.rebase_accepted(home.checkpoint_id, sha(live_dir / "live.db"))
    grant = store.home(lambda h: h.borrow(request, authenticated_peer=borrower))
    store.home(lambda h: h.activate(BorrowActivated(new(), grant.checkout_id, borrower, grant.epoch),
                                    authenticated_peer=borrower))
    (live_dir / "candidate.db").write_bytes(b"new ledger from the PC")
    begin = ReturnBegin(new(), new(), grant.checkout_id, borrower, grant.lineage_id, grant.epoch,
                        grant.base_checkpoint_id, sha(live_dir / "candidate.db"), 22)
    store.home(lambda h: h.receive_return(begin, authenticated_peer=borrower))
    activated = []
    with PosixPromotionFileOps(live_dir) as files:
        result = CandidatePromotionService(files, store).promote(
            operation_id=new(), old_checkpoint_id=home.checkpoint_id, new_checkpoint_id=new(),
            live_name="live.db", candidate_name="candidate.db", previous_name="previous.db",
            operation_gate=drained(), verify_database=lambda name: None,
            activate=lambda checkpoint, name: activated.append(checkpoint))
    after = ControlStore(control).read("home")
    assert result.phase is PromotionPhase.ACTIVATED and activated == [result.checkpoint_id]
    assert after.state is HomeState.AT_HOME and after.checkpoint_sha256 == begin.candidate_sha256
    assert after.receipt_for(begin.return_id).checkpoint_id == result.checkpoint_id
    assert (live_dir / "live.db").read_bytes() == b"new ledger from the PC"
    assert (live_dir / "previous.db").read_bytes() == b"old ledger"
    assert not blocks_restore(control)


def test_p4_refuses_a_file_no_return_matches(tmp_path):
    live_dir = tmp_path / "profile"
    live_dir.mkdir()
    store = make_home(tmp_path / "control", new())
    (live_dir / "live.db").write_bytes(b"old")
    (live_dir / "candidate.db").write_bytes(b"something nobody returned")
    home = store.read("home")
    store.rebase_accepted(home.checkpoint_id, sha(live_dir / "live.db"))
    with PosixPromotionFileOps(live_dir) as files, pytest.raises(ProtocolError):
        CandidatePromotionService(files, store).promote(
            operation_id=new(), old_checkpoint_id=home.checkpoint_id, new_checkpoint_id=new(),
            live_name="live.db", candidate_name="candidate.db", previous_name="previous.db",
            operation_gate=drained(), verify_database=lambda name: None, activate=lambda *a: None)
    # The guard fires after the file moved (P3): nothing is accepted, and the open promotion blocks writes and
    # restore until repaired. The lend service checks the match before it starts, so this is the last line.
    assert store.read("home").receipt_for(new()) is None and store.read("home").state is HomeState.AT_HOME
    assert store.unresolved_promotion().phase is PromotionPhase.FILE_PUBLISHED
    assert blocks_restore(tmp_path / "control")
