"""Protocol v1: every message, saved authority records and the borrower's states.

`tests/fixtures/sync_v1.json` freezes the wire form: a change to it is a protocol change and needs a new
PROTOCOL_VERSION, because a phone and a PC on different app versions must still understand each other."""
from __future__ import annotations

import dataclasses
import json
import threading
import uuid
from pathlib import Path

import pytest

from lightning.sync import domain
from lightning.sync.domain import (Accepted, Authenticate, Hello, MoveBegin, MoveDone, BorrowActivated, BorrowCancel, BorrowRequest, Checkpoint, Compatibility,
                                   Error, PairConfirm, PairReply, PairRequest, Prefetch, ReturnBegin, ReturnStatus,
                                   Status, StatusReply, BorrowGrant, Cancelled, Received, MAX_MESSAGE_BYTES,
                                   decode_message, encode_message)
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


# The protocol's rules in memory: parsing, races, cancels, tombstones and operation ids (no transport, no profile file).
def ident() -> str:
    return str(uuid.uuid4())


def fixture():
    borrower = ident()
    peer = ident()
    compatibility = Compatibility(1, 1, 1, 1, "0123456789abcdef", 1)
    home = HomeProtocolModel(
        profile_id=ident(), home_id=ident(), lineage_id=ident(),
        checkpoint_id=ident(), checkpoint_sha256="a" * 64,
        compatibility=compatibility, paired_devices={borrower, peer},
    )
    request = BorrowRequest(
        ident(), ident(), home.profile_id, home.home_id, home.lineage_id,
        borrower, home.checkpoint_id, home.checkpoint_sha256, compatibility,
    )
    return home, request, peer


def activated(home, request):
    grant = home.borrow(request, authenticated_peer=request.borrower_id)
    home.activate(BorrowActivated(ident(), grant.checkout_id, grant.borrower_id, grant.epoch),
                  authenticated_peer=request.borrower_id)
    return grant


def returning(request, grant):
    return ReturnBegin(
        ident(), ident(), grant.checkout_id, grant.borrower_id,
        grant.lineage_id, grant.epoch, grant.base_checkpoint_id, "b" * 64, 4096,
    )


def test_all_core_messages_round_trip_with_exact_schema():
    home, request, _ = fixture()
    grant = activated(home, request)
    message = returning(request, grant)
    samples = [
        request, grant,
        BorrowActivated(ident(), grant.checkout_id, grant.borrower_id, grant.epoch),
        BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True),
        Cancelled(grant.checkout_id, grant.borrower_id, grant.epoch),
        message, Received(message.return_id, message.checkout_id, message.candidate_sha256),
        Accepted(message.return_id, message.checkout_id, ident(), message.candidate_sha256,
                 message.lineage_id, message.epoch),
    ]
    for sample in samples:
        assert decode_message(encode_message(sample)) == sample


@pytest.mark.parametrize("mutation", [
    lambda data: {**data, "protocol": True},
    lambda data: {**data, "protocol": 2},
    lambda data: {**data, "kind": "Unknown"},
    lambda data: {**data, "unexpected": 1},
    lambda data: {key: val for key, val in data.items() if key != "checkout_id"},
    lambda data: {**data, "compatibility": {**data["compatibility"], "protocol": False}},
])
def test_parser_rejects_incompatible_or_extra_fields(mutation):
    _, request, _ = fixture()
    data = json.loads(encode_message(request))
    with pytest.raises(ValueError):
        decode_message(json.dumps(mutation(data)).encode())


def test_parser_rejects_duplicate_keys_and_oversize_message():
    _, request, _ = fixture()
    encoded = encode_message(request)
    with pytest.raises(ValueError, match="Malformed protocol JSON"):
        decode_message(encoded[:-1] + b',"kind":"BorrowRequest"}')
    with pytest.raises(ValueError, match="too large"):
        decode_message(b" " * (MAX_MESSAGE_BYTES + 1))


def test_only_one_borrower_wins_parallel_grant_attempts():
    home, request, peer = fixture()
    other = dataclasses.replace(request, operation_id=ident(), checkout_id=ident(), borrower_id=peer)
    barrier = threading.Barrier(2)
    results = []

    def run(message):
        barrier.wait()
        try:
            results.append(home.borrow(message, authenticated_peer=message.borrower_id))
        except ProtocolError as exc:
            results.append(exc.code)

    threads = [threading.Thread(target=run, args=(msg,)) for msg in (request, other)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert len(results) == 2
    assert sum(isinstance(result, BorrowGrant) for result in results) == 1
    assert "ALREADY_LENT" in results
    assert home.state is HomeState.LENT


def test_stale_base_compatibility_and_peer_are_rejected():
    home, request, peer = fixture()
    cases = [
        (dataclasses.replace(request, base_sha256="f" * 64), request.borrower_id, "STALE_BASE"),
        (dataclasses.replace(request, compatibility=dataclasses.replace(request.compatibility,
                                                                       ledger_schema=2)),
         request.borrower_id, "INCOMPATIBLE"),
        (request, peer, "UNAUTHORIZED"),
        (dataclasses.replace(request, lineage_id=ident()), request.borrower_id, "STALE_AUTHORITY"),
    ]
    for message, caller, code in cases:
        with pytest.raises(ProtocolError) as caught:
            home.borrow(message, authenticated_peer=caller)
        assert caught.value.code == code
    assert home.state is HomeState.AT_HOME


def test_rejected_checkout_and_return_messages_do_not_reserve_operation_ids():
    home, request, _ = fixture()
    stale_request = dataclasses.replace(request, base_sha256="f" * 64)
    with pytest.raises(ProtocolError, match="Prefetch"):
        home.borrow(stale_request, authenticated_peer=request.borrower_id)
    grant = home.borrow(request, authenticated_peer=request.borrower_id)

    activation = BorrowActivated(ident(), grant.checkout_id, grant.borrower_id, grant.epoch)
    with pytest.raises(ProtocolError, match="active grant"):
        home.activate(dataclasses.replace(activation, epoch=grant.epoch + 1),
                      authenticated_peer=request.borrower_id)
    assert home.activate(activation, authenticated_peer=request.borrower_id) == grant

    returned = returning(request, grant)
    with pytest.raises(ProtocolError, match="active checkout"):
        home.receive_return(dataclasses.replace(returned, epoch=grant.epoch + 1),
                            authenticated_peer=request.borrower_id)
    assert isinstance(home.receive_return(returned, authenticated_peer=request.borrower_id), Received)


def test_rejected_cancellation_does_not_reserve_its_operation_id():
    home, request, _ = fixture()
    grant = activated(home, request)
    rejected = BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True)
    with pytest.raises(ProtocolError, match="cannot cancel"):
        home.cancel(rejected, authenticated_peer=request.borrower_id)
    another = dataclasses.replace(rejected, checkout_id=ident())
    assert home.cancel(another, authenticated_peer=request.borrower_id).epoch == 0


def test_authenticated_durable_cancel_before_grant_tombstones_checkout():
    home, request, _ = fixture()
    cancel = BorrowCancel(ident(), request.checkout_id, request.borrower_id, True)
    receipt = home.cancel(cancel, authenticated_peer=request.borrower_id)
    assert receipt.epoch == 0
    assert home.cancel(cancel, authenticated_peer=request.borrower_id) == receipt
    with pytest.raises(ProtocolError, match="cancelled"):
        home.borrow(request, authenticated_peer=request.borrower_id)
    assert home.state is HomeState.AT_HOME


def test_cancel_after_grant_ends_lend_only_for_borrower_and_prevents_late_activation():
    home, request, peer = fixture()
    grant = home.borrow(request, authenticated_peer=request.borrower_id)
    cancel = BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True)
    with pytest.raises(ProtocolError) as caught:
        home.cancel(cancel, authenticated_peer=peer)
    assert caught.value.code == "UNAUTHORIZED"
    assert home.state is HomeState.LENT
    assert home.cancel(cancel, authenticated_peer=grant.borrower_id).epoch == grant.epoch
    with pytest.raises(ProtocolError) as caught:
        home.activate(BorrowActivated(ident(), grant.checkout_id, grant.borrower_id, grant.epoch),
                      authenticated_peer=grant.borrower_id)
    assert caught.value.code == "CANCELLED"
    assert home.state is HomeState.AT_HOME


def test_activated_borrow_cannot_cancel():
    home, request, _ = fixture()
    grant = activated(home, request)
    with pytest.raises(ProtocolError) as caught:
        home.cancel(BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True),
                    authenticated_peer=grant.borrower_id)
    assert caught.value.code == "ACTIVE_CHECKOUT"
    assert home.state is HomeState.LENT


def test_received_keeps_authority_away_until_matching_publication():
    home, request, _ = fixture()
    grant = activated(home, request)
    message = returning(request, grant)
    received = home.receive_return(message, authenticated_peer=grant.borrower_id)
    assert isinstance(received, Received)
    assert home.state is HomeState.RETURN_RECEIVED
    assert home.receive_return(message, authenticated_peer=grant.borrower_id) == received
    with pytest.raises(ProtocolError) as caught:
        home.borrow(request, authenticated_peer=grant.borrower_id)
    assert caught.value.code == "STALE_AUTHORITY"
    with pytest.raises(ProtocolError) as caught:
        home.borrow(dataclasses.replace(request, operation_id=ident(), checkout_id=ident()),
                    authenticated_peer=grant.borrower_id)
    assert caught.value.code == "ALREADY_LENT"
    acceptance = Accepted(message.return_id, grant.checkout_id, ident(), message.candidate_sha256,
                          grant.lineage_id, grant.epoch)
    with pytest.raises(ProtocolError) as caught:
        home.record_accepted(acceptance, published_sha256="c" * 64)
    assert caught.value.code == "NOT_PUBLISHED"
    with pytest.raises(ProtocolError) as caught:
        home.record_accepted(dataclasses.replace(acceptance, checkpoint_id=grant.base_checkpoint_id),
                             published_sha256=message.candidate_sha256)
    assert caught.value.code == "NOT_PUBLISHED"
    assert home.state is HomeState.RETURN_RECEIVED
    assert home.record_accepted(acceptance, published_sha256=message.candidate_sha256) == acceptance
    assert home.receive_return(message, authenticated_peer=grant.borrower_id) == acceptance
    with pytest.raises(ProtocolError) as caught:
        home.borrow(request, authenticated_peer=grant.borrower_id)
    assert caught.value.code == "STALE_AUTHORITY"
    assert home.state is HomeState.AT_HOME
    assert home.checkpoint_id == acceptance.checkpoint_id
    with pytest.raises(ProtocolError) as caught:
        home.cancel(BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True),
                    authenticated_peer=grant.borrower_id)
    assert caught.value.code == "ACTIVE_CHECKOUT"


def test_return_succeeds_when_activation_ack_was_lost():
    home, request, _ = fixture()
    grant = home.borrow(request, authenticated_peer=request.borrower_id)
    message = returning(request, grant)
    assert isinstance(home.receive_return(message, authenticated_peer=grant.borrower_id), Received)
    assert home.state is HomeState.RETURN_RECEIVED
    with pytest.raises(ProtocolError) as caught:
        home.cancel(BorrowCancel(ident(), grant.checkout_id, grant.borrower_id, True),
                    authenticated_peer=grant.borrower_id)
    assert caught.value.code == "ACTIVE_CHECKOUT"
    assert home.state is HomeState.RETURN_RECEIVED


def test_return_replay_conflict_and_stale_epoch_are_rejected():
    home, request, _ = fixture()
    grant = activated(home, request)
    message = returning(request, grant)
    stale = dataclasses.replace(message, operation_id=ident(), epoch=grant.epoch + 1)
    with pytest.raises(ProtocolError) as caught:
        home.receive_return(stale, authenticated_peer=grant.borrower_id)
    assert caught.value.code == "STALE_AUTHORITY"
    home.receive_return(message, authenticated_peer=grant.borrower_id)
    replay = dataclasses.replace(message, operation_id=ident(), candidate_sha256="c" * 64)
    with pytest.raises(ProtocolError) as caught:
        home.receive_return(replay, authenticated_peer=grant.borrower_id)
    assert caught.value.code == "REPLAY_CONFLICT"


def test_operation_id_cannot_be_reused_for_different_content():
    home, request, _ = fixture()
    home.borrow(request, authenticated_peer=request.borrower_id)
    changed = dataclasses.replace(request, checkout_id=ident())
    with pytest.raises(ProtocolError) as caught:
        home.borrow(changed, authenticated_peer=changed.borrower_id)
    assert caught.value.code == "REPLAY_CONFLICT"


def test_new_lend_requires_newly_accepted_checkpoint_and_new_epoch():
    home, request, _ = fixture()
    first = activated(home, request)
    returned = returning(request, first)
    home.receive_return(returned, authenticated_peer=request.borrower_id)
    accepted = Accepted(returned.return_id, first.checkout_id, ident(), returned.candidate_sha256,
                        first.lineage_id, first.epoch)
    home.record_accepted(accepted, published_sha256=accepted.candidate_sha256)
    stale = dataclasses.replace(request, operation_id=ident(), checkout_id=ident())
    with pytest.raises(ProtocolError) as caught:
        home.borrow(stale, authenticated_peer=stale.borrower_id)
    assert caught.value.code == "STALE_BASE"
    fresh = dataclasses.replace(stale, operation_id=ident(), checkout_id=ident(),
                                base_checkpoint_id=accepted.checkpoint_id,
                                base_sha256=accepted.candidate_sha256)
    second = home.borrow(fresh, authenticated_peer=fresh.borrower_id)
    assert second.epoch == first.epoch + 1


def test_cancel_tombstone_cannot_be_rewritten_with_another_operation():
    home, request, _ = fixture()
    home.borrow(request, authenticated_peer=request.borrower_id)
    cancel = BorrowCancel(ident(), request.checkout_id, request.borrower_id, True)
    home.cancel(cancel, authenticated_peer=request.borrower_id)
    with pytest.raises(ProtocolError) as caught:
        home.cancel(dataclasses.replace(cancel, operation_id=ident()),
                    authenticated_peer=request.borrower_id)
    assert caught.value.code == "REPLAY_CONFLICT"
