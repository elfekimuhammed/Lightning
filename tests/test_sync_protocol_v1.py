"""Protocol v1 (task 05a): every message, saved authority records and the borrower's states.

`tests/fixtures/sync_v1.json` freezes the wire form: a change to it is a protocol change and needs a new
PROTOCOL_VERSION, because a phone and a PC on different app versions must still understand each other."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from lightning.sync import domain
from lightning.sync.domain import (Accepted, Authenticate, Hello, MoveBegin, MoveDone, BorrowActivated, BorrowCancel, BorrowRequest, Checkpoint, Compatibility,
                                   Error, PairConfirm, PairReply, PairRequest, Prefetch, ReturnBegin, ReturnStatus,
                                   Status, StatusReply, decode_message, encode_message)
from lightning.sync.state import (BorrowerModel, BorrowerState, HomeProtocolModel, HomeState, ProtocolError)

FROZEN = Path(__file__).parent / "fixtures" / "sync_v1.json"


def u(n: int) -> str:
    """Stable version 4 UUIDs for frozen examples."""
    return str(uuid.UUID(int=n, version=4))


COMPAT = Compatibility(1, 1, 45, 1, "0123456789abcdef", 1)


def examples():
    return [
        PairRequest(u(1), u(2), "Office PC", "02" + "ab" * 32, "cd" * 32),
        PairReply(u(1), u(3), "Mohab", u(4), "Mohab's phone", u(5), '{"version": 2}', "0123456789abcdef", "ef" * 32),
        PairConfirm(u(1), u(2)),
        Status(u(2)),
        StatusReply(u(3), u(5), "LENT", u(6), "a" * 64, 3, u(2), False),
        Prefetch(u(7), u(2)),
        Checkpoint(u(6), u(5), "a" * 64, 4096, 45),
        BorrowRequest(u(8), u(9), u(3), u(4), u(5), u(2), u(6), "a" * 64, COMPAT),
        BorrowActivated(u(10), u(9), u(2), 3),
        BorrowCancel(u(11), u(9), u(2), True),
        ReturnBegin(u(12), u(13), u(9), u(2), u(5), 3, u(6), "b" * 64, 8192),
        ReturnStatus(u(13), u(2)),
        Accepted(u(13), u(9), u(14), "b" * 64, u(5), 3),
        Error("UNLOCK_NEEDED", "Unlock Lightning on your phone."),
        Hello("12" * 32),
        Authenticate(u(2), "30" * 70),
        MoveBegin(u(15), u(2), "Office PC", "02" + "ab" * 32, u(3), "Mohab", '{"version": 2}', "0123456789abcdef",
                  45, "c" * 64, 4096, "cd" * 32),
        MoveDone(u(15), u(4), "Mohab's phone", u(5), "ef" * 32),
    ]


def test_wire_form_is_frozen():
    encoded = [encode_message(message).decode("ascii") for message in examples()]
    assert encoded == json.loads(FROZEN.read_text(encoding="utf-8"))
    assert domain.PROTOCOL_VERSION == 1


@pytest.mark.parametrize("message", examples(), ids=lambda m: type(m).__name__)
def test_every_message_round_trips(message):
    assert decode_message(encode_message(message)) == message


@pytest.mark.parametrize("bad", [
    lambda: PairRequest(u(1), u(2), " padded", "02" + "ab" * 32, "cd" * 32),
    lambda: PairRequest(u(1), u(2), "x" * 61, "02" + "ab" * 32, "cd" * 32),
    lambda: PairRequest(u(1), u(2), "PC", "04" + "ab" * 32, "cd" * 32),
    lambda: PairReply(u(1), u(3), "M", u(4), "P", u(5), "", "0123456789abcdef", "ef" * 32),
    lambda: StatusReply(u(3), u(5), "SOMEWHERE", u(6), "a" * 64, 0, "", True),
    lambda: StatusReply(u(3), u(5), "AT_HOME", u(6), "a" * 64, 0, "", 1),
    lambda: Checkpoint(u(6), u(5), "a" * 64, 0, 45),
    lambda: Error("MADE_UP", "x"),
    lambda: Error("BUSY", "x" * 301),
])
def test_invalid_values_are_refused(bad):
    with pytest.raises(ValueError):
        bad()


def home_and_request():
    borrower = str(uuid.uuid4())
    home = HomeProtocolModel(profile_id=u(3), home_id=u(4), lineage_id=u(5), checkpoint_id=u(6),
                             checkpoint_sha256="a" * 64, compatibility=COMPAT, paired_devices={borrower})
    request = BorrowRequest(str(uuid.uuid4()), str(uuid.uuid4()), u(3), u(4), u(5), borrower, u(6), "a" * 64, COMPAT)
    return home, request


def restarted(home):
    """What a restart sees: only what was saved, through JSON."""
    return HomeProtocolModel.from_record(json.loads(json.dumps(home.to_record())))


def test_home_record_survives_restart_at_every_step_and_replays_the_same_answers():
    home, request = home_and_request()
    peer = request.borrower_id
    grant = home.borrow(request, authenticated_peer=peer)
    home = restarted(home)
    assert home.state is HomeState.LENT and home.borrow(request, authenticated_peer=peer) == grant
    activation = BorrowActivated(str(uuid.uuid4()), grant.checkout_id, peer, grant.epoch)
    home.activate(activation, authenticated_peer=peer)
    home = restarted(home)
    begin = ReturnBegin(str(uuid.uuid4()), str(uuid.uuid4()), grant.checkout_id, peer, grant.lineage_id, grant.epoch,
                        grant.base_checkpoint_id, "b" * 64, 100)
    received = home.receive_return(begin, authenticated_peer=peer)
    home = restarted(home)
    assert home.state is HomeState.RETURN_RECEIVED and home.pending_return() == begin
    assert home.receive_return(begin, authenticated_peer=peer) == received
    accepted = Accepted(begin.return_id, grant.checkout_id, str(uuid.uuid4()), "b" * 64, grant.lineage_id, grant.epoch)
    home.record_accepted(accepted, published_sha256="b" * 64)
    home = restarted(home)
    assert home.state is HomeState.AT_HOME and home.checkpoint_sha256 == "b" * 64
    assert home.receive_return(begin, authenticated_peer=peer) == accepted  # a lost receipt is replayed
    assert home.receipt_for(begin.return_id) == accepted


def test_cancel_tombstone_survives_restart():
    home, request = home_and_request()
    peer = request.borrower_id
    home.cancel(BorrowCancel(str(uuid.uuid4()), request.checkout_id, peer, True), authenticated_peer=peer)
    home = restarted(home)
    with pytest.raises(ProtocolError) as refused:
        home.borrow(request, authenticated_peer=peer)  # the request arrived after its cancellation
    assert refused.value.code == "CANCELLED"


def test_take_back_fences_the_old_borrower_and_allows_a_new_lend():
    home, request = home_and_request()
    peer = request.borrower_id
    grant = home.borrow(request, authenticated_peer=peer)
    home.take_back(str(uuid.uuid4()))
    home = restarted(home)
    late = ReturnBegin(str(uuid.uuid4()), str(uuid.uuid4()), grant.checkout_id, peer, grant.lineage_id, grant.epoch,
                       grant.base_checkpoint_id, "b" * 64, 100)
    with pytest.raises(ProtocolError) as refused:
        home.receive_return(late, authenticated_peer=peer)
    assert refused.value.code == "STALE_AUTHORITY" and home.state is HomeState.AT_HOME
    fresh = BorrowRequest(str(uuid.uuid4()), str(uuid.uuid4()), u(3), u(4), home.lineage_id, peer, u(6), "a" * 64,
                          COMPAT)
    assert home.borrow(fresh, authenticated_peer=peer).epoch == grant.epoch + 1


def test_revoked_device_cannot_borrow_and_checkpoint_moves_only_at_home():
    home, request = home_and_request()
    home.revoke(request.borrower_id)
    with pytest.raises(ProtocolError):
        home.borrow(request, authenticated_peer=request.borrower_id)
    home.pair(request.borrower_id)
    home.set_checkpoint(str(uuid.uuid4()), "c" * 64)
    with pytest.raises(ProtocolError) as stale:
        home.borrow(request, authenticated_peer=request.borrower_id)
    assert stale.value.code == "STALE_BASE"


def borrower_for(home, peer):
    return BorrowerModel(profile_id=home.profile_id, home_id=home.home_id, lineage_id=home.lineage_id, device_id=peer)


def test_borrower_walks_the_whole_cycle_with_restarts():
    home, request = home_and_request()
    peer = request.borrower_id
    pc = borrower_for(home, peer)

    def saved(model):
        return BorrowerModel.from_record(json.loads(json.dumps(model.to_record())))

    pc.prefetched(home.checkpoint_id, home.checkpoint_sha256)
    pc.prepare(request)
    pc = saved(pc)
    assert pc.state is BorrowerState.BORROW_PREPARED and not pc.writable
    pc.granted(home.borrow(request, authenticated_peer=peer))
    pc = saved(pc)
    assert pc.writable
    pc.seal()
    pc = saved(pc)
    assert not pc.writable
    pc.unseal()
    grant = pc.grant
    begin = ReturnBegin(str(uuid.uuid4()), str(uuid.uuid4()), grant.checkout_id, peer, grant.lineage_id, grant.epoch,
                        grant.base_checkpoint_id, "b" * 64, 100)
    pc.begin_return(begin)
    pc = saved(pc)
    assert pc.state is BorrowerState.RETURNING and not pc.writable
    with pytest.raises(ProtocolError):
        pc.unseal()  # returning never resumes editing
    home.receive_return(begin, authenticated_peer=peer)
    accepted = home.record_accepted(Accepted(begin.return_id, grant.checkout_id, str(uuid.uuid4()), "b" * 64,
                                             grant.lineage_id, grant.epoch), published_sha256="b" * 64)
    pc.handed_back(accepted)
    pc = saved(pc)
    assert pc.state is BorrowerState.HANDED_BACK and pc.checkpoint_sha256 == "b" * 64


def test_borrower_refuses_late_grant_after_abort_and_mismatched_grant():
    home, request = home_and_request()
    peer = request.borrower_id
    pc = borrower_for(home, peer)
    pc.prefetched(home.checkpoint_id, home.checkpoint_sha256)
    pc.prepare(request)
    grant = home.borrow(request, authenticated_peer=peer)
    other = BorrowerModel.from_record(pc.to_record())
    pc.abort(BorrowCancel(str(uuid.uuid4()), request.checkout_id, peer, True))
    with pytest.raises(ProtocolError) as late:
        pc.granted(grant)
    assert late.value.code == "CANCELLED"
    from dataclasses import replace
    with pytest.raises(ProtocolError):
        other.granted(replace(grant, base_sha256="f" * 64))


def test_corrupt_records_are_refused():
    home, request = home_and_request()
    record = home.to_record()
    with pytest.raises(ValueError):
        HomeProtocolModel.from_record({**record, "version": 2})
    with pytest.raises((ValueError, KeyError)):
        HomeProtocolModel.from_record({**record, "state": "LENT"})  # lent with no checkout
    pc = borrower_for(home, request.borrower_id)
    with pytest.raises(ValueError):
        BorrowerModel.from_record({**pc.to_record(), "state": "BORROWING"})  # borrowing without a permit
