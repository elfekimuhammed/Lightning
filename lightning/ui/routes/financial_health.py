from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.dates import parse_date, today
from lightning.core.errors import ValidationError

from .. import charts
from ..web import container, render

router = APIRouter()


@router.get("/financial-health")
async def financial_health(request: Request):
    c = container(request)
    raw = request.query_params.get("as_of")
    try:
        as_of = parse_date(raw, "as-of date") if raw else today()
        if as_of > today():
            raise ValidationError("Choose today or an earlier as-of date.", "as_of")
    except ValidationError as exc:
        as_of = today()
        error = exc.message
    else:
        error = ""
    overview = c.health.overview(as_of)
    trends = overview["trends"]
    savings_values = [month.savings_rate for month in trends]
    worth_values = [month.net_worth for month in trends]
    return render(request, "financial_health.html", **overview,
                  limits=c.health.limit_settings(),
                  as_of_iso=as_of.isoformat(),
                  today_iso=today().isoformat(),
                  savings_spark=(charts.sparkline(savings_values) if all(v is not None for v in savings_values)
                                 else {"points": ""}),
                  worth_spark=(charts.sparkline(worth_values) if all(v is not None for v in worth_values)
                               else {"points": ""}),
                  error=error)
