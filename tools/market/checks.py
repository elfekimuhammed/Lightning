"""What a quote must pass before it reaches the market file (proposal › Checks before anything is published)."""
from __future__ import annotations

from decimal import Decimal

from lightning.market.bundle import Close

from lightning.market.model import Quote

# How far one close may move from the last published one without a second source agreeing.
LIMITS = {"STOCK": Decimal("0.20"), "FUND": Decimal("0.15"), "CURRENCY": Decimal("0.15"), "GOLD": Decimal("0.15"),
          "INDEX": Decimal("0.15")}
# How close two sources must be to count as agreeing.
TOLERANCE = {"STOCK": Decimal("0.01"), "FUND": Decimal("0.005"), "CURRENCY": Decimal("0.005"), "GOLD": Decimal("0.02"),
             "INDEX": Decimal("0.01")}
OFFICIAL = {"cbe", "banque-misr"}  # first-party bank bulletin: a verified devaluation is not suppressed
# The fewest rows a healthy answer has; fewer means the source is broken or blocking us.
MINIMUM_ROWS = {"tradingview-egx": 150, "tradingview-us": 400, "tradingview-gcc": 300, "tradingview-europe": 700,
                "mubasher-funds": 100, "cbe": 5, "banque-misr": 10}
SPLIT_RATIO = Decimal("1.9")  # a fund NAV moving this much at once is a unit split, not a price


def family(category: str) -> str:
    return "FUND" if category.startswith("FUND") else category


def accept(candidates: list[Quote], published: dict[str, list[Close]], categories: dict[str, str], today: str,
           history: bool = False) -> tuple[list[Quote], list[str]]:
    """Choose one quote per instrument and day from `candidates`, which come in source priority order.

    A quote is used when it moves no more than its limit from the last published close, or another source
    agrees with it, or it is official; otherwise the day is held back and reported. History from one source
    is not jump-checked day to day, but every quote must be above zero and not in the future."""
    accepted, problems = [], []
    groups: dict[tuple[str, str], list[Quote]] = {}
    for quote in candidates:
        if quote.date > today or quote.close <= 0:
            problems.append(f"{quote.source}: {quote.key} {quote.date} {quote.close} is in the future or not above zero")
            continue
        groups.setdefault((quote.key, quote.date), []).append(quote)
    for (key, day), quotes in sorted(groups.items()):
        kind = family(categories.get(key, "STOCK"))
        limit, tolerance = LIMITS.get(kind, Decimal("0.15")), TOLERANCE.get(kind, Decimal("0.01"))
        earlier = [c for c in published.get(key, []) if c.date < day]
        previous = earlier[-1].close if earlier else None
        chosen = None
        for quote in quotes:
            agrees = any(other.source != quote.source and abs(other.close / quote.close - 1) <= tolerance
                         for other in quotes)
            move = abs(quote.close / previous - 1) if previous else Decimal(0)
            split = kind == "FUND" and previous and (quote.close / previous >= SPLIT_RATIO
                                                     or previous / quote.close >= SPLIT_RATIO)
            if history or previous is None or move <= limit or agrees or quote.source in OFFICIAL:
                chosen = quote
                break
            if split:
                chosen = quote
                problems.append(f"{quote.source}: {key} {day} moved {quote.close / previous:.2f}x at once; kept as a unit split")
                break
        if chosen is None:
            first = quotes[0]
            problems.append(f"{first.source}: {key} {day} held back, it moved {abs(first.close / previous - 1):.0%} "
                            f"from {previous} and no second source agrees")
            continue
        for other in quotes:
            if other.source != chosen.source and abs(other.close / chosen.close - 1) > tolerance:
                problems.append(f"{key} {day}: {chosen.source} says {chosen.close}, {other.source} says {other.close}")
        accepted.append(chosen)
    return accepted, problems
