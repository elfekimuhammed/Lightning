"""Bounded, versioned value objects for the first checkout protocol.

This is the in-process contract for task 05a. Transport authentication and
durable records arrive in later tasks; parsing these values never grants trust.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


PROTOCOL_VERSION = 1
CONTROL_SCHEMA_VERSION = 1
MAX_MESSAGE_BYTES = 16 * 1024
MAX_CANDIDATE_BYTES = 1024 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KEY_ID = re.compile(r"[0-9a-f]{16}\Z")


def _id(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 36:
        raise ValueError(f"Invalid {name}")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {name}") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f"Invalid {name}")


def _hash(value: str, name: str) -> None:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"Invalid {name}")


def _natural(value: int, name: str, *, minimum: int = 0, maximum: int = 2**63 - 1) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")


class MessageKind(StrEnum):
    BORROW_REQUEST = "BorrowRequest"
    BORROW_GRANT = "BorrowGrant"
    BORROW_ACTIVATED = "BorrowActivated"
    BORROW_CANCEL = "BorrowCancel"
    CANCELLED = "Cancelled"
    RETURN_BEGIN = "ReturnBegin"
    RECEIVED = "Received"
    ACCEPTED = "Accepted"


@dataclass(frozen=True)
class Compatibility:
    protocol: int
    control_schema: int
    ledger_schema: int
    cipher_format: int
    key_id: str
    write_capability: int

    def __post_init__(self) -> None:
        for name in ("protocol", "control_schema", "ledger_schema", "cipher_format", "write_capability"):
            _natural(getattr(self, name), name, minimum=1, maximum=65535)
        if not isinstance(self.key_id, str) or _KEY_ID.fullmatch(self.key_id) is None:
            raise ValueError("Invalid key_id")

    def require_same(self, other: Compatibility) -> None:
        if self != other:
            raise ValueError("Incompatible protocol, schema, cipher, key or write capability")


@dataclass(frozen=True)
class BorrowRequest:
    operation_id: str
    checkout_id: str
    profile_id: str
    home_id: str
    lineage_id: str
    borrower_id: str
    base_checkpoint_id: str
    base_sha256: str
    compatibility: Compatibility

    def __post_init__(self) -> None:
        for name in ("operation_id", "checkout_id", "profile_id", "home_id", "lineage_id", "borrower_id", "base_checkpoint_id"):
            _id(getattr(self, name), name)
        _hash(self.base_sha256, "base_sha256")
        if not isinstance(self.compatibility, Compatibility):
            raise ValueError("Invalid compatibility")


@dataclass(frozen=True)
class BorrowGrant:
    checkout_id: str
    borrower_id: str
    lineage_id: str
    epoch: int
    base_checkpoint_id: str
    base_sha256: str

    def __post_init__(self) -> None:
        for name in ("checkout_id", "borrower_id", "lineage_id", "base_checkpoint_id"):
            _id(getattr(self, name), name)
        _natural(self.epoch, "epoch", minimum=1)
        _hash(self.base_sha256, "base_sha256")


@dataclass(frozen=True)
class BorrowActivated:
    operation_id: str
    checkout_id: str
    borrower_id: str
    epoch: int

    def __post_init__(self) -> None:
        for name in ("operation_id", "checkout_id", "borrower_id"):
            _id(getattr(self, name), name)
        _natural(self.epoch, "epoch", minimum=1)


@dataclass(frozen=True)
class BorrowCancel:
    operation_id: str
    checkout_id: str
    borrower_id: str
    never_activated: bool

    def __post_init__(self) -> None:
        for name in ("operation_id", "checkout_id", "borrower_id"):
            _id(getattr(self, name), name)
        if self.never_activated is not True:
            raise ValueError("Cancel requires the borrower's never-activated assertion")


@dataclass(frozen=True)
class Cancelled:
    checkout_id: str
    borrower_id: str
    epoch: int

    def __post_init__(self) -> None:
        _id(self.checkout_id, "checkout_id")
        _id(self.borrower_id, "borrower_id")
        _natural(self.epoch, "epoch")


@dataclass(frozen=True)
class ReturnBegin:
    operation_id: str
    return_id: str
    checkout_id: str
    borrower_id: str
    lineage_id: str
    epoch: int
    parent_checkpoint_id: str
    candidate_sha256: str
    candidate_size: int

    def __post_init__(self) -> None:
        for name in ("operation_id", "return_id", "checkout_id", "borrower_id", "lineage_id", "parent_checkpoint_id"):
            _id(getattr(self, name), name)
        _natural(self.epoch, "epoch", minimum=1)
        _hash(self.candidate_sha256, "candidate_sha256")
        _natural(self.candidate_size, "candidate_size", minimum=1, maximum=MAX_CANDIDATE_BYTES)


@dataclass(frozen=True)
class Received:
    return_id: str
    checkout_id: str
    candidate_sha256: str

    def __post_init__(self) -> None:
        _id(self.return_id, "return_id")
        _id(self.checkout_id, "checkout_id")
        _hash(self.candidate_sha256, "candidate_sha256")


@dataclass(frozen=True)
class Accepted:
    return_id: str
    checkout_id: str
    checkpoint_id: str
    candidate_sha256: str
    lineage_id: str
    epoch: int

    def __post_init__(self) -> None:
        for name in ("return_id", "checkout_id", "checkpoint_id", "lineage_id"):
            _id(getattr(self, name), name)
        _hash(self.candidate_sha256, "candidate_sha256")
        _natural(self.epoch, "epoch", minimum=1)


Message = BorrowRequest | BorrowGrant | BorrowActivated | BorrowCancel | Cancelled | ReturnBegin | Received | Accepted
_TYPES: dict[MessageKind, type] = {
    MessageKind.BORROW_REQUEST: BorrowRequest,
    MessageKind.BORROW_GRANT: BorrowGrant,
    MessageKind.BORROW_ACTIVATED: BorrowActivated,
    MessageKind.BORROW_CANCEL: BorrowCancel,
    MessageKind.CANCELLED: Cancelled,
    MessageKind.RETURN_BEGIN: ReturnBegin,
    MessageKind.RECEIVED: Received,
    MessageKind.ACCEPTED: Accepted,
}
_KINDS = {value: key for key, value in _TYPES.items()}


def encode_message(message: Message) -> bytes:
    kind = _KINDS.get(type(message))
    if kind is None:
        raise ValueError("Unknown protocol message")
    data = {"kind": kind.value, "protocol": PROTOCOL_VERSION, **asdict(message)}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ValueError("Protocol message too large")
    return encoded


def decode_message(blob: bytes) -> Message:
    if not isinstance(blob, bytes) or len(blob) > MAX_MESSAGE_BYTES:
        raise ValueError("Protocol message too large or not bytes")
    try:
        def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate protocol JSON key")
                result[key] = value
            return result

        data: Any = json.loads(blob, object_pairs_hook=no_duplicates)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed protocol JSON") from exc
    if (not isinstance(data, dict) or type(data.get("protocol")) is not int
            or data["protocol"] != PROTOCOL_VERSION):
        raise ValueError("Unsupported protocol version")
    try:
        kind = MessageKind(data.pop("kind"))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Unknown protocol message kind") from exc
    data.pop("protocol")
    cls = _TYPES[kind]
    expected = set(cls.__dataclass_fields__)
    if set(data) != expected:
        raise ValueError("Protocol message fields do not match schema")
    if kind is MessageKind.BORROW_REQUEST:
        compat = data["compatibility"]
        if not isinstance(compat, dict) or set(compat) != set(Compatibility.__dataclass_fields__):
            raise ValueError("Compatibility fields do not match schema")
        data["compatibility"] = Compatibility(**compat)
    return cls(**data)
