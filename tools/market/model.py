"""What adapters return: instruments they list and the closes they report."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from lightning.market.bundle import Instrument


class SourceError(RuntimeError):
    """A source answered with something other than the data we expect: blocked, moved or changed."""


@dataclass(frozen=True)
class Quote:
    key: str
    date: str
    close: Decimal
    source: str


@dataclass
class SourceResult:
    source: str
    instruments: list[Instrument] = field(default_factory=list)
    quotes: list[Quote] = field(default_factory=list)
