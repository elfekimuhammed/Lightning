"""Pure journal model for crash-safe database candidate promotion.

This module deliberately does not touch the filesystem or the authority store.
It validates durable intent and chooses a restart action from observed hashes;
platform-specific POSIX/Windows adapters and publication are separate work.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum, StrEnum
from pathlib import PurePath
from typing import Protocol, runtime_checkable


class PromotionPhase(IntEnum):
    """Durable publication milestones from proposal P0 through P5."""

    STAGED = 0                 # P0: immutable candidate verified; no live change
    PREPARED = 1               # P1: operation intent recorded
    PREVIOUS_PROTECTED = 2     # P2: verified old checkpoint is durable
    FILE_PUBLISHED = 3         # P3: candidate is at the live path
    AUTHORITY_PUBLISHED = 4    # P4: accepted version and receipt are committed
    ACTIVATED = 5              # P5: new session generation may write


@dataclass(frozen=True)
class PromotionJournal:
    """Versioned control-store record. Hashes are ciphertext SHA-256 values."""

    operation_id: str
    old_checkpoint_id: str
    new_checkpoint_id: str
    old_sha256: str
    new_sha256: str
    live_name: str
    candidate_name: str
    previous_name: str
    phase: PromotionPhase
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported promotion journal schema")
        for name, value in (
            ("operation_id", self.operation_id),
            ("old_checkpoint_id", self.old_checkpoint_id),
            ("new_checkpoint_id", self.new_checkpoint_id),
        ):
            if not isinstance(value, str) or not value or len(value) > 200:
                raise ValueError(f"Invalid {name}")
        if self.old_checkpoint_id == self.new_checkpoint_id:
            raise ValueError("A promotion must advance to a new checkpoint")
        _validate_hash(self.old_sha256)
        _validate_hash(self.new_sha256)
        if self.old_sha256 == self.new_sha256:
            raise ValueError("Old and new database hashes must differ")
        names = (self.live_name, self.candidate_name, self.previous_name)
        if len(set(names)) != 3:
            raise ValueError("Promotion file names must be distinct")
        for name in names:
            _validate_file_name(name)
        if not isinstance(self.phase, PromotionPhase):
            raise ValueError("Invalid promotion phase")

    def advance(self, phase: PromotionPhase) -> PromotionJournal:
        """Return the next sequential record; callers persist it durably."""
        if phase != self.phase + 1:
            raise ValueError("Promotion phases must advance one durable step at a time")
        return replace(self, phase=phase)

    def to_record(self) -> dict[str, str | int]:
        """Produce a primitive-only mapping suitable for a control-store row."""
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "old_checkpoint_id": self.old_checkpoint_id,
            "new_checkpoint_id": self.new_checkpoint_id,
            "old_sha256": self.old_sha256,
            "new_sha256": self.new_sha256,
            "live_name": self.live_name,
            "candidate_name": self.candidate_name,
            "previous_name": self.previous_name,
            "phase": int(self.phase),
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> PromotionJournal:
        """Parse and validate a control-store row without coercing bad values."""
        required = {
            "schema_version", "operation_id", "old_checkpoint_id", "new_checkpoint_id",
            "old_sha256", "new_sha256", "live_name", "candidate_name", "previous_name", "phase",
        }
        if set(record) != required:
            raise ValueError("Promotion journal fields do not match schema")
        if type(record["schema_version"]) is not int or type(record["phase"]) is not int:
            raise ValueError("Promotion journal versions must be integers")
        try:
            phase = PromotionPhase(record["phase"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Unknown promotion phase") from exc
        return cls(
            operation_id=_record_str(record, "operation_id"),
            old_checkpoint_id=_record_str(record, "old_checkpoint_id"),
            new_checkpoint_id=_record_str(record, "new_checkpoint_id"),
            old_sha256=_record_str(record, "old_sha256"),
            new_sha256=_record_str(record, "new_sha256"),
            live_name=_record_str(record, "live_name"),
            candidate_name=_record_str(record, "candidate_name"),
            previous_name=_record_str(record, "previous_name"),
            phase=phase,
            schema_version=record["schema_version"],
        )


def _record_str(record: dict[str, object], key: str) -> str:
    value = record[key]
    if not isinstance(value, str):
        raise ValueError(f"Promotion journal {key} must be text")
    return value


def _validate_hash(value: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise ValueError("Expected a lowercase SHA-256 hex digest")


def _validate_file_name(value: str) -> None:
    if (not isinstance(value, str) or not value or len(value) > 255
            or PurePath(value).name != value or value in {".", ".."}
            or "/" in value or "\\" in value or "\x00" in value):
        raise ValueError("Promotion paths must be safe file names in one directory")


@runtime_checkable
class PromotionFileOps(Protocol):
    """Platform adapter contract; implementations must report durability errors.

    The three names passed to this protocol are sibling names below one trusted
    directory. Implementations must refuse cross-volume moves, flush file data
    and directory metadata where supported, and never silently ignore a flush
    failure. This interface does not claim those guarantees itself.
    """

    def sha256(self, name: str) -> str | None:
        """Return a file digest, None if absent; raise on unreadable/unsafe file."""
        ...

    def copy_exclusive(self, source: str, destination: str) -> None:
        """Copy without replacing; flush destination contents and metadata."""
        ...

    def atomic_replace(self, source: str, destination: str) -> None:
        """Atomically replace a sibling path and durably flush affected metadata."""
        ...

    def unlink(self, name: str) -> None:
        """Remove only an adapter-owned, unreferenced file and flush metadata."""
        ...


class FileState(StrEnum):
    HASHED = "hashed"
    MISSING = "missing"
    UNKNOWN = "unknown"  # I/O, permission or unsafe-path failure; never infer absence


@dataclass(frozen=True)
class FileObservation:
    state: FileState
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, FileState):
            raise ValueError("File observation state must be a FileState")
        if self.state is FileState.HASHED:
            if self.sha256 is None:
                raise ValueError("Hashed observation requires a digest")
            _validate_hash(self.sha256)
        elif self.sha256 is not None:
            raise ValueError("Only a hashed observation can carry a digest")

    @classmethod
    def hashed(cls, value: str) -> FileObservation:
        return cls(FileState.HASHED, value)

    @classmethod
    def missing(cls) -> FileObservation:
        return cls(FileState.MISSING)

    @classmethod
    def unknown(cls) -> FileObservation:
        return cls(FileState.UNKNOWN)


@dataclass(frozen=True)
class FileObservations:
    live: FileObservation
    candidate: FileObservation
    previous: FileObservation


class RestartAction(StrEnum):
    KEEP_CURRENT = "keep_current"
    PROTECT_PREVIOUS = "protect_previous"
    RETRY_PUBLISH = "retry_publish"
    VERIFY_AND_COMMIT_AUTHORITY = "verify_and_commit_authority"
    ACTIVATE_NEW = "activate_new"
    BLOCK_REPAIR = "block_repair"


@dataclass(frozen=True)
class RestartDecision:
    action: RestartAction
    reason: str


def decide_restart(
    journal: PromotionJournal | None,
    files: FileObservations,
    *,
    accepted_sha256: str | None,
    authority_readable: bool = True,
) -> RestartDecision:
    """Choose a safe deterministic action; never performs file/control writes.

    Accepted authority is authoritative after P4: an old file cannot be
    reactivated. Before P4, all mismatches or ambiguity block activation. A P3
    new live file can finish P4 only after its content is reverified by caller.
    """
    if not authority_readable or accepted_sha256 is None:
        return _block("Accepted authority state is unavailable")
    try:
        _validate_hash(accepted_sha256)
    except ValueError:
        return _block("Accepted authority hash is malformed")

    if journal is None:
        if files.live.state is FileState.HASHED and files.live.sha256 == accepted_sha256:
            return RestartDecision(RestartAction.KEEP_CURRENT, "No promotion journal; live matches accepted authority")
        return _block("No journal and live file does not match accepted authority")

    observations = (files.live, files.candidate, files.previous)
    if any(item.state is FileState.UNKNOWN for item in observations):
        return _block("A named promotion file could not be inspected safely")

    old = journal.old_sha256
    new = journal.new_sha256
    live_old = _is_hash(files.live, old)
    live_new = _is_hash(files.live, new)
    candidate_new = _is_hash(files.candidate, new)
    previous_old = _is_hash(files.previous, old)
    authority_old = accepted_sha256 == old
    authority_new = accepted_sha256 == new

    if not authority_old and not authority_new:
        return _block("Accepted authority matches neither journal checkpoint")

    # Once P4 commits, never fall back to old data. P5 merely confirms activation.
    if authority_new:
        if journal.phase < PromotionPhase.AUTHORITY_PUBLISHED:
            return _block("Authority advanced ahead of its durable journal phase")
        if live_new and previous_old:
            return RestartDecision(RestartAction.ACTIVATE_NEW, "Accepted authority and live file match new checkpoint")
        return _block("Accepted new authority needs matching live and retained previous checkpoints")

    # P0 has no replacement intent to resume: an untouched accepted live file
    # remains usable, and any staged candidate is unreferenced for authority.
    if journal.phase is PromotionPhase.STAGED:
        if live_old:
            return RestartDecision(RestartAction.KEEP_CURRENT, "P0 candidate is not yet an authority transition")
        return _block("P0 live file differs from accepted authority")

    # P1/P2/P3 while accepted authority remains old: the operation is incomplete.
    # Retry only with all required exact-hash evidence; every other shape blocks.
    if journal.phase in (PromotionPhase.PREPARED, PromotionPhase.PREVIOUS_PROTECTED):
        if journal.phase is PromotionPhase.PREPARED:
            if live_old and candidate_new and (files.previous.state is FileState.MISSING or previous_old):
                return RestartDecision(
                    RestartAction.PROTECT_PREVIOUS,
                    "P1 must durably establish the named previous checkpoint before P2",
                )
            return _block("P1 files do not match the journal")
        if live_old and candidate_new and previous_old:
            return RestartDecision(RestartAction.RETRY_PUBLISH, "Old authority intact; exact candidate and protection are present")
        return _block("Pre-publication files do not match the journal")

    if journal.phase is PromotionPhase.FILE_PUBLISHED:
        if live_new and previous_old:
            return RestartDecision(
                RestartAction.VERIFY_AND_COMMIT_AUTHORITY,
                "P3 file is published; reverify it before committing P4",
            )
        if live_old and candidate_new and previous_old:
            return RestartDecision(RestartAction.RETRY_PUBLISH, "Old live remains; exact candidate and backup permit retry")
        return _block("P3 file observations are incomplete or ambiguous")

    return _block("Journal phase and accepted authority disagree")


def _is_hash(observation: FileObservation, expected: str) -> bool:
    return observation.state is FileState.HASHED and observation.sha256 == expected


def _block(reason: str) -> RestartDecision:
    return RestartDecision(RestartAction.BLOCK_REPAIR, reason)
