from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.dates import fmt_date, month_of, parse_month, today
from lightning.core.errors import ValidationError
from lightning.transactions.domain import TxnFilter

from ..web import container, render

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    c = container(request)
    month = request.query_params.get("month") or month_of(today())
    try:
        first, last = parse_month(month)
    except ValidationError:
        month = month_of(today())
        first, last = parse_month(month)
    as_of = min(last, today()) if first <= today() else last
    accounts = c.accounts.list()
    if not accounts:
        return render(request, "dashboard/welcome.html")
    net_worth = c.reporting.net_worth(as_of)
    recent, _ = c.transactions.find(TxnFilter(limit=8))
    return render(
        request,
        "dashboard/index.html",
        month=month,
        as_of=fmt_date(as_of),
        net_worth=net_worth,
        # everything on the page is measured to the same day: today in the current month, else month end
        cash_flow=c.reporting.cash_flow(first, as_of),
        bridge=c.reporting.bridge(first, as_of),
        spending=c.reporting.spending_by_category(first, as_of, depth=2)[:8],
        trend=c.reporting.monthly_trend(month, 6),
        recent=recent,
        budget=c.budgets.month_view(month),
    )
