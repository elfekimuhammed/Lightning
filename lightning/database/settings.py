"""Key/value settings (base currency, ...)."""

from __future__ import annotations

import json

from lightning.core.dates import now_iso
from lightning.core.errors import ValidationError

from .connection import Database
from lightning.currencies import CURRENCIES, currency

DEFAULTS = {
    "base_currency": "EGP",
    "app_name": "Lightning",
}


class SettingsStore:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str) -> str:
        value = self.db.scalar("SELECT value FROM settings WHERE key = ?", (key,))
        return DEFAULTS.get(key, "") if value is None else value

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES (?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now_iso()),
        )

    @property
    def base_currency(self) -> str:
        return self.get("base_currency")

    @property
    def enabled_currencies(self) -> tuple[str, ...]:
        raw = self.get("enabled_currencies")
        if not raw:
            return (self.base_currency,)
        try:
            codes = {currency(code).code for code in json.loads(raw)}
        except (TypeError, ValueError):
            raise RuntimeError("The saved enabled-currency setting is invalid.") from None
        codes.add(self.base_currency)
        return tuple(item.code for item in CURRENCIES if item.code in codes)

    def set_base_currency(self, code: str) -> None:
        code = currency(code).code
        if self.db.scalar("SELECT 1 FROM transactions LIMIT 1"):
            raise ValidationError("The reporting currency is fixed after the first financial entry.", "base_currency")
        self.set("base_currency", code)
        self.set_enabled_currencies(set(self.enabled_currencies) | {code})

    def set_enabled_currencies(self, codes) -> None:
        selected = {currency(code).code for code in codes}
        selected.add(self.base_currency)
        removed = set(self.enabled_currencies) - selected
        for code in removed:
            if self.db.scalar("SELECT 1 FROM accounts WHERE currency=? LIMIT 1", (code,)):
                raise ValidationError(f"{code} is still used by an account.", "enabled_currencies")
            if self.db.scalar(
                "SELECT 1 FROM ledger_entries le JOIN financial_assets a ON a.id=le.asset_id "
                "WHERE a.currency=? LIMIT 1", (code,)
            ):
                raise ValidationError(f"{code} is still used by a holding.", "enabled_currencies")
            if self.db.scalar(
                "SELECT 1 FROM planned_items p JOIN accounts a ON a.id=p.account_id "
                "WHERE a.currency=? LIMIT 1", (code,)
            ):
                raise ValidationError(f"{code} is still used by a plan.", "enabled_currencies")
        ordered = [item.code for item in CURRENCIES if item.code in selected]
        self.set("enabled_currencies", json.dumps(ordered, separators=(",", ":")))
