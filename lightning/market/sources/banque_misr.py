"""Banque Misr's public transfer buy/sell quotes, expressed as an EGP midpoint per currency unit.

The bank publishes a dated bulletin on its public rates page. Transfer quotes are preferred to
banknotes, because several currencies have zero banknote quotes but valid transfer quotes.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from lightning.market.bundle import Instrument
from lightning.market.model import Quote, SourceError, SourceResult

from .cbe import CURRENCY_NAMES, _Rows, _code

URL = "https://banquemisr.com/Home/CAPITAL%20MARKETS/Exchange%20rates%20and%20currencies?sc_lang=en"
_DATE = re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\s+\d{2}:\d{2}:\d{2}\b")
_ALIASES = {"sterling pound": "GBP", "u.s. dollar": "USD", "yuan": "CNY"}


def _named(cell: str) -> tuple[str, Decimal] | None:
    found = _code(cell)
    if found:
        return found
    text = cell.casefold()
    for name, code in _ALIASES.items():
        if name in text:
            return code, Decimal(100) if "100" in text else Decimal(1)
    return None


def _number(cell: str) -> Decimal | None:
    try:
        return Decimal(cell.replace(",", "").strip())
    except InvalidOperation:
        return None


def parse(html: str, today: str) -> SourceResult:
    page = _Rows()
    page.feed(html)
    match = _DATE.search(" ".join(page.text))
    if not match:
        raise SourceError("Banque Misr's rate bulletin has no dated timestamp")
    try:
        day = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    except ValueError:
        raise SourceError("Banque Misr's rate bulletin has an invalid date") from None
    if day > today:
        raise SourceError("Banque Misr's rate bulletin is dated in the future")
    result = SourceResult("banque-misr")
    for row in page.rows:
        if len(row) < 5 or not (named := _named(row[0])):
            continue
        notes = (_number(row[1]), _number(row[2]))
        transfer = (_number(row[3]), _number(row[4]))
        pair = transfer if all(v is not None and v > 0 for v in transfer) else notes
        if any(v is None or v <= 0 for v in pair):
            continue
        buy, sell = pair
        if sell < buy or sell / buy > Decimal("1.10"):
            continue  # a shifted column or invalid spread is not a rate
        code, per = named
        key = f"{code}/EGP"
        if any(i.key == key for i in result.instruments):
            continue
        mid = ((buy + sell) / 2 / per).quantize(Decimal("0.000001"))
        result.instruments.append(Instrument(key=key, name=CURRENCY_NAMES.get(code, code), category="CURRENCY",
                                             currency="EGP", unit=code, sources={"banque-misr": code}))
        result.quotes.append(Quote(key, day, mid, result.source))
    if not any(i.key == "USD/EGP" for i in result.instruments):
        raise SourceError("Banque Misr's rates page has no US dollar transfer quote")
    return result


def fetch(session, today: str) -> SourceResult:
    return parse(session.get_text(URL), today)
