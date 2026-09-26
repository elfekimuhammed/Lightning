"""Cleared transaction tracking and statement reconciliation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from lightning.core.errors import NotFoundError, ValidationError
from lightning.core.money import ZERO, from_e6
from lightning.database.connection import Database


class ReconciliationService:
    def __init__(self, db: Database):
        self.db = db

    def lines(self, account_id: int, through: str):
        rows = [dict(row) for row in self.db.all(
            "SELECT le.id AS line_id,le.date,le.quantity_e6,t.type,t.ref,t.counterparty,t.description,"
            "le.memo,le.cleared,le.category_id FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id "
            "WHERE le.account_id=? AND le.date<=? AND t.status='POSTED' "
            "AND le.asset_id IN (SELECT id FROM financial_assets WHERE is_cash=1) "
            "ORDER BY le.date DESC,t.id DESC,le.line_no DESC",
            (account_id, through),
        )]
        for row in rows:
            row["amount"] = from_e6(row["quantity_e6"])
        return rows

    def summary(self, account_id: int, through: str, statement_balance: Decimal | None):
        row = self.db.one(
            "SELECT COALESCE(SUM(CASE WHEN le.cleared=1 OR t.type='OPN' "
            "THEN le.quantity_e6 ELSE 0 END),0) AS cleared_e6, "
            "SUM(CASE WHEN le.cleared=0 AND t.type<>'OPN' THEN 1 ELSE 0 END) AS uncleared_count "
            "FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
            "WHERE le.account_id=? AND le.date<=? AND t.status='POSTED' "
            "AND le.asset_id IN (SELECT id FROM financial_assets WHERE is_cash=1)",
            (account_id, through),
        )
        cleared = from_e6(row["cleared_e6"])
        difference = statement_balance - cleared if statement_balance is not None else None
        return {"cleared_balance": cleared, "uncleared_count": int(row["uncleared_count"] or 0),
                "difference": difference, "reconciled": difference == ZERO if difference is not None else False}

    def set_cleared(self, account_id: int, line_id: int, cleared: bool) -> None:
        row = self.db.one(
            "SELECT le.id,t.type FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
            "WHERE le.id=? AND le.account_id=? AND le.asset_id IN "
            "(SELECT id FROM financial_assets WHERE is_cash=1) AND t.status='POSTED'",
            (line_id, account_id),
        )
        if not row:
            raise NotFoundError("Transaction line not found in this account.")
        if row["type"] == "OPN" and not cleared:
            raise ValidationError("An opening balance is the starting point for reconciliation.")
        self.db.execute("UPDATE ledger_entries SET cleared=? WHERE id=?", (int(cleared), line_id))

    @staticmethod
    def parse_statement_balance(value: str) -> Decimal:
        from lightning.core.money import to_decimal
        return to_decimal(value, "statement_balance")

    @staticmethod
    def validate_date(value: str) -> str:
        try:
            return date.fromisoformat(value).isoformat()
        except (TypeError, ValueError):
            raise ValidationError("Enter a valid statement date.", "date") from None
