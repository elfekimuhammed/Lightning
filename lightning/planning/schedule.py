"""Expand a planned item's schedule into dated payments (pure functions)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from .domain import Frequency, PlannedItem

_MONTH_STEP = {Frequency.MONTHLY: 1, Frequency.QUARTERLY: 3, Frequency.YEARLY: 12}


def _add_months(anchor: date, months: int) -> date:
    """Same day of month, clamped to the month's last day (31 → 30/28/29)."""
    index = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(anchor.day, last))


def payment_dates(item: PlannedItem, until: str | date) -> list[tuple[int, str]]:
    """(payment number, date) for every payment from the first date up to ``until`` inclusive."""
    end = until if isinstance(until, date) else date.fromisoformat(until)
    if item.end_date:
        end = min(end, date.fromisoformat(item.end_date))
    start = date.fromisoformat(item.start_date)
    limit = item.payment_count
    out: list[tuple[int, str]] = []
    number = 0
    while True:
        if item.frequency == Frequency.ONCE:
            day = start if number == 0 else None
        elif item.frequency == Frequency.WEEKLY:
            day = start + timedelta(weeks=item.interval_count * number)
        else:
            day = _add_months(start, _MONTH_STEP[item.frequency] * item.interval_count * number)
        if day is None or day > end or (limit is not None and number >= limit):
            return out
        number += 1
        out.append((number, day.isoformat()))


def last_payment_date(item: PlannedItem) -> str | None:
    """The final payment date when the schedule has a fixed end, else None."""
    if item.payment_count is None and not item.end_date:
        return None
    if item.frequency == Frequency.ONCE:
        return item.start_date
    horizon = item.end_date or "9999-12-31"
    dates = payment_dates(item, horizon if item.end_date else "2999-12-31")
    return dates[-1][1] if dates else None


def describe(item: PlannedItem) -> str:
    """Plain wording such as "Monthly on day 20" or "Every 2 weeks from 2026-09-03"."""
    start = date.fromisoformat(item.start_date)
    every = item.interval_count
    if item.frequency == Frequency.ONCE:
        text = f"Once on {item.start_date}"
    elif item.frequency == Frequency.WEEKLY:
        text = ("Weekly" if every == 1 else f"Every {every} weeks") + f" from {item.start_date}"
    elif item.frequency == Frequency.MONTHLY:
        text = ("Monthly" if every == 1 else f"Every {every} months") + f" on day {start.day}"
    elif item.frequency == Frequency.QUARTERLY:
        text = ("Every 3 months" if every == 1 else f"Every {3 * every} months") + f" on day {start.day}"
    else:
        text = ("Yearly" if every == 1 else f"Every {every} years") + f" on {start:%m-%d}"
    if item.payment_count:
        text += f" · {item.payment_count} payments"
    elif item.end_date:
        text += f" · until {item.end_date}"
    return text
