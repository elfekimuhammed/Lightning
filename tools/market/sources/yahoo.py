"""Yahoo's chart feed, for history only: a whole series of daily closes per instrument in one request.

Yahoo's closes are adjusted for later splits (and EGX bonus shares), but a past holding must be valued
at the price it actually traded at, so each close is multiplied back by the splits that came after it."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from zoneinfo import ZoneInfo

from ..model import Quote, SourceError

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def symbol_for(key: str) -> str | None:
    """EG:COMI -> COMI.CA, US:BRK.B -> BRK-B, USD/EGP -> EGP=X; others have no Yahoo symbol."""
    if key.startswith("EG:") and ":FUND:" not in key:
        return key[3:] + ".CA"
    if key.startswith("US:"):
        return key[3:].replace(".", "-")
    if key.endswith("/EGP") and key[:3] == "USD":
        return "EGP=X"
    return None


def parse(data: dict, key: str, zone: str = "Africa/Cairo") -> list[Quote]:
    try:
        result = data["chart"]["result"][0]
        stamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
        splits = (result.get("events") or {}).get("splits") or {}
    except (KeyError, IndexError, TypeError):
        raise SourceError(f"Yahoo's chart answer for {key} has no price series") from None
    events = []
    for split in splits.values():
        try:
            events.append((int(split["date"]), Decimal(str(split["numerator"])) / Decimal(str(split["denominator"]))))
        except (KeyError, ValueError, InvalidOperation, ZeroDivisionError):
            continue
    tz = ZoneInfo(zone)
    quotes: dict[str, Quote] = {}
    for stamp, value in zip(stamps, closes):
        if value is None:
            continue
        try:
            close = Decimal(str(value))
        except InvalidOperation:
            continue
        for when, ratio in events:  # undo every split that happened after this day
            if when > stamp:
                close *= ratio
        if close.is_finite() and close > 0:
            day = datetime.fromtimestamp(int(stamp), tz).date().isoformat()
            quotes[day] = Quote(key, day, close.quantize(Decimal("0.000001")), "yahoo-history")
    return [quotes[d] for d in sorted(quotes)]


def fetch_history(session, key: str, since: str = "max") -> list[Quote]:
    symbol = symbol_for(key)
    if not symbol:
        return []
    data = session.get_json(CHART.format(symbol=quote(symbol, safe="")),
                            {"range": since, "interval": "1d", "events": "split"})
    zone = "America/New_York" if key.startswith("US:") else "Africa/Cairo"
    return parse(data, key, zone)
