"""Device-local control store for one profile's writing authority (multiple devices, task 05b).

One small SQLite file per profile, outside the profile folder and never synced or copied to another device:
the home or borrower authority record, the devices paired with it, and the promotion journal. It holds IDs,
hashes and device names only: no ledger rows, keys or passwords.

Every change runs `load -> apply -> save` inside one `BEGIN IMMEDIATE` transaction with FULL synchronous
writes. When the apply step raises, nothing is saved, so a refused message never changes state. A missing or
damaged record never becomes a fresh "at home": it raises `ControlCorrupt` and the caller keeps writes blocked.

The promotion journal (`lightning/database/promotion.py`) lives in the same file. Its P4 step, which makes the
returned candidate the accepted checkpoint, also records the home's acceptance receipt in the same transaction,
so a crash can never leave one without the other.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from lightning.database.promotion import (AcceptedCheckpoint, PromotionJournal, PromotionPhase,
                                          SqlitePromotionJournalStore)

from .domain import Accepted, _hash, _id, _name
from .state import BorrowerModel, HomeProtocolModel, HomeState, ProtocolError

T = TypeVar("T")
CONTROL_NAME = "control.db"


class ControlCorrupt(RuntimeError):
    """The authority record is missing, damaged or contradictory: keep the profile from writing."""


@dataclass(frozen=True)
class Peer:
    device_id: str
    name: str
    public_key: str        # the peer's signing key (PEM text for a PC; empty for a home)
    endpoint: str          # host:port this PC last reached the home at; empty on the home's side
    certificate_sha256: str  # the home's pinned TLS certificate, as seen by a PC; empty on the home's side
    revoked: bool = False


def _no_duplicates(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("Duplicate key")
        record[key] = value
    return record


class ControlStore(SqlitePromotionJournalStore):
    """Authority, peers and promotion for one profile on this device. Hold the profile's instance lock."""

    def __init__(self, folder: str | Path):
        folder = Path(folder)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        super().__init__(folder / CONTROL_NAME)
        connection = self._connect()
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "role TEXT NOT NULL CHECK(role IN ('home','borrower')), profile_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, record TEXT NOT NULL)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS peers (device_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                "public_key TEXT NOT NULL, endpoint TEXT NOT NULL, certificate_sha256 TEXT NOT NULL, "
                "revoked INTEGER NOT NULL CHECK(revoked IN (0,1)))")
        finally:
            connection.close()

    # ------------------------------------------------------------ authority record
    @staticmethod
    def _authority_row(connection):
        return connection.execute("SELECT role, profile_id, revision, record FROM authority WHERE singleton=1").fetchone()

    @classmethod
    def _decode(cls, row, role: str):
        if row is None:
            raise ControlCorrupt("This device has no authority record for the profile")
        stored_role, profile_id, _revision, text = row
        if stored_role != role:
            raise ControlCorrupt(f"This device holds the profile as {stored_role}, not {role}")
        try:
            record = json.loads(text, object_pairs_hook=_no_duplicates)
            model = (HomeProtocolModel if role == "home" else BorrowerModel).from_record(record)
        except (KeyError, TypeError, ValueError) as exc:
            raise ControlCorrupt("The authority record is damaged; writes stay blocked") from exc
        if model.profile_id != profile_id:
            raise ControlCorrupt("The authority record names another profile")
        return model

    def role(self) -> str | None:
        connection = self._connect()
        try:
            row = self._authority_row(connection)
        finally:
            connection.close()
        return None if row is None else row[0]

    def create(self, model: HomeProtocolModel | BorrowerModel) -> None:
        """First record for this profile on this device. Never replaces one (a missing record is not a reset)."""
        role = "home" if isinstance(model, HomeProtocolModel) else "borrower"
        with self._transaction() as connection:
            if self._authority_row(connection) is not None:
                raise ControlCorrupt("An authority record already exists for this profile")
            connection.execute("INSERT INTO authority VALUES (1, ?, ?, 1, ?)",
                               (role, model.profile_id, json.dumps(model.to_record(), sort_keys=True)))

    def read(self, role: str):
        connection = self._connect()
        try:
            return self._decode(self._authority_row(connection), role)
        finally:
            connection.close()

    def _apply(self, connection, role: str, change: Callable[[object], T]) -> T:
        row = self._authority_row(connection)
        model = self._decode(row, role)
        result = change(model)  # raises -> the caller's transaction rolls back: no state change
        connection.execute("UPDATE authority SET revision = revision + 1, record = ? WHERE singleton=1",
                           (json.dumps(model.to_record(), sort_keys=True),))
        return result

    def home(self, change: Callable[[HomeProtocolModel], T]) -> T:
        """Apply one change to the home record durably. Return what `change` returned."""
        with self._transaction() as connection:
            return self._apply(connection, "home", change)

    def borrower(self, change: Callable[[BorrowerModel], T]) -> T:
        with self._transaction() as connection:
            return self._apply(connection, "borrower", change)

    # ------------------------------------------------------------ peers
    def save_peer(self, peer: Peer) -> None:
        _id(peer.device_id, "device_id")
        _name(peer.name, "name")
        if peer.certificate_sha256:
            _hash(peer.certificate_sha256, "certificate_sha256")
        if len(peer.public_key) > 4096 or len(peer.endpoint) > 300:
            raise ValueError("Invalid peer")
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO peers VALUES (?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET name=excluded.name, "
                "public_key=excluded.public_key, endpoint=excluded.endpoint, "
                "certificate_sha256=excluded.certificate_sha256, revoked=excluded.revoked",
                (peer.device_id, peer.name, peer.public_key, peer.endpoint, peer.certificate_sha256,
                 int(peer.revoked)))

    def peers(self) -> list[Peer]:
        connection = self._connect()
        try:
            rows = connection.execute("SELECT device_id, name, public_key, endpoint, certificate_sha256, revoked "
                                      "FROM peers ORDER BY name, device_id").fetchall()
        finally:
            connection.close()
        return [Peer(*row[:5], revoked=bool(row[5])) for row in rows]

    def peer(self, device_id: str) -> Peer | None:
        return next((p for p in self.peers() if p.device_id == device_id), None)

    # ------------------------------------------------------------ promotion joined to authority (P4)
    def rebase_accepted(self, checkpoint_id: str, sha256: str) -> None:
        """The live home file before a lend: what a returned candidate will replace. Only with no open
        promotion; home edits since the last lend changed the file, so the accepted hash moves with it."""
        accepted = AcceptedCheckpoint(checkpoint_id, sha256)
        with self._transaction() as connection:
            state = self._read_from(connection)
            if state.journal is not None and state.journal.phase is not PromotionPhase.ACTIVATED:
                raise ControlCorrupt("A promotion is unresolved; repair it before lending")
            connection.execute("UPDATE promotion_control SET accepted_checkpoint_id=?, accepted_sha256=? "
                               "WHERE singleton=1", (accepted.checkpoint_id, accepted.sha256))

    def commit_authority(self, expected: PromotionJournal) -> PromotionJournal:
        """P4 and the home's acceptance receipt, in one transaction (plan section 9)."""
        if expected.phase is not PromotionPhase.FILE_PUBLISHED:
            raise ValueError("Authority can be accepted only from P3")
        accepted_new = AcceptedCheckpoint(expected.new_checkpoint_id, expected.new_sha256)
        p4 = expected.advance(PromotionPhase.AUTHORITY_PUBLISHED)
        with self._transaction() as connection:
            state = self._read_from(connection)
            if state.journal == p4 and state.accepted == accepted_new:
                return p4
            if state.journal != expected or state.accepted != AcceptedCheckpoint(expected.old_checkpoint_id,
                                                                                   expected.old_sha256):
                raise RuntimeError("Promotion journal changed before authority commit")
            row = self._authority_row(connection)
            if row is not None and row[0] == "home":
                def accept(home: HomeProtocolModel) -> None:
                    pending = home.pending_return()
                    if pending is None or pending.candidate_sha256 != expected.new_sha256:
                        raise ProtocolError("NOT_PUBLISHED", "No received return matches the published file")
                    home.record_accepted(Accepted(pending.return_id, pending.checkout_id, expected.new_checkpoint_id,
                                                  expected.new_sha256, pending.lineage_id, pending.epoch),
                                         published_sha256=expected.new_sha256)
                self._apply(connection, "home", accept)
            connection.execute("UPDATE promotion_control SET accepted_checkpoint_id=?, accepted_sha256=?, "
                               "journal_json=? WHERE singleton=1",
                               (accepted_new.checkpoint_id, accepted_new.sha256, self._encoded(p4)))
        return p4

    def unresolved_promotion(self) -> PromotionJournal | None:
        journal = self.read_state().journal
        return journal if journal is not None and journal.phase is not PromotionPhase.ACTIVATED else None


def new_id() -> str:
    return str(uuid.uuid4())


def blocks_restore(folder: str | Path) -> bool:
    """For the restore flow: True while this device has lent the profile or holds unfinished sync state.
    Restoring an old backup then would fork the ledger (Architecture, multiple devices)."""
    path = Path(folder) / CONTROL_NAME
    if not path.exists():
        return False
    try:
        store = ControlStore(folder)
        if store.unresolved_promotion() is not None:
            return True
        if store.role() == "borrower":
            return True
        if store.role() == "home":
            return store.read("home").state is not HomeState.AT_HOME
    except (ControlCorrupt, RuntimeError, sqlite3.Error):
        return True
    return False

