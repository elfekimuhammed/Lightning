"""SQL for the budgets table. Only this module touches it."""

from __future__ import annotations

from decimal import Decimal

from lightning.core.dates import now_iso
from lightning.core.money import from_e6, to_e6
from lightning.database.connection import Database

from .domain import BudgetEntry


class BudgetRepository:
    def __init__(self, db: Database):
        self.db = db

    def entries_up_to(self, month: str) -> list[BudgetEntry]:
        """Every row that can affect `month`: repeating rows up to it, one-off rows for it."""
        rows = self.db.all(
            "SELECT * FROM budgets WHERE (one_off = 0 AND month <= ?) OR (one_off = 1 AND month = ?)"
            " ORDER BY category_id, month",
            (month, month),
        )
        return [
            BudgetEntry(r["id"], r["category_id"], r["month"], bool(r["one_off"]),
                        None if r["amount_e6"] is None else from_e6(r["amount_e6"]), r["average_months"])
            for r in rows
        ]

    def upsert(self, category_id: int, month: str, one_off: bool, amount: Decimal | None,
               average_months: int | None = None) -> None:
        now = now_iso()
        self.db.execute(
            "INSERT INTO budgets(category_id, month, one_off, amount_e6, average_months, created_at, updated_at)"
            " VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(category_id, month, one_off) DO UPDATE SET amount_e6 = excluded.amount_e6,"
            " average_months = excluded.average_months,"
            " updated_at = excluded.updated_at",
            (category_id, month, int(one_off), None if amount is None else to_e6(amount), average_months, now, now),
        )

    def delete(self, category_id: int, month: str, one_off: bool) -> None:
        self.db.execute("DELETE FROM budgets WHERE category_id = ? AND month = ? AND one_off = ?",
                        (category_id, month, int(one_off)))

    def carryover_settings(self, month: str) -> dict[int, bool]:
        rows = self.db.all(
            "SELECT c.category_id, c.enabled FROM budget_carryover c "
            "JOIN (SELECT category_id, MAX(month) AS month FROM budget_carryover WHERE month <= ? GROUP BY category_id) latest "
            "ON latest.category_id=c.category_id AND latest.month=c.month", (month,))
        return {int(row["category_id"]): bool(row["enabled"]) for row in rows}

    def carryover_settings_up_to(self, month: str, category_id: int) -> list[tuple[str, bool]]:
        rows = self.db.all("SELECT month, enabled FROM budget_carryover WHERE category_id=? AND month<=? ORDER BY month",
                           (category_id, month))
        return [(str(row["month"]), bool(row["enabled"])) for row in rows]

    def first_carryover_month(self, category_id: int, month: str) -> str | None:
        row = self.db.one("SELECT MIN(month) AS month FROM ("
                          "SELECT month FROM budgets WHERE category_id=? AND one_off=0 AND month<=? "
                          "UNION ALL SELECT month FROM budget_carryover WHERE category_id=? AND month<=?)",
                          (category_id, month, category_id, month))
        return str(row["month"]) if row and row["month"] else None

    def set_carryover(self, category_id: int, month: str, enabled: bool) -> None:
        from lightning.core.dates import now_iso
        now = now_iso()
        self.db.execute(
            "INSERT INTO budget_carryover(category_id,month,enabled,created_at,updated_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(category_id,month) DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at",
            (category_id, month, int(enabled), now, now))
