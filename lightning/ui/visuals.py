"""Chart data for pages: read figures from services, then shape them with lightning.ui.charts.

No financial calculation happens here: every value is a figure a service computed.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from lightning.core.dates import fmt_date, month_of, parse_date, parse_month
from lightning.core.money import ZERO

from . import charts


def months_back(end: date, count: int, first_activity: str | None) -> list[str]:
    """Up to ``count`` months ending with ``end``'s month, never before the first recorded activity."""
    keys, cursor = [], end.replace(day=1)
    floor = parse_date(first_activity).replace(day=1) if first_activity else cursor
    while len(keys) < count and cursor >= floor:
        keys.append(month_of(cursor))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(keys))


def flow_trend(c, end: date, count: int = 6) -> dict:
    """Money in and money out per month (the same figures as Cash flow), ending with ``end``."""
    keys = months_back(end, count, c.reporting.first_activity_date())
    if not keys:
        return charts.trend([], [])
    rows = {r["month"]: r for r in c.reporting.monthly_flow_between(parse_month(keys[0])[0], end)}
    return charts.trend(keys, [
        {"name": "Money in", "tone": "in", "values": [rows.get(k, {}).get("inflows", ZERO) for k in keys]},
        {"name": "Money out", "tone": "spend", "values": [rows.get(k, {}).get("outflows", ZERO) for k in keys]},
    ])


def spending_trend(c, end: date, category_code: str = "", count: int = 6) -> dict:
    """Money out per month, with the month's plan as a dashed line when one exists."""
    keys = months_back(end, count, c.reporting.first_activity_date())
    if not keys:
        return charts.trend([], [])
    if category_code:
        values = []
        depth = c.categories.get_by_code(category_code).depth
        for key in keys:
            first, last = parse_month(key)
            last = min(last, end)
            values.append(sum((g.value for g in c.reporting.spending_by_category(first, last, depth=depth)
                               if g.code == category_code), ZERO))
    else:
        rows = {r["month"]: r for r in c.reporting.monthly_flow_between(parse_month(keys[0])[0], end)}
        values = [rows.get(k, {}).get("outflows", ZERO) for k in keys]
    plan, over = None, None
    if not category_code:
        # Each month is over (or not) against its own plan; the dashed line is the latest month's.
        plans = [c.budgets.month_view(k).available if c.budgets.has_plan(k) else None for k in keys]
        over = [p is not None and v > p for p, v in zip(plans, values)]
        plan = plans[-1] or None
    return charts.trend(keys, [{"name": "Money out", "tone": "hold", "values": values, "area": True, "over": over}],
                        plan=plan)


def spending_bars(c, first: date, last: date, limit: int = 6) -> dict:
    """Money out by category (level 2), largest first, each linking to its transactions."""
    rows = []
    for group in c.reporting.spending_by_category(first, last, depth=2):
        if group.value <= 0:
            continue
        category = c.categories.get_by_code(group.code)
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first), "date_to": fmt_date(last)})
        parent = c.categories.get(category.parent_id).name if category.parent_id else ""
        rows.append({"label": category.name, "value": group.value, "href": f"/transactions?{query}",
                     "note": parent if parent and parent != "Personal" else ""})
    return charts.bars(rows, limit)


def holdings_donut(position, include_deposits: bool = False, include_cash: bool = False) -> dict:
    """What you hold by asset class, in class colours (cash, deposits, gold, equity, other)."""
    slices = []
    if include_cash and position.cash_you_own:
        slices.append({"label": "Cash you own", "value": position.cash_you_own, "tone": "cash"})
    for cls in position.classes:
        if cls.is_deposit and not include_deposits:
            continue
        slices.append({"label": cls.name, "value": cls.value, "tone": charts.class_tone(cls.code)})
    if include_cash and position.other_you_own > 0:
        slices.append({"label": "Other you own", "value": position.other_you_own, "tone": "other"})
    return charts.donut(slices)


def portfolio_trend(values: list[tuple[str, Decimal | None]]) -> dict:
    """Portfolio value per month, starting at the first month that held anything."""
    started = False
    kept = []
    for label, value in values:
        if not started and not value:
            continue
        started = True
        kept.append((label, value))
    return charts.trend([k for k, _ in kept], [{"name": "Portfolio value", "tone": "hold",
                                                "values": [v for _, v in kept], "area": True}])


def forecast_trend(forecast) -> dict:
    """The forecast's Ends with for each month."""
    labels = [m.month for m in forecast.months]
    values = [m.closing for m in forecast.months]
    return charts.trend(labels, [{"name": "Ends with", "tone": "hold", "values": values, "area": True}])
