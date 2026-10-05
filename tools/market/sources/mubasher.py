"""Mubasher Info: every Egyptian mutual fund's latest NAV in one request, and each fund's whole NAV
history as one small CSV. Endpoints as used daily by the open-source egypt-funds-tracker. Mubasher's
robots.txt asks automated clients to keep off /api/: one request a day at most (proposal › Rights)."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from lightning.market.bundle import Instrument

from ..model import Quote, SourceError, SourceResult

FUNDS = "https://english.mubasher.info/api/1/funds"
HISTORY = "https://static.mubasher.info/File.MubasherCharts/File.Mutual_Fund_Charts_Dir/priceChartFund_{fund_id}.csv"
# Mubasher's classification ids, as Lightning asset classes.
CLASSES = {14: "FUND.EQUITY", 9: "FUND.EQUITY", 13: "FUND.EQUITY", 11: "FUND.MONEY_MARKET", 6: "FUND.FIXED_INCOME",
           3: "FUND.FIXED_INCOME", 15: "FUND.FIXED_INCOME", 18: "FUND.GOLD"}
_MONTHS = {name: n for n, name in enumerate(("january", "february", "march", "april", "may", "june", "july",
                                             "august", "september", "october", "november", "december"), 1)}
_USD = re.compile(r"\bUSD\b|dollar|دولار", re.IGNORECASE)


def list_date(text: str | None) -> str | None:
    """'17 September 2026' -> '2026-09-17'."""
    parts = " ".join(str(text or "").split()).split(" ")
    if len(parts) != 3 or parts[1].lower() not in _MONTHS:
        return None
    try:
        return date(int(parts[2]), _MONTHS[parts[1].lower()], int(parts[0])).isoformat()
    except ValueError:
        return None


def parse_funds(data: dict, classes: dict[int, str] | None = None) -> SourceResult:
    """The fund list as instruments (EG:FUND:<id>) and each fund's latest NAV on its own date."""
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise SourceError("Mubasher's fund list answered without rows")
    if (data.get("numberOfPages") or 1) > 1:
        raise SourceError("Mubasher split the fund list into pages; the adapter reads one page")
    result = SourceResult("mubasher-funds")
    for row in data["rows"]:
        try:
            fund_id, name = int(row["fundId"]), " ".join(str(row["name"]).split())
            nav = Decimal(str(row.get("price") or 0))
        except (KeyError, ValueError, InvalidOperation, TypeError):
            continue
        key = f"EG:FUND:{fund_id}"
        result.instruments.append(Instrument(
            key=key, name=name, category=(classes or {}).get(fund_id, "FUND.OTHER"), country="EG",
            currency="USD" if _USD.search(name) else "EGP", unit="unit", sources={"mubasher": str(fund_id)}))
        day = list_date(row.get("date"))
        if day and nav.is_finite() and nav > 0:
            result.quotes.append(Quote(key, day, nav, result.source))
    return result


def parse_history(text: str, key: str) -> list[Quote]:
    """A fund's history CSV (date,nav per line) as quotes; unreadable lines are skipped."""
    if text.lstrip().startswith("<"):
        raise SourceError("Mubasher returned a web page instead of a fund history")
    quotes = []
    for line in text.splitlines():
        stamp, _, value = line.strip().partition(",")
        try:
            day = date.fromisoformat(stamp[:10].replace("/", "-")).isoformat()
            nav = Decimal(value.strip())
        except (ValueError, InvalidOperation):
            continue
        if nav.is_finite() and nav > 0:
            quotes.append(Quote(key, day, nav, "mubasher-history"))
    return quotes


def fetch(session, classes: dict[int, str] | None = None) -> SourceResult:
    return parse_funds(session.get_json(FUNDS, {"country": "eg", "size": 1000}), classes)


def fetch_history(session, key: str, fund_id: str) -> list[Quote]:
    return parse_history(session.get_text(HISTORY.format(fund_id=fund_id)), key)
