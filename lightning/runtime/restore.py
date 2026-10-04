"""Encrypted backup restore preparation and durable promotion."""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import shutil
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from lightning.database.backup import backup, list_backups
from lightning.database.connection import Database
from lightning.database.migrator import inspect_schema, migrate
from lightning.database.promotion import (
    CandidatePromotionService, PromotionBlocked, PromotionPhase,
    SqlitePromotionJournalStore,
)
from lightning.database.seed import seed
from lightning.database.snapshot import verify_connection
from lightning.database.staging import stage_database
from lightning.ownership_migration import migrate_legacy_ownership
from lightning.runtime.paths import ProfilePaths
from lightning.security.keys import unwrap_key
from .session import ProfileError, read_slot


@contextmanager
def _held_profile_lock(lock):
    """Expose the already-acquired process gate to the promotion service."""
    if not lock.acquired:
        raise RuntimeError("Profile instance lock is not held")
    yield


class EncryptedBackupRestorer:
    """Keep restore I/O out of the live session lifecycle controller."""

    def __init__(self, session):
        self.session = session

    @staticmethod
    def _sidecars(path: Path) -> tuple[Path, ...]:
        return tuple(Path(str(path) + suffix) for suffix in ("-wal", "-journal", "-shm"))

    @classmethod
    def _require_clean_database_file(cls, path: Path) -> None:
        if path.is_symlink():
            raise ProfileError("Restore is blocked because a database path is a symbolic link.")
        try:
            info = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise ProfileError("Restore is blocked because a database file cannot be inspected.") from exc
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ProfileError("Restore is blocked because a database file is not a private regular file.")
        if any(sidecar.exists() or sidecar.is_symlink() for sidecar in cls._sidecars(path)):
            raise ProfileError("Restore is blocked while SQLite journal or WAL sidecars exist. Close Lightning and retry after the database is cleanly checkpointed.")

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _verify_file(cls, path: Path, key: bytes) -> None:
        cls._require_clean_database_file(path)
        db = Database(path, key=key, read_only=True)
        try:
            if not db.has_table("schema_migrations"):
                raise ProfileError("The selected file is not a Lightning database.")
            inspect_schema(db)
            verify_connection(db.conn, encrypted=True)
        finally:
            db.close()
        cls._require_clean_database_file(path)

    @staticmethod
    def _restore_journal_paths(paths: ProfilePaths) -> tuple[Path, ...]:
        return tuple(paths.data_dir.glob(".lightning-restore-*.sqlite"))

    @staticmethod
    def _restore_marker_paths(paths: ProfilePaths) -> tuple[Path, ...]:
        return tuple(paths.data_dir.glob(".lightning-restore-*.state"))

    @staticmethod
    def _write_restore_marker(path: Path, value: bytes) -> None:
        temporary = path.with_name(f".{path.name}-{secrets.token_hex(12)}.partial")
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if os.name != "nt":
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _preserve_source_backup(source: Path, folder: Path, operation_id: str) -> Path:
        target = folder / f".lightning-restore-source-{operation_id}.db"
        source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        target_fd = None
        try:
            target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(source_fd, "rb", closefd=False) as input_file, os.fdopen(
                target_fd, "wb", closefd=False
            ) as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
                output_file.flush()
                os.fsync(output_file.fileno())
            if os.name != "nt":
                directory_fd = os.open(folder, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        finally:
            os.close(source_fd)
            if target_fd is not None:
                os.close(target_fd)
        return target

    @classmethod
    def _check_restore_control(cls, paths: ProfilePaths) -> None:
        # Sync authority is deliberately not inferred from a missing store.
        # These reserved paths are the integration boundary for the future sync
        # control store; until its API exists, any such state blocks local restore.
        reserved = (paths.data_dir / ".sync", paths.data_dir / "sync-control.sqlite",
                    paths.data_dir / ".lightning-sync.sqlite")
        if any(path.exists() or path.is_symlink() for path in reserved):
            raise ProfileError("Restore is unavailable while sync authority state exists or cannot be verified.")
        markers = {path.name.removesuffix(".state") for path in cls._restore_marker_paths(paths)}
        for marker in cls._restore_marker_paths(paths):
            try:
                info = marker.stat(follow_symlinks=False)
                if marker.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError("unsafe restore marker")
                state_bytes = marker.read_bytes()
            except OSError as exc:
                raise ProfileError("Restore operation marker cannot be read; this profile is locked for repair.") from exc
            if state_bytes != b"COMPLETE\n":
                raise ProfileError("An interrupted restore needs repair before this profile can be unlocked.")
        journals: dict[str, object] = {}
        for control in cls._restore_journal_paths(paths):
            marker_id = control.name.removesuffix(".sqlite")
            if marker_id not in markers:
                raise ProfileError("A restore journal has no matching operation marker; this profile is locked for repair.")
            try:
                info = control.stat(follow_symlinks=False)
                if control.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError("unsafe restore journal")
                connection = sqlite3.connect(control.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
                try:
                    row = connection.execute(
                        "SELECT accepted_checkpoint_id, accepted_sha256, journal_json "
                        "FROM promotion_control WHERE singleton=1"
                    ).fetchone()
                    state = SqlitePromotionJournalStore._row_state(row)
                finally:
                    connection.close()
            except Exception as exc:
                raise ProfileError("Restore control state is damaged. This profile is locked for repair.") from exc
            journal = state.journal
            if (journal is None or state.accepted is None or
                    journal.phase is not PromotionPhase.ACTIVATED or
                    journal.operation_id != marker_id.removeprefix(".lightning-restore-") or
                    state.accepted.checkpoint_id != journal.new_checkpoint_id or
                    state.accepted.sha256 != journal.new_sha256):
                raise ProfileError("An interrupted restore needs repair before this profile can be unlocked.")
            previous = paths.data_dir / journal.previous_name
            try:
                cls._require_clean_database_file(previous)
                previous_hash = cls._digest(previous)
            except ProfileError as exc:
                raise ProfileError("The retained pre-restore checkpoint is missing or unsafe.") from exc
            if previous_hash != journal.old_sha256:
                raise ProfileError("The retained pre-restore checkpoint is missing or does not match its journal.")
            journals[marker_id] = journal
        if set(journals) != markers:
            raise ProfileError("A restore operation marker has no complete matching journal; this profile is locked for repair.")
        for previous in paths.data_dir.glob(".lightning-restore-*.previous.db"):
            operation_marker = previous.name.removesuffix(".previous.db") + ".state"
            if operation_marker not in {path.name for path in cls._restore_marker_paths(paths)}:
                raise ProfileError("A retained restore checkpoint has no safely completed operation record; this profile is locked for repair.")

    def restore_backup(self, selected: str, backup_path: str, password: str) -> None:
        """Restore one verified encrypted backup into its existing standalone profile.

        The backup and current live database are retained. All staging and
        migration happens on a private candidate before the P0–P5 publication.
        """
        self.session._attempt()
        self.session._locked()
        paths = self.session._select(selected)
        if paths.profile is None:
            raise ProfileError("Restore requires a named Lightning profile.")
        lock = self.session._acquire(paths)
        staged = None
        try:
            self._check_restore_control(paths)
            try:
                key = unwrap_key(read_slot(paths.keys_path), password)
            except (ProfileError, ValueError) as exc:
                raise ProfileError("The profile password could not unlock its encrypted database.") from exc
            self._require_clean_database_file(paths.db_path)
            entries = list_backups(paths.backups_dir, paths.db_path)
            selected_backup = Path(backup_path)
            try:
                selected_resolved = selected_backup.resolve(strict=True)
            except OSError as exc:
                raise ProfileError("Choose a completed backup from this profile.") from exc
            entry = next((item for item in entries if item.path.resolve() == selected_resolved), None)
            if entry is None:
                raise ProfileError("Choose a completed backup from this profile.")
            source = entry.path
            self._require_clean_database_file(source)
            source_hash = self._digest(source)
            operation_id = uuid4().hex
            preserved_source = self._preserve_source_backup(source, paths.backups_dir, operation_id)
            if self._digest(preserved_source) != source_hash:
                raise ProfileError("Could not preserve the selected backup bytes; restore was cancelled.")
            try:
                self._verify_file(source, key)
            except Exception as exc:
                raise ProfileError("The selected backup is damaged, uses another key, or needs a newer Lightning version.") from exc
            if self._digest(source) != source_hash:
                raise ProfileError("The selected backup changed during verification.")

            # Preserve the current live contents, including any committed WAL
            # snapshot semantics. keep=0 is intentional: no retention pruning.
            current = Database(paths.db_path, key=key, read_only=True)
            try:
                saved = backup(current, paths.backups_dir, keep=0, pre_upgrade=True)
            finally:
                current.close()
            if saved is None:
                raise ProfileError("Could not create a verified pre-restore backup; restore was cancelled.")

            staged = stage_database(source, paths.data_dir, destination_key=key, source_key=key)
            candidate = staged.path
            self._migrate_candidate(candidate, key)
            self._verify_file(candidate, key)
            self._require_clean_database_file(paths.db_path)
            if self._digest(source) != source_hash:
                raise ProfileError("The selected backup changed during staging; restore was cancelled.")

            live_hash = self._digest(paths.db_path)
            store_path = paths.data_dir / f".lightning-restore-{operation_id}.sqlite"
            marker_path = paths.data_dir / f".lightning-restore-{operation_id}.state"
            self._write_restore_marker(marker_path, b"PENDING\n")
            existed = store_path.exists()
            store = SqlitePromotionJournalStore(store_path)
            state = store.read_state()
            if state.accepted is None:
                if existed or state.journal is not None:
                    raise ProfileError("Restore control state is incomplete. This profile is locked for repair.")
                old_checkpoint = "restore-base-" + live_hash[:32]
                store.initialize_accepted(old_checkpoint, live_hash)
            else:
                old_checkpoint = state.accepted.checkpoint_id
                if state.accepted.sha256 != live_hash:
                    raise ProfileError("The live database changed before restore publication; restore was cancelled.")
            if state.journal is not None and state.journal.phase is not PromotionPhase.ACTIVATED:
                raise ProfileError("An earlier restore is unresolved. This profile is locked for repair.")
            self._require_clean_database_file(paths.db_path)
            self._require_clean_database_file(candidate)
            previous_name = f".lightning-restore-{operation_id}.previous.db"
            new_checkpoint = "restore-" + uuid4().hex
            if os.name == "nt":
                from lightning.database.promotion_windows import WindowsPromotionFileOps
                file_ops = WindowsPromotionFileOps(paths.data_dir)
            else:
                from lightning.database.promotion import PosixPromotionFileOps
                file_ops = PosixPromotionFileOps(paths.data_dir)
            try:
                service = CandidatePromotionService(file_ops, store)
                def verify(name: str) -> None:
                    self._verify_file(paths.data_dir / name, key)

                def mark_ready(_checkpoint: str, live_name: str) -> None:
                    # P4 is durable; P5 records readiness while the UI remains
                    # locked. The ordinary writable builder runs on a later unlock.
                    self._verify_file(paths.data_dir / live_name, key)

                result = service.promote(
                    operation_id=operation_id,
                    old_checkpoint_id=old_checkpoint,
                    new_checkpoint_id=new_checkpoint,
                    live_name=paths.db_path.name,
                    candidate_name=candidate.name,
                    previous_name=previous_name,
                    operation_gate=_held_profile_lock(lock),
                    verify_database=verify,
                    activate=mark_ready,
                )
                if result.phase is not PromotionPhase.ACTIVATED:
                    raise ProfileError("Restore did not reach durable activation; this profile remains locked.")
                if self._digest(source) != source_hash:
                    raise ProfileError("The selected backup changed during publication; this profile remains locked for repair.")
                self._write_restore_marker(marker_path, b"COMPLETE\n")
                self.session.retry_at = 0.0
            finally:
                file_ops.close()
        except Exception as exc:
            if isinstance(exc, ProfileError):
                raise
            if isinstance(exc, PromotionBlocked):
                raise ProfileError("Restore needs repair. The profile remains locked and recovery files were preserved.") from exc
            raise ProfileError("Restore failed safely. The profile remains locked and recovery files were preserved.") from exc
        finally:
            if staged is not None:
                # Keep failed candidates as evidence; remove only a successful
                # unreferenced partial after it has been atomically consumed.
                if not staged.path.exists():
                    staged.path.unlink(missing_ok=True)
            lock.close()

    @staticmethod
    def _migrate_candidate(path: Path, key: bytes) -> None:
        """Apply supported migrations only to the private staged candidate."""
        db = Database(path, key=key)
        try:
            inspect_schema(db)
            migrate(db)
            seed(db)
            migrate_legacy_ownership(db)
        finally:
            db.close()
