"""In-memory authority model for validating checkout message behavior.

This is intentionally not a persistent authority store. It provides the
transition contract and replay behavior task 05b must preserve across restarts.
It never opens a finance database or grants write access to a session.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum

from .domain import (
    Accepted,
    BorrowActivated,
    BorrowCancel,
    BorrowGrant,
    BorrowRequest,
    Cancelled,
    Compatibility,
    Received,
    ReturnBegin,
    _hash,
    _id,
    from_fields,
    to_fields,
)


class HomeState(StrEnum):
    AT_HOME = "AT_HOME"
    LENT = "LENT"
    RETURN_RECEIVED = "RETURN_RECEIVED"
    NEEDS_REPAIR = "NEEDS_REPAIR"


RECORD_VERSION = 1


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class _Checkout:
    request: BorrowRequest
    grant: BorrowGrant
    activated: bool = False


class HomeProtocolModel:
    """Serialized, replay-aware model; persistence and OS write gates are later.

    `authenticated_peer` is supplied by the eventual pinned-identity transport.
    Passing a string here is a test seam, not authentication in this class.
    """

    def __init__(self, *, profile_id: str, home_id: str, lineage_id: str,
                 checkpoint_id: str, checkpoint_sha256: str,
                 compatibility: Compatibility, paired_devices: set[str]):
        for name, value in (("profile_id", profile_id), ("home_id", home_id),
                            ("lineage_id", lineage_id), ("checkpoint_id", checkpoint_id)):
            _id(value, name)
        _hash(checkpoint_sha256, "checkpoint_sha256")
        if not isinstance(compatibility, Compatibility):
            raise ValueError("Invalid compatibility")
        for device in paired_devices:
            _id(device, "paired device")
        self.profile_id = profile_id
        self.home_id = home_id
        self.lineage_id = lineage_id
        self.checkpoint_id = checkpoint_id
        self.checkpoint_sha256 = checkpoint_sha256
        self.compatibility = compatibility
        self.paired_devices = frozenset(paired_devices)
        self.state = HomeState.AT_HOME
        self.epoch = 0
        self.active: _Checkout | None = None
        self._operations: dict[str, object] = {}
        self._grants: dict[str, _Checkout] = {}
        self._cancellations: dict[str, tuple[BorrowCancel, Cancelled]] = {}
        self._returns: dict[str, tuple[ReturnBegin, Received]] = {}
        self._accepted: dict[str, Accepted] = {}
        self._lock = threading.RLock()

    def _peer(self, claimed: str, authenticated_peer: str) -> None:
        if claimed != authenticated_peer or claimed not in self.paired_devices:
            raise ProtocolError("UNAUTHORIZED", "Borrower identity is not paired and authenticated")

    def _check_operation(self, operation_id: str, message: object) -> None:
        previous = self._operations.get(operation_id)
        if previous is not None and previous != message:
            raise ProtocolError("REPLAY_CONFLICT", "Operation ID reused for different content")

    def borrow(self, request: BorrowRequest, *, authenticated_peer: str) -> BorrowGrant:
        with self._lock:
            self._peer(request.borrower_id, authenticated_peer)
            if (request.profile_id, request.home_id, request.lineage_id) != (
                self.profile_id, self.home_id, self.lineage_id
            ):
                raise ProtocolError("STALE_AUTHORITY", "Profile, home or lineage differs")
            try:
                self.compatibility.require_same(request.compatibility)
            except ValueError as exc:
                raise ProtocolError("INCOMPATIBLE", str(exc)) from exc
            self._check_operation(request.operation_id, request)
            if request.checkout_id in self._cancellations:
                raise ProtocolError("CANCELLED", "This checkout was durably cancelled by the borrower")
            prior = self._grants.get(request.checkout_id)
            if prior is not None:
                if prior.request != request:
                    raise ProtocolError("REPLAY_CONFLICT", "Checkout ID reused for different content")
                if self.active is not prior or self.state is not HomeState.LENT:
                    raise ProtocolError("STALE_AUTHORITY", "Checkout has already started returning or finished")
                return prior.grant
            if self.state is not HomeState.AT_HOME:
                raise ProtocolError("ALREADY_LENT", "Another checkout or return holds authority")
            if (request.base_checkpoint_id, request.base_sha256) != (
                self.checkpoint_id, self.checkpoint_sha256
            ):
                raise ProtocolError("STALE_BASE", "Prefetch does not match the accepted checkpoint")
            self._operations[request.operation_id] = request
            self.epoch += 1
            grant = BorrowGrant(
                request.checkout_id, request.borrower_id, self.lineage_id, self.epoch,
                self.checkpoint_id, self.checkpoint_sha256,
            )
            checkout = _Checkout(request, grant)
            self._grants[request.checkout_id] = checkout
            self.active = checkout
            self.state = HomeState.LENT
            return grant

    def activate(self, message: BorrowActivated, *, authenticated_peer: str) -> BorrowGrant:
        with self._lock:
            self._peer(message.borrower_id, authenticated_peer)
            self._check_operation(message.operation_id, message)
            if message.checkout_id in self._cancellations:
                raise ProtocolError("CANCELLED", "Cancelled checkout cannot be activated")
            active = self.active
            if (self.state is not HomeState.LENT or active is None
                    or message.checkout_id != active.grant.checkout_id
                    or message.borrower_id != active.grant.borrower_id
                    or message.epoch != active.grant.epoch):
                raise ProtocolError("STALE_AUTHORITY", "Activation does not match the active grant")
            self._operations[message.operation_id] = message
            active.activated = True
            return active.grant

    def cancel(self, message: BorrowCancel, *, authenticated_peer: str) -> Cancelled:
        """Caller asserts it durably recorded ABORTED before sending this."""
        with self._lock:
            self._peer(message.borrower_id, authenticated_peer)
            self._check_operation(message.operation_id, message)
            prior = self._cancellations.get(message.checkout_id)
            if prior is not None:
                if prior[0] != message:
                    raise ProtocolError("REPLAY_CONFLICT", "Cancellation ID reused for different content")
                return prior[1]
            known = self._grants.get(message.checkout_id)
            if known is not None and known.grant.borrower_id != message.borrower_id:
                raise ProtocolError("UNAUTHORIZED", "Only the granted borrower can cancel")
            if known is not None and (known.activated
                                      or any(returned.checkout_id == message.checkout_id
                                             for returned, _ in self._returns.values())
                                      or (self.active is known and self.state is not HomeState.LENT)):
                raise ProtocolError("ACTIVE_CHECKOUT", "Activated or returned checkout cannot cancel")
            self._operations[message.operation_id] = message
            receipt = Cancelled(message.checkout_id, message.borrower_id,
                                known.grant.epoch if known is not None else 0)
            self._cancellations[message.checkout_id] = (message, receipt)
            if self.active is known and known is not None:
                self.active = None
                self.state = HomeState.AT_HOME
            return receipt

    def receive_return(self, message: ReturnBegin, *, authenticated_peer: str) -> Received | Accepted:
        """Record exact return identity after the complete ciphertext is flushed."""
        with self._lock:
            self._peer(message.borrower_id, authenticated_peer)
            self._check_operation(message.operation_id, message)
            prior = self._returns.get(message.return_id)
            if prior is not None:
                if prior[0] != message:
                    raise ProtocolError("REPLAY_CONFLICT", "Return ID reused for different content")
                return self._accepted.get(message.return_id, prior[1])
            active = self.active
            # BorrowActivated is advisory: its acknowledgement can be lost after
            # the borrower durably enabled writes. The permit itself is enough
            # to identify a valid return.
            if (self.state is not HomeState.LENT or active is None
                    or message.checkout_id != active.grant.checkout_id
                    or message.borrower_id != active.grant.borrower_id
                    or message.lineage_id != self.lineage_id
                    or message.epoch != active.grant.epoch
                    or message.parent_checkpoint_id != active.grant.base_checkpoint_id):
                raise ProtocolError("STALE_AUTHORITY", "Return does not match the active checkout")
            self._operations[message.operation_id] = message
            receipt = Received(message.return_id, message.checkout_id, message.candidate_sha256)
            self._returns[message.return_id] = (message, receipt)
            self.state = HomeState.RETURN_RECEIVED
            return receipt

    def record_accepted(self, receipt: Accepted, *, published_sha256: str) -> Accepted:
        """Model P4; caller must already have verified and durably published P0–P4.

        This in-memory check does not replace that publication proof in task 05b.
        """
        with self._lock:
            prior = self._accepted.get(receipt.return_id)
            if prior is not None:
                if prior != receipt:
                    raise ProtocolError("REPLAY_CONFLICT", "Acceptance receipt changed")
                return prior
            pending = self._returns.get(receipt.return_id)
            active = self.active
            if (pending is None or active is None
                    or self.state is not HomeState.RETURN_RECEIVED
                    or receipt.checkout_id != active.grant.checkout_id
                    or receipt.lineage_id != self.lineage_id
                    or receipt.epoch != active.grant.epoch
                    or receipt.checkpoint_id == active.grant.base_checkpoint_id
                    or receipt.candidate_sha256 != pending[0].candidate_sha256
                    or published_sha256 != receipt.candidate_sha256):
                raise ProtocolError("NOT_PUBLISHED", "No matching verified, published return")
            self._accepted[receipt.return_id] = receipt
            self.checkpoint_id = receipt.checkpoint_id
            self.checkpoint_sha256 = receipt.candidate_sha256
            self.active = None
            self.state = HomeState.AT_HOME
            return receipt

    # ------------------------------------------------------------ home-only actions (no message from a peer)
    def set_checkpoint(self, checkpoint_id: str, checkpoint_sha256: str) -> None:
        """A new immutable checkpoint of the home ledger (prefetch, or after home edits). Only while at home."""
        _id(checkpoint_id, "checkpoint_id")
        _hash(checkpoint_sha256, "checkpoint_sha256")
        with self._lock:
            if self.state is not HomeState.AT_HOME:
                raise ProtocolError("STALE_AUTHORITY", "The ledger is not at home")
            self.checkpoint_id, self.checkpoint_sha256 = checkpoint_id, checkpoint_sha256

    def pair(self, device_id: str) -> None:
        _id(device_id, "device_id")
        with self._lock:
            self.paired_devices = self.paired_devices | {device_id}

    def revoke(self, device_id: str) -> None:
        """No future connection or grant. An active lend stays lent: bring it back or take it back."""
        with self._lock:
            self.paired_devices = self.paired_devices - {device_id}

    def mark_needs_repair(self) -> None:
        with self._lock:
            if self.state is HomeState.AT_HOME:
                raise ProtocolError("STALE_AUTHORITY", "Nothing to repair at home")
            self.state = HomeState.NEEDS_REPAIR

    def take_back(self, new_lineage_id: str) -> None:
        """Owner's explicit choice: end the lend without the borrower. A new lineage fences every old copy:
        the old borrower can never hand back into it (plan section 5, rule 8)."""
        _id(new_lineage_id, "new_lineage_id")
        with self._lock:
            if self.state is HomeState.AT_HOME:
                raise ProtocolError("STALE_AUTHORITY", "The ledger is already at home")
            if new_lineage_id == self.lineage_id:
                raise ProtocolError("REPLAY_CONFLICT", "Take back needs a new lineage")
            self.lineage_id = new_lineage_id
            self.active = None
            self.state = HomeState.AT_HOME

    # ------------------------------------------------------------ durable form (task 05b stores this)
    def to_record(self) -> dict:
        checkouts = [{"request": to_fields(c.request), "grant": to_fields(c.grant), "activated": c.activated}
                     for c in self._grants.values()]
        return {
            "version": RECORD_VERSION,
            "profile_id": self.profile_id, "home_id": self.home_id, "lineage_id": self.lineage_id,
            "checkpoint_id": self.checkpoint_id, "checkpoint_sha256": self.checkpoint_sha256,
            "compatibility": to_fields(self.compatibility), "paired_devices": sorted(self.paired_devices),
            "state": self.state.value, "epoch": self.epoch,
            "active": self.active.grant.checkout_id if self.active is not None else None,
            "checkouts": checkouts,
            "operations": {key: [type(value).__name__, to_fields(value)] for key, value in self._operations.items()},
            "cancellations": [[to_fields(m), to_fields(r)] for m, r in self._cancellations.values()],
            "returns": [[to_fields(m), to_fields(r)] for m, r in self._returns.values()],
            "accepted": [to_fields(a) for a in self._accepted.values()],
        }

    @classmethod
    def from_record(cls, record: dict) -> "HomeProtocolModel":
        if not isinstance(record, dict) or record.get("version") != RECORD_VERSION:
            raise ValueError("Unsupported home authority record")
        model = cls(profile_id=record["profile_id"], home_id=record["home_id"], lineage_id=record["lineage_id"],
                    checkpoint_id=record["checkpoint_id"], checkpoint_sha256=record["checkpoint_sha256"],
                    compatibility=from_fields(Compatibility, record["compatibility"]),
                    paired_devices=set(record["paired_devices"]))
        model.state = HomeState(record["state"])
        epoch = record["epoch"]
        if type(epoch) is not int or epoch < 0:
            raise ValueError("Invalid epoch")
        model.epoch = epoch
        types = {"BorrowRequest": BorrowRequest, "BorrowActivated": BorrowActivated, "BorrowCancel": BorrowCancel,
                 "ReturnBegin": ReturnBegin}
        for item in record["checkouts"]:
            if type(item["activated"]) is not bool:
                raise ValueError("Invalid checkout")
            checkout = _Checkout(from_fields(BorrowRequest, item["request"]), from_fields(BorrowGrant, item["grant"]),
                                 item["activated"])
            model._grants[checkout.grant.checkout_id] = checkout
        active = record["active"]
        model.active = model._grants[active] if active is not None else None
        for key, (name, fields) in record["operations"].items():
            model._operations[key] = from_fields(types[name], fields)
        for message, receipt in record["cancellations"]:
            cancel = from_fields(BorrowCancel, message)
            model._cancellations[cancel.checkout_id] = (cancel, from_fields(Cancelled, receipt))
        for message, receipt in record["returns"]:
            begin = from_fields(ReturnBegin, message)
            model._returns[begin.return_id] = (begin, from_fields(Received, receipt))
        for fields in record["accepted"]:
            accepted = from_fields(Accepted, fields)
            model._accepted[accepted.return_id] = accepted
        if (model.state in (HomeState.LENT, HomeState.RETURN_RECEIVED)) != (model.active is not None) \
                and model.state is not HomeState.NEEDS_REPAIR:
            raise ValueError("Home authority record is inconsistent")
        return model

    def pending_return(self) -> ReturnBegin | None:
        """The received, not yet accepted return of the active checkout."""
        with self._lock:
            if self.active is None:
                return None
            for begin, _ in self._returns.values():
                if begin.checkout_id == self.active.grant.checkout_id and begin.return_id not in self._accepted:
                    return begin
            return None

    def receipt_for(self, return_id: str) -> Received | Accepted | None:
        with self._lock:
            if return_id in self._accepted:
                return self._accepted[return_id]
            prior = self._returns.get(return_id)
            return prior[1] if prior is not None else None


# ==================================================================== borrower (a PC)

class BorrowerState(StrEnum):
    PREFETCHED = "PREFETCHED"
    BORROW_PREPARED = "BORROW_PREPARED"
    BORROWING = "BORROWING"
    SEALED = "SEALED"
    RETURNING = "RETURNING"
    HANDED_BACK = "HANDED_BACK"
    ABORTED = "ABORTED"
    NEEDS_REPAIR = "NEEDS_REPAIR"


_WRITABLE = frozenset({BorrowerState.BORROWING})
_IDLE = frozenset({BorrowerState.HANDED_BACK, BorrowerState.ABORTED})


class BorrowerModel:
    """One PC's view of one borrowed profile (plan section 5, borrower table).

    Only BORROWING may open the working copy writable. RETURNING never goes back to editing; SEALED does,
    under the same process lock that the hand-back worker takes (task 13)."""

    def __init__(self, *, profile_id: str, home_id: str, lineage_id: str, device_id: str):
        for name, value in (("profile_id", profile_id), ("home_id", home_id), ("lineage_id", lineage_id),
                            ("device_id", device_id)):
            _id(value, name)
        self.profile_id, self.home_id, self.lineage_id, self.device_id = profile_id, home_id, lineage_id, device_id
        self.state = BorrowerState.HANDED_BACK  # nothing borrowed yet
        self.checkpoint_id: str | None = None
        self.checkpoint_sha256: str | None = None
        self.request: BorrowRequest | None = None
        self.grant: BorrowGrant | None = None
        self.returning: ReturnBegin | None = None
        self.accepted: Accepted | None = None
        self.cancel: BorrowCancel | None = None

    @property
    def writable(self) -> bool:
        return self.state in _WRITABLE

    def _require(self, *states: BorrowerState) -> None:
        if self.state not in states:
            raise ProtocolError("STALE_AUTHORITY", f"Not allowed while {self.state.value.lower().replace('_', ' ')}")

    def prefetched(self, checkpoint_id: str, sha256: str) -> None:
        """A verified copy of the home's checkpoint arrived. Replaces an older prefetch, never a lend."""
        _id(checkpoint_id, "checkpoint_id")
        _hash(sha256, "sha256")
        self._require(BorrowerState.HANDED_BACK, BorrowerState.ABORTED, BorrowerState.PREFETCHED)
        self.state, self.checkpoint_id, self.checkpoint_sha256 = BorrowerState.PREFETCHED, checkpoint_id, sha256
        self.request = self.grant = self.returning = self.accepted = self.cancel = None

    def prepare(self, request: BorrowRequest) -> BorrowRequest:
        """Recorded before the request is sent (plan section 7, grant step 1)."""
        if self.state is BorrowerState.BORROW_PREPARED and self.request == request:
            return request
        self._require(BorrowerState.PREFETCHED)
        if (request.borrower_id, request.profile_id, request.home_id, request.lineage_id,
                request.base_checkpoint_id, request.base_sha256) != (
                self.device_id, self.profile_id, self.home_id, self.lineage_id,
                self.checkpoint_id, self.checkpoint_sha256):
            raise ProtocolError("STALE_BASE", "The request does not match this PC's verified copy")
        self.request, self.state = request, BorrowerState.BORROW_PREPARED
        return request

    def granted(self, grant: BorrowGrant) -> BorrowGrant:
        """The permit, committed before the working copy opens writable (rule 3)."""
        if self.state is BorrowerState.BORROWING and self.grant == grant:
            return grant
        if self.state is BorrowerState.ABORTED and self.request is not None \
                and grant.checkout_id == self.request.checkout_id:
            raise ProtocolError("CANCELLED", "This PC cancelled the request; the late grant is refused")
        self._require(BorrowerState.BORROW_PREPARED)
        request = self.request
        if (grant.checkout_id, grant.borrower_id, grant.lineage_id, grant.base_checkpoint_id, grant.base_sha256) != (
                request.checkout_id, request.borrower_id, request.lineage_id, request.base_checkpoint_id,
                request.base_sha256):
            raise ProtocolError("STALE_AUTHORITY", "The grant does not match the prepared request")
        self.grant, self.state = grant, BorrowerState.BORROWING
        return grant

    def abort(self, cancel: BorrowCancel) -> BorrowCancel:
        """Only a request that never became writable can be cancelled; recorded before the cancel is sent."""
        if self.state is BorrowerState.ABORTED and self.cancel == cancel:
            return cancel
        self._require(BorrowerState.BORROW_PREPARED, BorrowerState.PREFETCHED)
        if self.request is None or cancel.checkout_id != self.request.checkout_id or cancel.borrower_id != self.device_id:
            raise ProtocolError("STALE_AUTHORITY", "Nothing to cancel")
        self.cancel, self.state = cancel, BorrowerState.ABORTED
        return cancel

    def seal(self) -> None:
        self._require(BorrowerState.BORROWING)
        self.state = BorrowerState.SEALED

    def unseal(self) -> None:
        self._require(BorrowerState.SEALED)
        self.state = BorrowerState.BORROWING

    def begin_return(self, message: ReturnBegin) -> ReturnBegin:
        """The final candidate is frozen; from here the working copy is read-only for good (rule 4)."""
        if self.state is BorrowerState.RETURNING and self.returning == message:
            return message
        self._require(BorrowerState.BORROWING, BorrowerState.SEALED)
        grant = self.grant
        if (message.checkout_id, message.borrower_id, message.lineage_id, message.epoch,
                message.parent_checkpoint_id) != (grant.checkout_id, self.device_id, grant.lineage_id, grant.epoch,
                                                  grant.base_checkpoint_id):
            raise ProtocolError("STALE_AUTHORITY", "The return does not match this PC's permit")
        self.returning, self.state = message, BorrowerState.RETURNING
        return message

    def handed_back(self, receipt: Accepted) -> Accepted:
        if self.state is BorrowerState.HANDED_BACK and self.accepted == receipt:
            return receipt
        self._require(BorrowerState.RETURNING)
        sent = self.returning
        if (receipt.return_id, receipt.checkout_id, receipt.candidate_sha256, receipt.epoch) != (
                sent.return_id, sent.checkout_id, sent.candidate_sha256, sent.epoch):
            raise ProtocolError("STALE_AUTHORITY", "The receipt is for another return")
        self.accepted, self.state = receipt, BorrowerState.HANDED_BACK
        self.lineage_id = receipt.lineage_id
        self.checkpoint_id, self.checkpoint_sha256 = receipt.checkpoint_id, receipt.candidate_sha256
        return receipt

    def needs_repair(self) -> None:
        if self.state in _IDLE:
            return
        self.state = BorrowerState.NEEDS_REPAIR

    def to_record(self) -> dict:
        def fields(message):
            return to_fields(message) if message is not None else None
        return {"version": RECORD_VERSION, "profile_id": self.profile_id, "home_id": self.home_id,
                "lineage_id": self.lineage_id, "device_id": self.device_id, "state": self.state.value,
                "checkpoint_id": self.checkpoint_id, "checkpoint_sha256": self.checkpoint_sha256,
                "request": fields(self.request), "grant": fields(self.grant), "returning": fields(self.returning),
                "accepted": fields(self.accepted), "cancel": fields(self.cancel)}

    @classmethod
    def from_record(cls, record: dict) -> "BorrowerModel":
        if not isinstance(record, dict) or record.get("version") != RECORD_VERSION:
            raise ValueError("Unsupported borrower authority record")
        model = cls(profile_id=record["profile_id"], home_id=record["home_id"], lineage_id=record["lineage_id"],
                    device_id=record["device_id"])
        model.state = BorrowerState(record["state"])
        if record["checkpoint_id"] is not None:
            _id(record["checkpoint_id"], "checkpoint_id")
            _hash(record["checkpoint_sha256"], "checkpoint_sha256")
        model.checkpoint_id, model.checkpoint_sha256 = record["checkpoint_id"], record["checkpoint_sha256"]
        for name, kind in (("request", BorrowRequest), ("grant", BorrowGrant), ("returning", ReturnBegin),
                           ("accepted", Accepted), ("cancel", BorrowCancel)):
            if record[name] is not None:
                setattr(model, name, from_fields(kind, record[name]))
        needs = {BorrowerState.BORROW_PREPARED: ("request",), BorrowerState.BORROWING: ("request", "grant"),
                 BorrowerState.SEALED: ("request", "grant"), BorrowerState.RETURNING: ("grant", "returning")}
        if any(getattr(model, name) is None for name in needs.get(model.state, ())):
            raise ValueError("Borrower authority record is inconsistent")
        return model
