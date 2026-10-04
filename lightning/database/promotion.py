"""Journal model and POSIX file-operation adapter for candidate promotion.

The state machine chooses restart actions but does not integrate them with an
authority store. The POSIX adapter supplies durable, same-directory primitives;
it does not decide when a caller may publish or clean up a referenced file.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, replace
from enum import IntEnum, StrEnum
from pathlib import Path, PurePath
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
        """Remove a caller-confirmed unreferenced sibling and flush metadata."""
        ...


class PosixPromotionFileOps:
    """POSIX sibling-file operations rooted at one already-created directory.

    Names are always validated as plain siblings and opened relative to a held
    directory descriptor with no-follow semantics. The caller must hold its
    profile operation gate and prove a file is unreferenced before unlinking.
    The adapter never follows file symlinks and refuses regular files with more
    than one hard link. Any data or directory fsync failure is raised.
    """

    def __init__(self, directory: str | Path):
        if os.name == "nt":
            raise OSError("PosixPromotionFileOps is unavailable on Windows")
        path = Path(os.path.abspath(directory))
        probe = Path(path.anchor)
        for part in path.parts[1:]:
            probe = probe / part
            if probe.is_symlink():
                raise ValueError("Promotion directory path must not contain symbolic links")
        path = path.resolve(strict=True)
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Promotion root must be a directory")
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        directory_fd = os.open(path, flags)
        try:
            opened_info = os.fstat(directory_fd)
            named_info = os.stat(path, follow_symlinks=False)
            if (not stat.S_ISDIR(named_info.st_mode)
                    or (opened_info.st_dev, opened_info.st_ino) != (info.st_dev, info.st_ino)
                    or (named_info.st_dev, named_info.st_ino) != (info.st_dev, info.st_ino)):
                raise OSError("Promotion directory changed while opening")
        except BaseException:
            os.close(directory_fd)
            raise
        self._directory_fd = directory_fd
        self._directory_path = path
        self._directory_identity = (info.st_dev, info.st_ino)
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            os.close(self._directory_fd)
            self._closed = True

    def __enter__(self) -> PosixPromotionFileOps:
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Promotion file adapter is closed")
        try:
            opened = os.fstat(self._directory_fd)
            named = os.stat(self._directory_path, follow_symlinks=False)
        except OSError as exc:
            raise OSError("Promotion directory path is no longer available") from exc
        if (not stat.S_ISDIR(named.st_mode)
                or (opened.st_dev, opened.st_ino) != self._directory_identity
                or (named.st_dev, named.st_ino) != self._directory_identity):
            raise OSError("Promotion directory path changed after adapter construction")

    @staticmethod
    def _validate_name(name: str) -> str:
        _validate_file_name(name)
        return name

    @staticmethod
    def _require_single_regular(info: os.stat_result, name: str) -> None:
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Promotion path is not a regular file: {name}")
        if info.st_nlink != 1:
            raise ValueError(f"Hard-linked promotion files are not allowed: {name}")

    def _open_regular(self, name: str, flags: int) -> tuple[int, os.stat_result]:
        self._ensure_open()
        name = self._validate_name(name)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(name, flags | nofollow | getattr(os, "O_NONBLOCK", 0), dir_fd=self._directory_fd)
        try:
            info = os.fstat(fd)
            self._require_single_regular(info, name)
            named = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
            self._require_single_regular(named, name)
            if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                raise OSError(f"Promotion path changed while opening: {name}")
            return fd, info
        except BaseException:
            os.close(fd)
            raise

    def _fsync_directory(self) -> None:
        self._ensure_open()
        os.fsync(self._directory_fd)

    def sha256(self, name: str) -> str | None:
        name = self._validate_name(name)
        try:
            fd, before = self._open_regular(name, os.O_RDONLY)
        except FileNotFoundError:
            return None
        digest = hashlib.sha256()
        try:
            while True:
                block = os.read(fd, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
            after = os.fstat(fd)
            named = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
            self._require_single_regular(named, name)
            stable_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            stable_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            if stable_before != stable_after or (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino):
                raise OSError(f"Promotion file changed while hashing: {name}")
            return digest.hexdigest()
        finally:
            os.close(fd)

    def copy_exclusive(self, source: str, destination: str) -> None:
        source = self._validate_name(source)
        destination = self._validate_name(destination)
        if source == destination:
            raise ValueError("Copy source and destination must differ")
        source_fd, source_before = self._open_regular(source, os.O_RDONLY)
        destination_fd = None
        created_identity = None
        try:
            destination_fd = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=self._directory_fd,
            )
            created = os.fstat(destination_fd)
            self._require_single_regular(created, destination)
            created_identity = (created.st_dev, created.st_ino)
            while True:
                block = os.read(source_fd, 1024 * 1024)
                if not block:
                    break
                view = memoryview(block)
                while view:
                    written = os.write(destination_fd, view)
                    if written <= 0:
                        raise OSError("Short write while copying promotion file")
                    view = view[written:]
            os.fsync(destination_fd)
            source_after = os.fstat(source_fd)
            source_named = os.stat(source, dir_fd=self._directory_fd, follow_symlinks=False)
            self._require_single_regular(source_named, source)
            stable_before = (
                source_before.st_dev, source_before.st_ino, source_before.st_size,
                source_before.st_mtime_ns, source_before.st_ctime_ns,
            )
            stable_after = (
                source_after.st_dev, source_after.st_ino, source_after.st_size,
                source_after.st_mtime_ns, source_after.st_ctime_ns,
            )
            if stable_before != stable_after or (source_named.st_dev, source_named.st_ino) != (
                source_after.st_dev, source_after.st_ino
            ):
                raise OSError(f"Promotion source changed while copying: {source}")
            os.close(destination_fd)
            destination_fd = None
            self._fsync_directory()
        except BaseException:
            if destination_fd is not None:
                os.close(destination_fd)
                destination_fd = None
            if created_identity is not None:
                try:
                    current = os.stat(destination, dir_fd=self._directory_fd, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == created_identity:
                        os.unlink(destination, dir_fd=self._directory_fd)
                        try:
                            self._fsync_directory()
                        except OSError:
                            pass
                except FileNotFoundError:
                    pass
            raise
        finally:
            os.close(source_fd)

    def atomic_replace(self, source: str, destination: str) -> None:
        source = self._validate_name(source)
        destination = self._validate_name(destination)
        if source == destination:
            raise ValueError("Replace source and destination must differ")
        source_fd, source_info = self._open_regular(source, os.O_RDONLY)
        destination_fd = None
        try:
            destination_fd, destination_info = self._open_regular(destination, os.O_RDONLY)
            # Recheck the names immediately before the rename. The process-level
            # operation gate excludes Lightning writers; dir_fd/no-follow keeps
            # resolution inside the pinned directory.
            self._assert_name_is_inode(source, source_info)
            self._assert_name_is_inode(destination, destination_info)
            os.fsync(source_fd)
            os.replace(
                source, destination,
                src_dir_fd=self._directory_fd,
                dst_dir_fd=self._directory_fd,
            )
            self._fsync_directory()
            published = os.stat(destination, dir_fd=self._directory_fd, follow_symlinks=False)
            if (published.st_dev, published.st_ino) != (source_info.st_dev, source_info.st_ino):
                raise OSError("Published path does not refer to the opened candidate")
        finally:
            if destination_fd is not None:
                os.close(destination_fd)
            os.close(source_fd)

    def _assert_name_is_inode(self, name: str, info: os.stat_result) -> None:
        current = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
        self._require_single_regular(current, name)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise OSError(f"Promotion path changed before publication: {name}")

    def unlink(self, name: str) -> None:
        name = self._validate_name(name)
        fd, opened = self._open_regular(name, os.O_RDONLY)
        try:
            self._assert_name_is_inode(name, opened)
            os.unlink(name, dir_fd=self._directory_fd)
            self._fsync_directory()
        finally:
            os.close(fd)


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
