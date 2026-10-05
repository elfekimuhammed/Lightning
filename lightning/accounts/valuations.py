"""Dated whole-asset estimates for accounts such as a home or land share."""
from __future__ import annotations

from lightning.accounts.domain import AccountType
from lightning.core.dates import now_iso, parse_date
from lightning.core.errors import ValidationError
from lightning.core.money import check_places, from_e6, to_decimal, to_e6
from lightning.database.connection import Database


class OtherAssetValuationRepository:
    def __init__(self, db: Database):
        self.db = db

    def latest(self, account_id: int, as_of: str) -> dict | None:
        row = self.db.one(
            "SELECT effective_date,value_e6,notes FROM other_asset_valuations "
            "WHERE account_id=? AND effective_date<=? ORDER BY effective_date DESC LIMIT 1",
            (account_id, as_of))
        if not row:
            return None
        return {**row, "value": from_e6(row["value_e6"])}

    def save(self, account, effective_date: str, amount, notes: str = "") -> dict:
        if account.account_type != AccountType.OTHER_ASSET:
            raise ValidationError("Choose an Other asset account.", "account")
        day = parse_date(effective_date, "date")
        from lightning.core.dates import today
        if day > today():
            raise ValidationError("A value date cannot be in the future.", "date")
        value = check_places(to_decimal(amount, "value"), 2, "value")
        if value < 0:
            raise ValidationError("Enter a value of zero or more.", "value")
        self.db.execute(
            "INSERT INTO other_asset_valuations(account_id,effective_date,value_e6,notes,updated_at) "
            "VALUES(?,?,?,?,?) ON CONFLICT(account_id,effective_date) DO UPDATE SET "
            "value_e6=excluded.value_e6,notes=excluded.notes,updated_at=excluded.updated_at",
            (account.id, day.isoformat(), to_e6(value), (notes or "").strip(), now_iso()))
        return self.latest(account.id, day.isoformat())
