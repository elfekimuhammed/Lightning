"""Turns quantities into base-currency value.

value = quantity x price (on or before the date) x FX rate (asset currency -> base)
- Base-currency cash is always worth its quantity.
- Anything without a price/rate is reported as "unvalued" instead of silently counted as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lightning.assets.domain import FinancialAsset
from lightning.core.money import ONE, from_e6

from .queries import ReportQueries


@dataclass
class Valuation:
    value: Decimal | None  # None = missing price or FX rate
    price: Decimal | None
    price_date: str | None
    reason: str = ""


class Valuer:
    def __init__(self, queries: ReportQueries, base_currency: str):
        self.q = queries
        self.base = base_currency

    def value(self, asset: FinancialAsset, quantity: Decimal, as_of: date | str) -> Valuation:
        day = as_of if isinstance(as_of, str) else as_of.isoformat()
        if asset.is_cash:
            price, price_date = ONE, None
        else:
            row = self.q.latest_price(asset.id, day)
            if row is None:
                return Valuation(None, None, None, f"No price for {asset.code} on or before {day}")
            price, price_date = from_e6(row["price_e6"]), row["date"]
        fx = self._fx(asset.currency, day)
        if fx is None:
            return Valuation(None, price, price_date, f"No {asset.currency}/{self.base} rate on or before {day}")
        return Valuation((quantity * price * fx).quantize(Decimal("0.000001")), price, price_date)

    def _fx(self, currency: str, day: str) -> Decimal | None:
        if currency == self.base:
            return ONE
        row = self.q.latest_fx(currency, self.base, day)
        return from_e6(row["rate_e6"]) if row else None
