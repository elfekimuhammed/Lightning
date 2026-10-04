"""Single-owner encrypted profile lifecycle. Never opens a profile implicitly."""
from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from lightning.bootstrap import Container, build
from lightning.database.connection import Database
from lightning.database.migrator import inspect_schema
from lightning.database.snapshot import verify_connection
from lightning.security.keys import generate_recovery, recover_key, unwrap_key, wrap_key

from .instance import InstanceAlreadyRunning, InstanceLock
from .paths import ProfilePaths, choose_data_root, create_profile, resolve_profile


class ProfileError(ValueError):
    """Safe, deliberately authored messages suitable for the locked UI."""


def validate_password(password: str, confirm: str) -> None:
    if password != confirm:
        raise ProfileError("The passwords do not match.")
    if len(password) < 12 or len(password.encode("utf-8")) > 4096:
        raise ProfileError("Use a passphrase of at least 12 characters (at most 4096 UTF-8 bytes).")


def read_slot(path: Path) -> dict:
    if path.is_symlink():
        raise ProfileError("A password file must not be a symbolic link.")
    try:
        with path.open("rb") as handle:
            raw = handle.read(16385)
        if len(raw) > 16384:
            raise ValueError("oversized")
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("object required")
        return document
    except (OSError, ValueError) as exc:
        raise ProfileError("The password file is missing or invalid. Use your recovery key.") from exc


def write_slot(path: Path, document: dict, *, replace: bool = False) -> None:
    """Durable atomic slot publication, never truncate the working password file."""
    if path.is_symlink():
        raise ProfileError("A password file must not be a symbolic link.")
    temporary = path.with_name(f".keys-{secrets.token_hex(12)}.partial")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(document, sort_keys=True).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Link publishes exclusively on both supported platforms.
            os.link(temporary, path)
            temporary.unlink()
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass
class PendingProfile:
    paths: ProfilePaths
    recovery: str
    key: bytes
    slot: dict
    expires: float


class ProfileSession:
    """All methods are called on the ASGI owning thread under the request gate."""

    def __init__(self, root: str | Path | None = None):
        self.root = choose_data_root(root)
        self.container: Container | None = None
        self.paths: ProfilePaths | None = None
        self.lock: InstanceLock | None = None
        self.pending: PendingProfile | None = None
        self.token = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.retry_at = 0.0
        self.last_activity = time.monotonic()
        self.idle_seconds = 15 * 60

    @property
    def name(self) -> str:
        if self.paths is None:
            return ""
        return self.paths.profile.name if self.paths.profile else self.paths.db_path.stem

    def _locked(self) -> None:
        if self.container is not None:
            raise ProfileError("Lock the current profile before choosing another one.")

    def prepare(self, name: str, password: str, confirm: str) -> PendingProfile:
        self._locked()
        validate_password(password, confirm)
        if not name.strip() or len(name) > 200:
            raise ProfileError("Enter a profile name of 1–200 characters.")
        paths = create_profile(name, root=self.root)
        recovery, key = generate_recovery()
        self.pending = PendingProfile(paths, recovery, key, wrap_key(key, password), time.monotonic() + 900)
        # Invalidate confirmation forms from any older setup tab. Otherwise a
        # user could acknowledge key A while the pending database uses key B.
        self.csrf = secrets.token_urlsafe(32)
        return self.pending

    def confirm(self, saved: bool) -> None:
        self._locked()
        pending = self.pending
        if pending is None or time.monotonic() >= pending.expires:
            self.pending = None
            raise ProfileError("Setup expired. Create the profile again.")
        if not saved:
            raise ProfileError("Save the recovery key somewhere safe before continuing.")
        paths = pending.paths
        paths.prepare()  # Exclusive directory; never reuse a failed or existing profile.
        lock = InstanceLock(paths.lock_path).acquire()
        candidate = paths.db_path.with_suffix(".partial")
        container = None
        try:
            write_slot(paths.keys_path, pending.slot)
            container = build(candidate, key=pending.key, backup_dir=paths.backups_dir)
            verify_connection(container.db.conn, encrypted=True)
            container.db.close()
            container = None
            with candidate.open("r+b") as handle:
                os.fsync(handle.fileno())
            os.link(candidate, paths.db_path)  # No replacement even in a collision.
            candidate.unlink()
            if os.name != "nt":
                directory = os.open(paths.data_dir, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            container = build(paths.db_path, key=pending.key, backup_dir=paths.backups_dir)
            self._activate(paths, lock, container)
        except BaseException:
            if container is not None:
                container.db.close()
            lock.close()
            raise
        finally:
            # Failed directories remain as recognizable recovery evidence.
            self.pending = None

    def _activate(self, paths: ProfilePaths, lock: InstanceLock, container: Container) -> None:
        self.paths, self.lock, self.container = paths, lock, container
        self.token = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.pending = None
        self.retry_at = 0.0
        self.last_activity = time.monotonic()

    def _select(self, selected: str) -> ProfilePaths:
        self._locked()
        if not selected or len(selected) > 4096:
            raise ProfileError("Choose an existing database file.")
        paths = resolve_profile(db_path=selected)
        if not paths.db_path.is_file() or paths.db_path.stat().st_size == 0:
            raise ProfileError("The selected database does not exist or is empty.")
        # Completed snapshots must never become live databases through the picker.
        if paths.db_path.parent.name == "backups" or "_backup_" in paths.db_path.stem or "_upgrade_" in paths.db_path.stem:
            raise ProfileError("This is a backup. Keep it unchanged; restoring into a new profile is not available yet.")
        with paths.db_path.open("rb") as handle:
            if handle.read(16) == b"SQLite format 3\x00":
                raise ProfileError("This is an unencrypted legacy database. It has not been changed. Explicit import is not available yet.")
        for companion in (paths.data_dir, paths.keys_path, paths.backups_dir, paths.lock_path):
            if companion.is_symlink():
                raise ProfileError("Profile companion files must not be symbolic links.")
        return paths

    def _acquire(self, paths: ProfilePaths) -> InstanceLock:
        paths.prepare()
        try:
            return InstanceLock(paths.lock_path).acquire()
        except InstanceAlreadyRunning as exc:
            raise ProfileError("This profile is open in another Lightning process. Close it there first.") from exc

    def _attempt(self) -> None:
        if time.monotonic() < self.retry_at:
            raise ProfileError("Please wait a moment before trying again.")
        self.retry_at = time.monotonic() + 2

    def unlock(self, selected: str, password: str) -> None:
        self._attempt()
        paths = self._select(selected)
        lock = self._acquire(paths)
        try:
            try:
                key = unwrap_key(read_slot(paths.keys_path), password)
            except ProfileError:
                raise
            except ValueError as exc:
                raise ProfileError("The password is incorrect or the password file is damaged.") from exc
            from lightning.runtime.restore import EncryptedBackupRestorer
            EncryptedBackupRestorer._check_restore_control(paths, key)
            self._verify(paths, key)
            container = build(paths.db_path, key=key, backup_dir=paths.backups_dir, backup_on_start=True)
            self._activate(paths, lock, container)
        except BaseException:
            lock.close()
            raise

    def restore_backup(self, selected: str, backup_path: str, password: str) -> None:
        from lightning.runtime.restore import EncryptedBackupRestorer

        EncryptedBackupRestorer(self).restore_backup(selected, backup_path, password)

    def resume_interrupted_restore(self, selected: str, password: str) -> None:
        from lightning.runtime.restore import EncryptedBackupRestorer

        EncryptedBackupRestorer(self).resume_interrupted_restore(selected, password)

    @staticmethod
    def _verify(paths: ProfilePaths, key: bytes) -> None:
        db = Database(paths.db_path, key=key, read_only=True)
        try:
            if not db.has_table("schema_migrations"):
                raise ProfileError("The selected file is not a Lightning database.")
            inspect_schema(db)
            verify_connection(db.conn, encrypted=True)
        finally:
            db.close()

    def recover(self, selected: str, recovery: str, password: str, confirm: str) -> None:
        self._attempt()
        validate_password(password, confirm)
        paths = self._select(selected)
        lock = self._acquire(paths)
        try:
            try:
                key = recover_key(recovery)
                self._verify(paths, key)
            except Exception as exc:
                raise ProfileError("The recovery key could not unlock this database, or the database needs repair/a newer app.") from exc
            write_slot(paths.keys_path, wrap_key(key, password), replace=True)
            self.retry_at = 0.0
        finally:
            lock.close()

    def change_password(self, current: str, password: str, confirm: str) -> None:
        if self.paths is None or self.container is None:
            raise ProfileError("Unlock a profile first.")
        self._attempt()
        validate_password(password, confirm)
        try:
            key = unwrap_key(read_slot(self.paths.keys_path), current)
            self._verify(self.paths, key)
        except Exception as exc:
            raise ProfileError("The current password could not be verified.") from exc
        write_slot(self.paths.keys_path, wrap_key(key, password), replace=True)
        self.retry_at = 0.0

    def close(self) -> None:
        # Do not release the OS lock if closing the database fails.
        if self.container is not None:
            self.container.db.close()
        self.container = None
        self.paths = None
        if self.lock is not None:
            self.lock.close()
            self.lock = None
        self.pending = None
        self.token = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
