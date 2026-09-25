"""Audit trail: every edit, void and restore records what changed."""

from __future__ import annotations

import json
from typing import Any

from lightning.core.dates import now_iso

from .connection import Database


class AuditLog:
    def __init__(self, db: Database):
        self.db = db

    def record(
        self,
        entity: str,
        entity_id: int,
        action: str,
        summary: str = "",
        before: Any = None,
        after: Any = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO audit_log(at, entity, entity_id, action, summary, before_json, after_json)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                now_iso(),
                entity,
                entity_id,
                action,
                summary,
                None if before is None else json.dumps(before, default=str, ensure_ascii=False),
                None if after is None else json.dumps(after, default=str, ensure_ascii=False),
            ),
        )

    def history(self, entity: str, entity_id: int) -> list[dict]:
        rows = self.db.all(
            "SELECT at, action, summary FROM audit_log WHERE entity = ? AND entity_id = ? ORDER BY id DESC",
            (entity, entity_id),
        )
        return [dict(r) for r in rows]
