"""Dated manual exchange rates, quoted in profile currency per foreign unit."""

from __future__ import annotations

from lightning.core.dates import fmt_date, now_iso, parse_date, today
from lightning.core.errors import ValidationError
from lightning.core.money import check_places, from_e6, to_decimal, to_e6
from lightning.database.connection import Database


class CurrencyRates:
    def __init__(self, db: Database, profile_currency: str):
        self.db = db
        self.profile_currency = profile_currency

    def save(self, currency: str, day: str, rate: object) -> None:
        currency = (currency or "").strip().upper()
        if currency == self.profile_currency:
            raise ValidationError("The profile currency already has a rate of 1.", "currency")
        if not self.db.scalar("SELECT 1 FROM registered_currencies WHERE code=?", (currency,)):
            raise ValidationError("Register this currency first.", "currency")
        on = parse_date(day, "date")
        if on > today():
            raise ValidationError("The rate date cannot be in the future.", "date")
        value = check_places(to_decimal(rate, "rate"), 6)
        if value <= 0:
            raise ValidationError("Enter a rate greater than zero.", "rate")
        with self.db.transaction():
            self.db.execute(
                "INSERT INTO fx_rates(date,base,quote,rate_e6,source,created_at) "
                "VALUES(?,?,?,?,'MANUAL',?) ON CONFLICT(date,base,quote,source) "
                "DO UPDATE SET rate_e6=excluded.rate_e6,created_at=excluded.created_at",
                (fmt_date(on), currency, self.profile_currency, to_e6(value), now_iso()),
            )

    def list(self) -> list[dict]:
        rows = self.db.all(
            "SELECT date,base AS currency,quote,rate_e6,source FROM fx_rates "
            "WHERE quote=? ORDER BY date DESC,base,source LIMIT 300", (self.profile_currency,))
        return [dict(row) | {"rate": from_e6(row["rate_e6"])} for row in rows]
