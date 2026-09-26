"""Canonical counterparty identity and user-confirmed spelling aliases."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from lightning.core.dates import now_iso
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.database.connection import Database

MAX_ALIASES_PER_COUNTERPARTY = 10


def normalize(value: str) -> str:
    """Normalize harmless spelling differences without erasing meaningful words."""
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


class CounterpartyService:
    def __init__(self, db: Database):
        self.db = db

    def resolve(self, value: str):
        key = normalize(value)
        if not key:
            return None
        return self.db.one(
            "SELECT c.* FROM counterparties c WHERE c.normalized_name=? "
            "UNION SELECT c.* FROM counterparties c JOIN counterparty_aliases a "
            "ON a.counterparty_id=c.id WHERE a.normalized_alias=? LIMIT 1", (key, key)
        )

    def get(self, counterparty_id: int):
        return self.db.one("SELECT * FROM counterparties WHERE id=?", (counterparty_id,))

    def aliases_for(self, counterparty_id: int):
        return self.db.all(
            "SELECT id,alias FROM counterparty_aliases WHERE counterparty_id=? ORDER BY alias COLLATE NOCASE",
            (counterparty_id,),
        )

    def search_names(self):
        """Canonical names and confirmed aliases offered by smart-search pickers."""
        rows = self.db.all(
            "SELECT name AS value FROM counterparties WHERE active=1 "
            "UNION SELECT a.alias AS value FROM counterparty_aliases a "
            "JOIN counterparties c ON c.id=a.counterparty_id WHERE c.active=1 "
            "ORDER BY value COLLATE NOCASE"
        )
        return [row["value"] for row in rows]

    def list_active(self):
        """Counterparties available in picker controls, in display order."""
        return self.db.all("SELECT id,name,default_category_id FROM counterparties WHERE active=1 ORDER BY name COLLATE NOCASE")

    def suggestions(self, value: str, limit: int = 3) -> list[tuple[str, float]]:
        """Rank likely matches for a human to confirm; suggestions are never auto-merged."""
        key = normalize(value)
        if len(key) < 3 or self.resolve(value):
            return []
        rows = self.db.all(
            "SELECT name, normalized_name AS normalized FROM counterparties WHERE active=1 "
            "UNION SELECT c.name, a.normalized_alias FROM counterparty_aliases a "
            "JOIN counterparties c ON c.id=a.counterparty_id WHERE c.active=1"
        )
        best: dict[str, float] = {}
        for row in rows:
            ratio = SequenceMatcher(None, key, row["normalized"]).ratio()
            if ratio >= 0.68:
                best[row["name"]] = max(best.get(row["name"], 0), ratio)
        return sorted(best.items(), key=lambda item: (-item[1], item[0].casefold()))[:limit]

    def create(self, name: str, default_category_id: int | None = None, alias: str | None = None) -> int:
        name = " ".join((name or "").split())
        key = normalize(name)
        if not key:
            raise ValidationError("Enter a counterparty name.", "counterparty")
        if self.resolve(name):
            raise ConflictError(f"{name} already matches a saved counterparty. Choose it instead.", "counterparty")
        now = now_iso()
        with self.db.transaction():
            cur = self.db.execute(
                "INSERT INTO counterparties(name,normalized_name,default_category_id,created_at,updated_at) "
                "VALUES (?,?,?,?,?)", (name, key, default_category_id, now, now)
            )
            counterparty_id = cur.lastrowid
            self._link_historical(counterparty_id, name)
            if alias:
                if normalize(alias) != key:
                    self.add_alias(counterparty_id, alias)
                else:
                    self._link_historical(counterparty_id, alias)
        return counterparty_id

    def add_alias(self, counterparty_id: int, alias: str) -> None:
        alias = " ".join((alias or "").split())
        key = normalize(alias)
        if not key:
            raise ValidationError("Enter the spelling to remember.", "alias")
        if not self.get(counterparty_id):
            raise NotFoundError("Counterparty not found.")
        if self.resolve(alias):
            existing = self.resolve(alias)
            if existing["id"] == counterparty_id:
                return
            raise ConflictError(f"“{alias}” is already linked to {existing['name']}.", "alias")
        with self.db.transaction():
            alias_count = self.db.scalar(
                "SELECT COUNT(*) FROM counterparty_aliases WHERE counterparty_id=?", (counterparty_id,)
            )
            if int(alias_count or 0) >= MAX_ALIASES_PER_COUNTERPARTY:
                raise ValidationError(f"A counterparty can have at most {MAX_ALIASES_PER_COUNTERPARTY} aliases.", "alias")
            self.db.execute(
                "INSERT INTO counterparty_aliases(counterparty_id,alias,normalized_alias,created_at) "
                "VALUES (?,?,?,?)", (counterparty_id, alias, key, now_iso())
            )
            self._link_historical(counterparty_id, alias)

    def rename_alias(self, counterparty_id: int, alias_id: int, alias: str) -> None:
        alias = " ".join((alias or "").split())
        key = normalize(alias)
        if not key:
            raise ValidationError("Enter the spelling to remember.", "alias")
        row = self.db.one(
            "SELECT id FROM counterparty_aliases WHERE id=? AND counterparty_id=?", (alias_id, counterparty_id)
        )
        if not row:
            raise NotFoundError("Alias not found.")
        existing = self.resolve(alias)
        if existing and existing["id"] != counterparty_id:
            raise ConflictError(f"“{alias}” is already linked to {existing['name']}.", "alias")
        duplicate = self.db.one(
            "SELECT id FROM counterparty_aliases WHERE normalized_alias=? AND id<>?", (key, alias_id)
        )
        if duplicate or (existing and normalize(existing["name"]) == key):
            raise ConflictError(f"“{alias}” is already saved for this counterparty.", "alias")
        self.db.execute(
            "UPDATE counterparty_aliases SET alias=?,normalized_alias=? WHERE id=? AND counterparty_id=?",
            (alias, key, alias_id, counterparty_id),
        )
        self._link_historical(counterparty_id, alias)

    def remove_alias(self, counterparty_id: int, alias_id: int) -> None:
        cur = self.db.execute(
            "DELETE FROM counterparty_aliases WHERE id=? AND counterparty_id=?", (alias_id, counterparty_id)
        )
        if cur.rowcount != 1:
            raise NotFoundError("Alias not found.")

    def _link_historical(self, counterparty_id: int, alias: str) -> None:
        target = self.get(counterparty_id)
        for row in self.db.all("SELECT id,counterparty FROM transactions WHERE counterparty_id IS NULL AND counterparty<>''"):
            if normalize(row["counterparty"]) == normalize(alias):
                self.db.execute("UPDATE transactions SET counterparty_id=?,counterparty=? WHERE id=?",
                                (counterparty_id, target["name"], row["id"]))

    def set_default_category(self, counterparty_id: int, category_id: int | None) -> None:
        cur = self.db.execute(
            "UPDATE counterparties SET default_category_id=?,updated_at=? WHERE id=?",
            (category_id, now_iso(), counterparty_id)
        )
        if cur.rowcount != 1:
            raise NotFoundError("Counterparty not found.")
