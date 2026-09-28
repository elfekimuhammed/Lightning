"""Shared date range contract for Overview and Birdview."""

from dataclasses import dataclass
from datetime import date

from lightning.core.dates import fmt_date, month_of, parse_month
from lightning.core.errors import ValidationError


@dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: date
    end: date

    @property
    def start_text(self) -> str:
        return fmt_date(self.start)

    @property
    def end_text(self) -> str:
        return fmt_date(self.end)

    @property
    def start_display(self) -> str:
        return self.start.strftime("%d %b %Y")

    @property
    def end_display(self) -> str:
        return self.end.strftime("%d %b %Y")


def parse_period(query, today: date, first_activity: str | None = None) -> Period:
    """Parse all|ytd|month|custom. Invalid selections raise a user-facing error."""
    key = str(query.get("period", "month"))
    if key == "all":
        start = date.fromisoformat(first_activity) if first_activity else today
        return Period("all", "All time", start, today)
    if key == "ytd":
        return Period("ytd", "YTD", date(today.year, 1, 1), today)
    if key == "custom":
        try:
            start, end = date.fromisoformat(str(query.get("date_from", ""))), date.fromisoformat(str(query.get("date_to", "")))
        except ValueError:
            raise ValidationError("Choose both dates for a custom timeline.") from None
        if end < start:
            raise ValidationError("The end date must be on or after the start date.")
        if end > today:
            raise ValidationError("The end date cannot be later than today.")
        return Period(key, "Custom", start, end)
    if key != "month":
        raise ValidationError("Choose All time, YTD, Monthly, or Custom.")
    month = str(query.get("month", month_of(today)))
    start, end = parse_month(month)
    if start > today:
        raise ValidationError("Choose a month that has started.")
    return Period("month", "Monthly", start, min(end, today))
