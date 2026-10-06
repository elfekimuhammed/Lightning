"""Encrypted ledger copies moved between devices: hashing, verifying and content fingerprints.

A ciphertext hash proves the bytes arrived intact. It does not prove the copy is a sound Lightning ledger of
this profile: `verify_copy` opens it read-only with the data key and checks integrity, schema and identity.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from lightning.database.connection import Database
from lightning.database.migrator import inspect_schema
from lightning.database.snapshot import _inventory, verify_connection

CHUNK = 1024 * 1024


class CopyRejected(ValueError):
    """The copy is damaged, from another profile or another schema."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def fsync_file(path: str | Path) -> None:
    with open(path, "rb+") as handle:
        os.fsync(handle.fileno())


def profile_id_of(db: Database) -> str | None:
    if not db.has_table("profile_identity"):
        return None
    row = db.one("SELECT profile_id FROM profile_identity WHERE singleton = 1")
    return row[0] if row else None


def schema_version(db: Database) -> int:
    return inspect_schema(db).current_version


def verify_copy(path: str | Path, key: bytes, profile_id: str, *, schema: int | None = None) -> int:
    """Open read-only and check pages, integrity, foreign keys, the profile's ID and the schema. Returns the
    schema version. Raises CopyRejected with a reason the owner can act on."""
    db = Database(path, key=key, read_only=True)
    try:
        try:
            verify_connection(db.conn, encrypted=True)
            inspection = inspect_schema(db)
        except Exception as exc:  # noqa: BLE001 - any failure to open or check is a rejection
            raise CopyRejected("The copy is damaged or was not made with this profile's key.") from exc
        if inspection.pending:
            raise CopyRejected("The copy was made by an older Lightning. Update both devices to the same version.")
        if schema is not None and inspection.current_version != schema:
            raise CopyRejected("The two devices run different Lightning versions. Update both to the same one.")
        if profile_id_of(db) != profile_id:
            raise CopyRejected("The copy belongs to another profile.")
        return inspection.current_version
    finally:
        db.close()


def content_fingerprint(path: str | Path, key: bytes) -> str:
    """Hash of every table's rows and the schema: equal for two files with the same ledger, even when their
    ciphertext differs (each export re-encrypts). Used to tell whether the home changed since a checkpoint."""
    db = Database(path, key=key, read_only=True)
    try:
        return hashlib.sha256(repr(_inventory(db.conn)).encode("utf-8")).hexdigest()
    finally:
        db.close()
