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
)


class HomeState(StrEnum):
    AT_HOME = "AT_HOME"
    LENT = "LENT"
    RETURN_RECEIVED = "RETURN_RECEIVED"


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

    def _remember(self, operation_id: str, message: object) -> None:
        previous = self._operations.get(operation_id)
        if previous is not None and previous != message:
            raise ProtocolError("REPLAY_CONFLICT", "Operation ID reused for different content")
        self._operations[operation_id] = message

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
            self._remember(request.operation_id, request)
            if request.checkout_id in self._cancellations:
                raise ProtocolError("CANCELLED", "This checkout was durably cancelled by the borrower")
            prior = self._grants.get(request.checkout_id)
            if prior is not None:
                if prior.request != request:
                    raise ProtocolError("REPLAY_CONFLICT", "Checkout ID reused for different content")
                return prior.grant
            if self.state is not HomeState.AT_HOME:
                raise ProtocolError("ALREADY_LENT", "Another checkout or return holds authority")
            if (request.base_checkpoint_id, request.base_sha256) != (
                self.checkpoint_id, self.checkpoint_sha256
            ):
                raise ProtocolError("STALE_BASE", "Prefetch does not match the accepted checkpoint")
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
            self._remember(message.operation_id, message)
            if message.checkout_id in self._cancellations:
                raise ProtocolError("CANCELLED", "Cancelled checkout cannot be activated")
            active = self.active
            if (self.state is not HomeState.LENT or active is None
                    or message.checkout_id != active.grant.checkout_id
                    or message.borrower_id != active.grant.borrower_id
                    or message.epoch != active.grant.epoch):
                raise ProtocolError("STALE_AUTHORITY", "Activation does not match the active grant")
            active.activated = True
            return active.grant

    def cancel(self, message: BorrowCancel, *, authenticated_peer: str) -> Cancelled:
        """Caller asserts it durably recorded ABORTED before sending this."""
        with self._lock:
            self._peer(message.borrower_id, authenticated_peer)
            self._remember(message.operation_id, message)
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
            self._remember(message.operation_id, message)
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
