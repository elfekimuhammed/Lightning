"""Market data adapters (M4).

Every price source implements ``PriceProvider``. Planned adapters:
Yahoo Finance (EGX via ``.CA`` symbols), gold parity (XAU/USD x USD/EGP / 31.1035),
local Egyptian gold sites, manual entry and CSV. Prices land in ``price_history``
with their ``source``; manual prices always win over automatic ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    external_symbol: str
    date: date
    price: Decimal
    currency: str
    source: str


class PriceProvider(Protocol):
    source: str

    def fetch(self, symbols: list[str], on: date) -> list[Quote]:
        """Return quotes for the symbols it knows; never raise for one bad symbol."""
        ...
