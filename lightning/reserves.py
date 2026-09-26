"""Virtual cash reserves for upcoming needs and savings goals."""

from __future__ import annotations

import sqlite3
import calendar
from datetime import date, timedelta
from decimal import Decimal

from lightning.core.dates import now_iso
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.core.money import ZERO, from_e6, to_decimal, to_e6
from lightning.database.connection import Database


class CashReserveService:
    def __init__(self, db: Database):
        self.db = db

    def list_active(self):
        return [self._row(row) for row in self.db.all(
            "SELECT r.*,(SELECT COALESCE(SUM(l.amount_e6),0) FROM reserve_transaction_links l "
            "JOIN transactions t ON t.id=l.transaction_id WHERE l.reserve_id=r.id AND t.status='POSTED') AS spent_e6 "
            "FROM cash_reserves r WHERE r.status='ACTIVE' ORDER BY "
            "CASE r.kind WHEN 'EMERGENCY' THEN 0 ELSE 1 END,r.due_date IS NULL,r.due_date,r.name COLLATE NOCASE"
        )]

    def cash_summary(self, owned_liquid_cash: Decimal):
        allocated = ZERO
        for row in self.list_active():
            allocated += row["effective_allocated"]
        return {"owned_liquid_cash": owned_liquid_cash, "allocated": allocated,
                "free_cash": owned_liquid_cash - allocated}

    def get(self, reserve_id: int):
        row = self.db.one("SELECT * FROM cash_reserves WHERE id=?", (reserve_id,))
        if not row:
            raise NotFoundError("Reserve not found.")
        return self._row(row)

    def set_emergency_fund(self, amount, salary_target=ZERO):
        """Set the reserved cash for the fixed Emergency Fund section."""
        value = to_decimal(amount, "allocated")
        if value < ZERO:
            raise ValidationError("Reserved cash cannot be negative.", "allocated")
        target = max(to_decimal(salary_target, "target"), value, Decimal("0.01"))
        active = self.db.one("SELECT id FROM cash_reserves WHERE kind='EMERGENCY' AND status='ACTIVE'")
        if not active and value == ZERO:
            raise ValidationError("Enter the amount you have reserved for emergencies.", "allocated")
        with self.db.transaction():
            if active:
                self.db.execute("UPDATE cash_reserves SET target_e6=?,updated_at=? WHERE id=?",
                                (to_e6(target), now_iso(), active["id"]))
                return self.allocate(int(active["id"]), value)
            reserve = self.create("Emergency Fund", target, "EMERGENCY")
            return self.allocate(reserve["id"], value)

    def create(self, name: str, target, kind: str = "PROJECT", due_date: str | None = None,
               recurrence: str = "NONE", counterparty_id: int | None = None):
        name = " ".join((name or "").split())
        if not name:
            raise ValidationError("Enter a name for this reserve.", "name")
        kind = str(kind or "PROJECT").upper()
        if kind not in {"PROJECT", "EMERGENCY"}:
            raise ValidationError("Choose an emergency fund or project.", "kind")
        if kind == "EMERGENCY":
            name = "Emergency Fund"
        recurrence = self._recurrence(recurrence, kind, due_date)
        target_value = to_decimal(target, "target")
        if target_value <= ZERO:
            raise ValidationError("Enter a target greater than zero.", "target")
        day = self._date(due_date) if due_date else None
        self._validate_counterparty(counterparty_id)
        now = now_iso()
        try:
            cur = self.db.execute(
                "INSERT INTO cash_reserves(name,kind,target_e6,due_date,created_at,updated_at,recurrence,recurrence_day,counterparty_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, kind, to_e6(target_value), day, now, now, recurrence,
                 date.fromisoformat(day).day if day and recurrence != "NONE" else None, counterparty_id),
            )
        except sqlite3.IntegrityError:
            if kind == "EMERGENCY" and self.db.scalar(
                "SELECT 1 FROM cash_reserves WHERE kind='EMERGENCY' AND status='ACTIVE'"
            ):
                raise ConflictError("An active emergency fund already exists.", "kind") from None
            raise
        return self.get(int(cur.lastrowid))

    def update(self, reserve_id: int, name: str, target, due_date: str | None, recurrence: str | None = None,
               counterparty_id: int | None = None):
        reserve = self.get(reserve_id)
        if reserve["kind"] == "EMERGENCY":
            raise ValidationError("The Emergency Fund is managed in its dedicated section.")
        name = " ".join((name or "").split())
        if not name:
            raise ValidationError("Enter a name for this reserve.", "name")
        target_value = to_decimal(target, "target")
        if target_value <= ZERO:
            raise ValidationError("Enter a target greater than zero.", "target")
        day = self._date(due_date) if due_date else None
        recurrence = self._recurrence(recurrence if recurrence is not None else reserve["recurrence"],
                                      reserve["kind"], day)
        self._validate_counterparty(counterparty_id)
        recurrence_day = (date.fromisoformat(day).day if day != reserve["due_date"] else
                          (reserve.get("recurrence_day") or date.fromisoformat(day).day)) if day and recurrence != "NONE" else None
        self.db.execute(
            "UPDATE cash_reserves SET name=?,target_e6=?,due_date=?,recurrence=?,recurrence_day=?,counterparty_id=?,updated_at=? WHERE id=?",
            (name, to_e6(target_value), day, recurrence, recurrence_day, counterparty_id, now_iso(), reserve_id),
        )
        return self.get(reserve.id)

    def allocate(self, reserve_id: int, amount):
        reserve = self.get(reserve_id)
        if reserve["status"] != "ACTIVE":
            raise ValidationError("Reopen this reserve before changing its assigned cash.")
        value = to_decimal(amount, "allocated")
        if value < ZERO:
            raise ValidationError("Assigned cash cannot be negative.", "allocated")
        linked = int(self.db.scalar(
            "SELECT COALESCE(SUM(l.amount_e6),0) FROM reserve_transaction_links l "
            "JOIN transactions t ON t.id=l.transaction_id WHERE l.reserve_id=? AND t.status='POSTED'",
            (reserve_id,),
        ) or 0)
        if to_e6(value) < linked:
            raise ValidationError("This amount is below payments already assigned to the reserve.", "allocated")
        self.db.execute(
            "UPDATE cash_reserves SET allocated_e6=?,updated_at=? WHERE id=? AND status='ACTIVE'",
            (to_e6(value), now_iso(), reserve_id),
        )
        return next((item for item in self.list_active() if item["id"] == reserve_id), self.get(reserve_id))

    def set_expense_link(self, reserve_id: int, transaction_id: int, amount):
        with self.db.transaction():
            return self._set_expense_link(reserve_id, transaction_id, amount)

    def _set_expense_link(self, reserve_id: int, transaction_id: int, amount):
        reserve = self.get(reserve_id)
        if reserve["status"] != "ACTIVE":
            raise ValidationError("Choose an active reserve.")
        value = to_decimal(amount, "amount")
        if value <= ZERO:
            raise ValidationError("Enter an amount greater than zero.", "amount")
        txn = self.db.one("SELECT id,status,type FROM transactions WHERE id=?", (transaction_id,))
        if not txn or txn["status"] != "POSTED" or txn["type"] != "OUT":
            raise ValidationError("Choose a posted expense transaction.")
        if self.db.scalar("SELECT 1 FROM money_from_others WHERE transaction_id=?", (transaction_id,)):
            raise ValidationError("Money held for others cannot be assigned to your reserve.")
        total_e6 = int(self.db.scalar(
            "SELECT COALESCE(-SUM(le.quantity_e6),0) FROM ledger_entries le "
            "JOIN financial_assets a ON a.id=le.asset_id WHERE le.transaction_id=? AND a.is_cash=1",
            (transaction_id,),
        ) or 0)
        if total_e6 <= 0:
            raise ValidationError("This transaction has no expense amount to assign.")
        old = self.db.one("SELECT id,amount_e6 FROM reserve_transaction_links WHERE reserve_id=? AND transaction_id=?",
                          (reserve_id, transaction_id))
        other_for_txn = int(self.db.scalar(
            "SELECT COALESCE(SUM(amount_e6),0) FROM reserve_transaction_links WHERE transaction_id=? "
            "AND NOT (reserve_id=? AND transaction_id=?)", (transaction_id, reserve_id, transaction_id),
        ) or 0)
        if to_e6(value) + other_for_txn > total_e6:
            raise ValidationError("The amount assigned across reserves cannot exceed this transaction.", "amount")
        other_spent = int(self.db.scalar(
            "SELECT COALESCE(SUM(amount_e6),0) FROM reserve_transaction_links WHERE reserve_id=? "
            "AND transaction_id<>? AND transaction_id IN (SELECT id FROM transactions WHERE status='POSTED')",
            (reserve_id, transaction_id),
        ) or 0)
        if other_spent + to_e6(value) > int(reserve["allocated_e6"]):
            raise ValidationError("Assign more cash to this reserve before linking that much of the payment.", "amount")
        now = now_iso()
        self.db.execute(
            "INSERT INTO reserve_transaction_links(reserve_id,transaction_id,amount_e6,created_at,updated_at) "
            "VALUES (?,?,?,?,?) ON CONFLICT(reserve_id,transaction_id) DO UPDATE SET "
            "amount_e6=excluded.amount_e6,updated_at=excluded.updated_at",
            (reserve_id, transaction_id, to_e6(value), now, now),
        )
        total_spent = int(self.db.scalar(
            "SELECT COALESCE(SUM(l.amount_e6),0) FROM reserve_transaction_links l "
            "JOIN transactions t ON t.id=l.transaction_id WHERE l.reserve_id=? AND t.status='POSTED'",
            (reserve_id,),
        ) or 0)
        if reserve["recurrence"] != "NONE" and total_spent >= int(reserve["target_e6"]):
            next_due = self._next_due(reserve)
            if next_due:
                self.db.execute("UPDATE cash_reserves SET status='COMPLETE',updated_at=? WHERE id=?",
                                (now_iso(), reserve_id))
                self.create(reserve["name"], reserve["target"], "PROJECT", next_due,
                            reserve["recurrence"], reserve["counterparty_id"])

    def auto_link_transaction(self, transaction_id: int) -> int:
        transaction = self.db.one(
            "SELECT id,counterparty_id,type,status FROM transactions WHERE id=?", (transaction_id,)
        )
        if not transaction or transaction["type"] != "OUT" or transaction["status"] != "POSTED" \
                or not transaction["counterparty_id"]:
            return 0
        if self.db.scalar("SELECT 1 FROM money_from_others WHERE transaction_id=?", (transaction_id,)):
            return 0
        if self.db.scalar("SELECT 1 FROM reserve_transaction_links WHERE transaction_id=?", (transaction_id,)):
            return 0
        remaining = int(self.db.scalar(
            "SELECT COALESCE(-SUM(le.quantity_e6),0) FROM ledger_entries le "
            "JOIN financial_assets a ON a.id=le.asset_id WHERE le.transaction_id=? AND a.is_cash=1",
            (transaction_id,),
        ) or 0)
        if remaining <= 0:
            return 0
        targets = self.db.all(
            "SELECT id FROM cash_reserves WHERE status='ACTIVE' AND counterparty_id=? "
            "ORDER BY due_date IS NULL,due_date,id", (transaction["counterparty_id"],)
        )
        linked = 0
        for row in targets:
            reserve = next((item for item in self.list_active() if item["id"] == row["id"]), None)
            if not reserve or reserve["effective_allocated"] <= ZERO or remaining <= 0:
                continue
            amount_e6 = min(remaining, to_e6(reserve["effective_allocated"]))
            self.set_expense_link(reserve["id"], transaction_id, from_e6(amount_e6))
            remaining -= amount_e6
            linked += 1
        return linked

    def unlink_expense(self, reserve_id: int, transaction_id: int):
        self.db.execute("DELETE FROM reserve_transaction_links WHERE reserve_id=? AND transaction_id=?",
                        (reserve_id, transaction_id))

    def links_for_transaction(self, transaction_id: int):
        rows = [dict(row) for row in self.db.all(
            "SELECT l.reserve_id,r.name,r.kind,l.amount_e6 FROM reserve_transaction_links l "
            "JOIN cash_reserves r ON r.id=l.reserve_id JOIN transactions t ON t.id=l.transaction_id "
            "WHERE l.transaction_id=? AND t.status='POSTED' ORDER BY r.name COLLATE NOCASE", (transaction_id,)
        )]
        for row in rows:
            row["amount"] = from_e6(row["amount_e6"])
        return rows

    def complete(self, reserve_id: int):
        reserve = self.get(reserve_id)
        if reserve["kind"] == "EMERGENCY":
            raise ValidationError("The Emergency Fund cannot be completed or archived.")
        self.db.execute("UPDATE cash_reserves SET status='COMPLETE',updated_at=? WHERE id=?",
                        (now_iso(), reserve_id))
        return self.get(reserve_id)

    def delete(self, reserve_id: int):
        reserve = self.get(reserve_id)
        if reserve["kind"] == "EMERGENCY":
            raise ValidationError("The Emergency Fund cannot be deleted.")
        self.db.execute("DELETE FROM cash_reserves WHERE id=?", (reserve_id,))

    @staticmethod
    def _row(row):
        item = dict(row)
        item["target"] = from_e6(item["target_e6"])
        item["allocated"] = from_e6(item["allocated_e6"])
        item["spent"] = from_e6(item.get("spent_e6", 0))
        item["effective_allocated"] = max(item["allocated"] - item["spent"], ZERO)
        credited = item["allocated"] if item["kind"] == "PROJECT" else item["effective_allocated"]
        item["remaining"] = max(item["target"] - credited, ZERO)
        item["progress"] = min(credited / item["target"] * 100, Decimal(100))
        return item

    @staticmethod
    def _date(value: str) -> str:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except (TypeError, ValueError):
            raise ValidationError("Enter a valid due date.", "due_date") from None

    @staticmethod
    def _recurrence(value: str, kind: str, due_date: str | None) -> str:
        recurrence = str(value or "NONE").upper()
        if recurrence not in {"NONE", "WEEKLY", "MONTHLY", "YEARLY"}:
            raise ValidationError("Choose a supported repeat interval.", "recurrence")
        if kind == "EMERGENCY" and recurrence != "NONE":
            raise ValidationError("Emergency funds do not repeat on a schedule.", "recurrence")
        if recurrence != "NONE" and not due_date:
            raise ValidationError("Choose a due date for a repeating project.", "due_date")
        return recurrence

    def _validate_counterparty(self, counterparty_id: int | None) -> None:
        if counterparty_id is not None and not self.db.scalar(
            "SELECT 1 FROM counterparties WHERE id=? AND active=1", (counterparty_id,)
        ):
            raise ValidationError("Choose an active saved Counterparty.", "counterparty_id")

    @staticmethod
    def _next_due(reserve) -> str | None:
        recurrence = reserve["recurrence"]
        if not recurrence or recurrence == "NONE" or not reserve["due_date"]:
            return None
        current = date.fromisoformat(reserve["due_date"])
        if recurrence == "WEEKLY":
            return (current + timedelta(days=7)).isoformat()
        if recurrence == "YEARLY":
            year, month, day = current.year + 1, current.month, int(reserve.get("recurrence_day") or current.day)
            day = min(day, calendar.monthrange(year, month)[1])
            return date(year, month, day).isoformat()
        month_index = current.year * 12 + current.month
        year, month = divmod(month_index, 12)
        day = min(int(reserve.get("recurrence_day") or current.day), calendar.monthrange(year, month + 1)[1])
        return date(year, month + 1, day).isoformat()
