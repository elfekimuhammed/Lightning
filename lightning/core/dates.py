"""Dates are always ISO ``yyyy-mm-dd`` — in storage, on screen, in files."""

from __future__ import annotations

import calendar
import os
import re
from datetime import date, datetime, timedelta

from .errors import ValidationError

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def parse_date(value: object, field: str = "date") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not _DATE_RE.match(text):
        raise ValidationError("Use the date format yyyy-mm-dd, e.g. 2026-12-31.", field)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValidationError(f"{text} is not a real calendar date.", field) from None


def fmt_date(value: date) -> str:
    return value.isoformat()


def today() -> date:
    """The current date. Tests can pin it with the LIGHTNING_TODAY environment variable (yyyy-mm-dd)."""
    pinned = os.environ.get("LIGHTNING_TODAY")
    return date.fromisoformat(pinned) if pinned else date.today()


def now_iso() -> str:
    """Local timestamp with UTC offset, e.g. 2026-09-25T16:00:00+03:00."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_month(value: str, field: str = "month") -> tuple[date, date]:
    """``2026-09`` -> (2026-09-01, 2026-09-30)."""
    text = str(value or "").strip()
    if not _MONTH_RE.match(text):
        raise ValidationError("Use the month format yyyy-mm, e.g. 2026-09.", field)
    year, month = int(text[:4]), int(text[5:7])
    if not 1900 <= year <= 9998:
        raise ValidationError("Choose a month from 1900 through 9998.", field)
    if not 1 <= month <= 12:
        raise ValidationError(f"{text} is not a valid month.", field)
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def month_of(value: date) -> str:
    return value.strftime("%Y-%m")


def previous_day(value: date) -> date:
    return value - timedelta(days=1)
