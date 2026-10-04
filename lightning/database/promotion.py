"""Journal model and POSIX file-operation adapter for candidate promotion.

The state machine chooses restart actions but does not integrate them with an
authority store. The POSIX adapter supplies durable, same-directory primitives;
it does not decide when a caller may publish or clean up a referenced file.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, replace
from enum import IntEnum, StrEnum
from pathlib import Path, PurePath
from typing import Callable, Protocol, runtime_checkable


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
    RECORD_PUBLISHED = "record_published"
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
        if live_new and previous_old and files.candidate.state is FileState.MISSING:
            return RestartDecision(
                RestartAction.RECORD_PUBLISHED,
                "P2 candidate is live; record P3 after full verification",
            )
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


@dataclass(frozen=True)
class AcceptedCheckpoint:
    checkpoint_id: str
    sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.checkpoint_id, str) or not self.checkpoint_id
                or len(self.checkpoint_id) > 200):
            raise ValueError("Invalid accepted checkpoint ID")
        _validate_hash(self.sha256)


@dataclass(frozen=True)
class PromotionControlState:
    accepted: AcceptedCheckpoint | None
    journal: PromotionJournal | None


class PromotionJournalStore(Protocol):
    """Durable authority/journal contract used by the promotion service."""

    def read_state(self) -> PromotionControlState: ...

    def initialize_accepted(self, checkpoint_id: str, sha256: str) -> None: ...

    def prepare(self, journal: PromotionJournal) -> PromotionJournal: ...

    def advance(self, expected: PromotionJournal, updated: PromotionJournal) -> PromotionJournal: ...

    def commit_authority(self, expected: PromotionJournal) -> PromotionJournal: ...

    def mark_activated(self, expected: PromotionJournal) -> PromotionJournal: ...


class SqlitePromotionJournalStore:
    """Small FULL-synchronous control database for one profile's promotion.

    The caller must place it in private device-local storage and hold the
    profile operation/instance lock. It contains IDs and ciphertext hashes only.
    Journal and accepted checkpoint update together in one SQLite transaction.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        connection = self._connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS promotion_control ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "accepted_checkpoint_id TEXT, accepted_sha256 TEXT, journal_json TEXT, "
                "CHECK ((accepted_checkpoint_id IS NULL) = (accepted_sha256 IS NULL)))"
            )
            connection.execute(
                "INSERT OR IGNORE INTO promotion_control(singleton) VALUES (1)"
            )
        finally:
            connection.close()
        if not existed:
            os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            connection.close()
            raise
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @staticmethod
    def _row_state(row) -> PromotionControlState:
        if row is None:
            raise RuntimeError("Promotion control singleton is missing")
        accepted_id, accepted_hash, journal_json = row
        if (accepted_id is None) != (accepted_hash is None):
            raise RuntimeError("Accepted checkpoint record is incomplete")
        accepted = None if accepted_id is None else AcceptedCheckpoint(accepted_id, accepted_hash)
        if journal_json is None:
            journal = None
        else:
            try:
                def no_duplicates(pairs):
                    record = {}
                    for key, value in pairs:
                        if key in record:
                            raise ValueError("Duplicate promotion journal key")
                        record[key] = value
                    return record

                record = json.loads(journal_json, object_pairs_hook=no_duplicates)
                journal = PromotionJournal.from_record(record)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("Promotion journal is corrupt; writes must remain blocked") from exc
        return PromotionControlState(accepted, journal)

    @classmethod
    def _read_from(cls, connection: sqlite3.Connection) -> PromotionControlState:
        row = connection.execute(
            "SELECT accepted_checkpoint_id, accepted_sha256, journal_json "
            "FROM promotion_control WHERE singleton=1"
        ).fetchone()
        return cls._row_state(row)

    @staticmethod
    def _encoded(journal: PromotionJournal) -> str:
        return json.dumps(journal.to_record(), sort_keys=True, separators=(",", ":"))

    def read_state(self) -> PromotionControlState:
        connection = self._connect()
        try:
            return self._read_from(connection)
        finally:
            connection.close()

    def initialize_accepted(self, checkpoint_id: str, sha256: str) -> None:
        accepted = AcceptedCheckpoint(checkpoint_id, sha256)
        with self._transaction() as connection:
            state = self._read_from(connection)
            if state.accepted == accepted and state.journal is None:
                return
            if state.accepted is not None or state.journal is not None:
                raise RuntimeError("Initial accepted checkpoint is already established")
            connection.execute(
                "UPDATE promotion_control SET accepted_checkpoint_id=?, accepted_sha256=? "
                "WHERE singleton=1",
                (accepted.checkpoint_id, accepted.sha256),
            )

    def prepare(self, journal: PromotionJournal) -> PromotionJournal:
        if journal.phase is not PromotionPhase.PREPARED:
            raise ValueError("Prepared journal must start at P1")
        with self._transaction() as connection:
            state = self._read_from(connection)
            if state.journal == journal:
                return journal
            if state.journal is not None and state.journal.phase is not PromotionPhase.ACTIVATED:
                raise RuntimeError("Another promotion is still unresolved")
            if state.accepted != AcceptedCheckpoint(journal.old_checkpoint_id, journal.old_sha256):
                raise RuntimeError("Accepted checkpoint changed before promotion")
            connection.execute(
                "UPDATE promotion_control SET journal_json=? WHERE singleton=1",
                (self._encoded(journal),),
            )
        return journal

    def advance(self, expected: PromotionJournal, updated: PromotionJournal) -> PromotionJournal:
        if updated != expected.advance(updated.phase):
            raise ValueError("Journal update must be the next sequential phase")
        with self._transaction() as connection:
            state = self._read_from(connection)
            if state.journal == updated:
                return updated  # Idempotent retry after a lost commit response.
            if state.journal != expected:
                raise RuntimeError("Promotion journal changed concurrently")
            connection.execute(
                "UPDATE promotion_control SET journal_json=? WHERE singleton=1",
                (self._encoded(updated),),
            )
        return updated

    def commit_authority(self, expected: PromotionJournal) -> PromotionJournal:
        if expected.phase is not PromotionPhase.FILE_PUBLISHED:
            raise ValueError("Authority can be accepted only from P3")
        accepted_new = AcceptedCheckpoint(expected.new_checkpoint_id, expected.new_sha256)
        with self._transaction() as connection:
            state = self._read_from(connection)
            p4 = expected.advance(PromotionPhase.AUTHORITY_PUBLISHED)
            if state.journal == p4 and state.accepted == accepted_new:
                return p4
            if state.journal != expected:
                raise RuntimeError("Promotion journal changed before authority commit")
            accepted_old = AcceptedCheckpoint(expected.old_checkpoint_id, expected.old_sha256)
            if state.accepted != accepted_old:
                raise RuntimeError("Accepted checkpoint changed before authority commit")
            connection.execute(
                "UPDATE promotion_control SET accepted_checkpoint_id=?, accepted_sha256=?, journal_json=? "
                "WHERE singleton=1",
                (accepted_new.checkpoint_id, accepted_new.sha256, self._encoded(p4)),
            )
        return p4

    def mark_activated(self, expected: PromotionJournal) -> PromotionJournal:
        if expected.phase is PromotionPhase.ACTIVATED:
            return expected
        if expected.phase is not PromotionPhase.AUTHORITY_PUBLISHED:
            raise ValueError("Activation follows authority publication at P4")
        with self._transaction() as connection:
            state = self._read_from(connection)
            p5 = expected.advance(PromotionPhase.ACTIVATED)
            accepted_new = AcceptedCheckpoint(expected.new_checkpoint_id, expected.new_sha256)
            if state.journal == p5 and state.accepted == accepted_new:
                return p5
            if state.journal != expected or state.accepted != accepted_new:
                raise RuntimeError("Promotion authority changed before activation")
            connection.execute(
                "UPDATE promotion_control SET journal_json=? WHERE singleton=1",
                (self._encoded(p5),),
            )
        return p5


class PromotionBlocked(RuntimeError):
    """Evidence is missing, damaged or ambiguous; keep the profile non-writable."""


@dataclass(frozen=True)
class PromotionResult:
    operation_id: str | None
    checkpoint_id: str
    sha256: str
    phase: PromotionPhase | None


class CandidatePromotionService:
    """Journal and publish one already-staged, verified database candidate.

    `operation_gate` is mandatory and must quiesce the profile, drain active
    transactions and keep all writes fenced for the entire context. The verifier
    must validate SQLCipher/page integrity, schema/profile identity and the
    application structure for a file name in the adapter's directory. The
    activation callback prepares the new session only after P4 is durable; the
    gate must not admit finance writes until this method exits successfully.
    This layer never builds/restores/migrates candidate bytes itself.
    """

    def __init__(self, files: PromotionFileOps, store: PromotionJournalStore):
        self.files = files
        self.store = store

    def promote(
        self,
        *,
        operation_id: str,
        old_checkpoint_id: str,
        new_checkpoint_id: str,
        live_name: str,
        candidate_name: str,
        previous_name: str,
        operation_gate: AbstractContextManager,
        verify_database: Callable[[str], None],
        activate: Callable[[str, str], None],
    ) -> PromotionResult:
        """Begin or resume a promotion; callers must supply a drained gate."""
        with operation_gate:
            state = self.store.read_state()
            if state.journal is not None and state.journal.operation_id == operation_id:
                journal = state.journal
                if (journal.old_checkpoint_id != old_checkpoint_id
                        or journal.new_checkpoint_id != new_checkpoint_id
                        or journal.live_name != live_name
                        or journal.candidate_name != candidate_name
                        or journal.previous_name != previous_name):
                    raise PromotionBlocked("Operation ID was reused with different promotion details")
                return self._resume_locked(live_name, verify_database, activate)
            if state.journal is not None and state.journal.phase is not PromotionPhase.ACTIVATED:
                if state.journal.operation_id != operation_id:
                    raise PromotionBlocked("Resolve the existing promotion before starting another")

            state = self.store.read_state()
            if state.accepted is None:
                raise PromotionBlocked("No accepted home checkpoint is established")
            if state.accepted.checkpoint_id != old_checkpoint_id:
                raise PromotionBlocked("Expected base checkpoint is no longer accepted")
            old_hash = state.accepted.sha256
            live_hash = self.files.sha256(live_name)
            new_hash = self.files.sha256(candidate_name)
            if live_hash != old_hash:
                raise PromotionBlocked("Live database does not match accepted checkpoint")
            if new_hash is None:
                raise PromotionBlocked("Staged candidate is missing")
            journal = PromotionJournal(
                operation_id=operation_id,
                old_checkpoint_id=old_checkpoint_id,
                new_checkpoint_id=new_checkpoint_id,
                old_sha256=old_hash,
                new_sha256=new_hash,
                live_name=live_name,
                candidate_name=candidate_name,
                previous_name=previous_name,
                phase=PromotionPhase.STAGED,
            )
            self._verify_file(live_name, old_hash, verify_database)
            self._verify_file(candidate_name, new_hash, verify_database)
            prepared = journal.advance(PromotionPhase.PREPARED)
            self.store.prepare(prepared)
            return self._resume_locked(live_name, verify_database, activate)

    def recover(
        self,
        *,
        live_name: str,
        operation_gate: AbstractContextManager,
        verify_database: Callable[[str], None],
        activate: Callable[[str, str], None],
    ) -> PromotionResult:
        """Resolve durable journal state before the caller exposes finance writes."""
        with operation_gate:
            state = self.store.read_state()
            if state.accepted is None:
                raise PromotionBlocked("Accepted authority is unavailable")
            if state.journal is not None and state.journal.live_name != live_name:
                raise PromotionBlocked("Journal names another live profile file")
            return self._resume_locked(live_name, verify_database, activate)

    def _resume_locked(
        self,
        live_name: str,
        verify_database: Callable[[str], None],
        activate: Callable[[str, str], None],
    ) -> PromotionResult:
        # Each durable step is idempotent. A bounded loop prevents corrupt
        # journal implementations from keeping startup in an unbounded retry.
        for _ in range(8):
            state = self.store.read_state()
            accepted = state.accepted
            if accepted is None:
                raise PromotionBlocked("Accepted authority is unavailable")
            journal = state.journal
            observations = self._observe(live_name, journal)
            decision = decide_restart(
                journal, observations, accepted_sha256=accepted.sha256,
                authority_readable=True,
            )
            if decision.action is RestartAction.BLOCK_REPAIR:
                raise PromotionBlocked(decision.reason)

            if decision.action is RestartAction.KEEP_CURRENT:
                if journal is not None:
                    checkpoint_id = journal.old_checkpoint_id
                else:
                    checkpoint_id = accepted.checkpoint_id
                self._verify_file(live_name, accepted.sha256, verify_database)
                activate(checkpoint_id, live_name)
                return PromotionResult(
                    journal.operation_id if journal else None,
                    checkpoint_id,
                    accepted.sha256,
                    journal.phase if journal else None,
                )

            if journal is None:
                raise PromotionBlocked("A restart action requires a durable promotion journal")

            if decision.action is RestartAction.PROTECT_PREVIOUS:
                self._verify_file(journal.live_name, journal.old_sha256, verify_database)
                self._verify_file(journal.candidate_name, journal.new_sha256, verify_database)
                previous_hash = self.files.sha256(journal.previous_name)
                if previous_hash is None:
                    self.files.copy_exclusive(journal.live_name, journal.previous_name)
                elif previous_hash != journal.old_sha256:
                    raise PromotionBlocked("Named previous checkpoint conflicts with journal")
                self._verify_file(journal.previous_name, journal.old_sha256, verify_database)
                updated = journal.advance(PromotionPhase.PREVIOUS_PROTECTED)
                self.store.advance(journal, updated)
                continue

            if decision.action is RestartAction.RETRY_PUBLISH:
                if journal.phase not in (PromotionPhase.PREVIOUS_PROTECTED,
                                         PromotionPhase.FILE_PUBLISHED):
                    raise PromotionBlocked("Publication retry is allowed only after P2 or P3")
                self._verify_file(journal.live_name, journal.old_sha256, verify_database)
                self._verify_file(journal.candidate_name, journal.new_sha256, verify_database)
                self._verify_file(journal.previous_name, journal.old_sha256, verify_database)
                self.files.atomic_replace(journal.candidate_name, journal.live_name)
                continue

            if decision.action is RestartAction.RECORD_PUBLISHED:
                self._verify_file(journal.live_name, journal.new_sha256, verify_database)
                self._verify_file(journal.previous_name, journal.old_sha256, verify_database)
                updated = journal.advance(PromotionPhase.FILE_PUBLISHED)
                self.store.advance(journal, updated)
                continue

            if decision.action is RestartAction.VERIFY_AND_COMMIT_AUTHORITY:
                self._verify_file(journal.live_name, journal.new_sha256, verify_database)
                self._verify_file(journal.previous_name, journal.old_sha256, verify_database)
                self.store.commit_authority(journal)
                continue

            if decision.action is RestartAction.ACTIVATE_NEW:
                new_checkpoint = AcceptedCheckpoint(journal.new_checkpoint_id, journal.new_sha256)
                if accepted != new_checkpoint:
                    raise PromotionBlocked("New file is not accepted authority")
                self._verify_file(journal.live_name, journal.new_sha256, verify_database)
                self._verify_file(journal.previous_name, journal.old_sha256, verify_database)
                activate(journal.new_checkpoint_id, journal.live_name)
                if journal.phase is PromotionPhase.AUTHORITY_PUBLISHED:
                    journal = self.store.mark_activated(journal)
                return PromotionResult(journal.operation_id, journal.new_checkpoint_id,
                                       journal.new_sha256, journal.phase)

        raise PromotionBlocked("Promotion did not converge within its bounded restart steps")

    def _observe(self, live_name: str, journal: PromotionJournal | None) -> FileObservations:
        if journal is None:
            # Only live matters without a journal; absent auxiliary names are
            # placeholders and are never used as authority evidence.
            return FileObservations(self._file_observation(live_name),
                                    FileObservation.missing(), FileObservation.missing())
        return FileObservations(
            self._file_observation(journal.live_name),
            self._file_observation(journal.candidate_name),
            self._file_observation(journal.previous_name),
        )

    def _file_observation(self, name: str) -> FileObservation:
        try:
            value = self.files.sha256(name)
            return FileObservation.missing() if value is None else FileObservation.hashed(value)
        except (OSError, ValueError, RuntimeError):
            return FileObservation.unknown()

    def _verify_file(self, name: str, expected_hash: str, verifier: Callable[[str], None]) -> None:
        try:
            before = self.files.sha256(name)
        except (OSError, ValueError, RuntimeError) as exc:
            raise PromotionBlocked(f"Could not inspect promotion file {name}") from exc
        if before != expected_hash:
            raise PromotionBlocked(f"Promotion file hash does not match journal: {name}")
        verifier(name)
        after = self.files.sha256(name)
        if after != expected_hash:
            raise PromotionBlocked(f"Promotion file changed during verification: {name}")
