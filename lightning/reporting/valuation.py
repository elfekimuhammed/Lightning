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
    source: str = ""  # MANUAL (a price you typed) · TRADE (last buy/sell) · COST (what you paid) · CASH


class Valuer:
    def __init__(self, queries: ReportQueries, base_currency: str):
        self.q = queries
        self.base = base_currency

    def value(self, asset: FinancialAsset, quantity: Decimal, as_of: date | str) -> Valuation:
        day = as_of if isinstance(as_of, str) else as_of.isoformat()
        if asset.is_cash:
            price, price_date, source = ONE, None, "CASH"
        else:
            found = self._price(asset, day)
            if found is None:
                return Valuation(None, None, None, f"No price for {asset.label} on or before {day}")
            price, price_date, source = found
        fx = self._fx(asset.currency, day)
        if fx is None:
            return Valuation(None, price, price_date, f"No {asset.currency}/{self.base} rate on or before {day}")
        return Valuation((quantity * price * fx).quantize(Decimal("0.000001")), price, price_date, "", source)

    def _price(self, asset: FinancialAsset, day: str) -> tuple[Decimal, str, str] | None:
        """Newest of: a price you entered, the last buy/sell price. A typed price wins on the same day.
        Holdings entered as already owned fall back to their cost until a price exists."""
        typed = self.q.latest_price(asset.id, day)
        trade = self.q.latest_trade_price(asset.id, day)
        if typed and (not trade or typed["date"] >= trade["date"]):
            return from_e6(typed["price_e6"]), typed["date"], typed["source"]
        if trade:
            return from_e6(trade["price_e6"]), trade["date"], "TRADE"
        cost = self.q.average_opening_cost(asset.id, day)
        if cost:
            per_unit = Decimal(cost["amount"]) / Decimal(cost["qty"])  # unrounded: value comes out at exact cost
            return per_unit, cost["date"], "COST"
        return None

    def _fx(self, currency: str, day: str) -> Decimal | None:
        if currency == self.base:
            return ONE
        row = self.q.latest_fx(currency, self.base, day)
        return from_e6(row["rate_e6"]) if row else None
