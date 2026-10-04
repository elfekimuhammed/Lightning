"""Checkout protocol contract; no transport or profile database is involved."""

from __future__ import annotations

import dataclasses
import json
import threading
import uuid

import pytest

from lightning.sync.domain import (
    Accepted,
    BorrowActivated,
    BorrowCancel,
    BorrowGrant,
    BorrowRequest,
    Cancelled,
    Compatibility,
    MAX_MESSAGE_BYTES,
    Received,
    ReturnBegin,
    decode_message,
    encode_message,
)
from lightning.sync.state import HomeProtocolModel, HomeState, ProtocolError


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
