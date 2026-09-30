from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response

from lightning.core.dates import fmt_date, month_of, today
from lightning.core.errors import LightningError, ValidationError
from lightning.core.money import ZERO, to_decimal

from ..web import container, redirect, render
from ..periods import Period, parse_period
from ..charts import line_chart
from .. import charts, keynotes, visuals

router = APIRouter(prefix="/birdview")


def _own_holdings(c, day):
    rows, unvalued = c.position.owned_holdings(day)
    return rows, unvalued


def _period(c, query):
    if str(query.get("period", "month")) == "custom" and (not query.get("date_from") or not query.get("date_to")):
        period = parse_period({"period": "month", "month": query.get("month", month_of(today()))}, today(), c.reporting.first_activity_date())
        return Period("custom", "Custom", period.start, period.end)
    return parse_period(query, today(), c.reporting.first_activity_date())


@router.get("")
async def birdview(request: Request):
    """Birdview was folded into the Overview; old links land there with the same period."""
    return redirect("/" + (f"?{request.url.query}" if request.url.query else ""))


@router.get("/class/{class_id:int}")
async def class_popup(request: Request, class_id: int):
    c = container(request)
    day = str(request.query_params.get("as_of", fmt_date(today())))
    try:
        date.fromisoformat(day)
    except ValueError:
        day = fmt_date(today())
    cls = c.assets.get_class(class_id)
    rows, _ = _own_holdings(c, day)
    rows = [r for r in rows if r["class_code"] == cls.code]
    return render(request, "birdview/class_popup.html", asset_class=cls, rows=rows, as_of=day)


@router.get("/expenses")
async def expense_analysis(request: Request):
    c = container(request)
    try:
        selected = _period(c, request.query_params)
        error = ""
    except LightningError as exc:
        fallback = _period(c, {"period": "month", "month": month_of(today())})
        selected = Period("custom", "Custom", fallback.start, fallback.end) if request.query_params.get("period") == "custom" else fallback
        error = exc.message
    first, last = selected.start, selected.end
    flow = c.reporting.cash_flow(first, last)
    l1 = c.reporting.spending_by_category(first, last, depth=1)
    l2 = c.reporting.spending_by_category(first, last, depth=2)
    for group in l1 + l2:
        group.category_id = c.categories.get_by_code(group.code).id
    prior = None
    if selected.key != "all":
        if selected.key == "month":
            prior_to = first - timedelta(days=1)
            prior_from = prior_to.replace(day=1)
            prior_to = date(prior_to.year, prior_to.month, calendar.monthrange(prior_to.year, prior_to.month)[1])
        elif selected.key == "ytd":
            prior_from = date(first.year - 1, 1, 1)
            prior_to = date(first.year - 1, last.month, min(last.day, calendar.monthrange(first.year - 1, last.month)[1]))
        else:
            prior_to = first - timedelta(days=1)
            prior_from = prior_to - (last - first)
        prior = c.reporting.cash_flow(prior_from, prior_to)
    trend_first = first.replace(day=1)
    trend_count = (last.year - trend_first.year) * 12 + last.month - trend_first.month + 1
    trend_truncated = trend_count > 24
    if trend_count > 24:
        trend_first = last.replace(day=1)
        for _ in range(23):
            trend_first = (trend_first - timedelta(days=1)).replace(day=1)
    trend = c.reporting.monthly_flow_between(max(first, trend_first), last)
    category_filter = str(request.query_params.get("category_id", ""))
    category_code = ""
    category_name = ""
    selected_category = None
    if category_filter.isdigit():
        selected_category = c.categories.get(int(category_filter))
        category_code, category_name = selected_category.code, selected_category.name
        l2 = [x for x in l2 if x.code.startswith(category_code)]
        l1 = [x for x in l1 if category_code.startswith(x.code) or x.code.startswith(category_code)]
    if selected_category:
        depth = selected_category.depth
        def selected_spending(start, end):
            return sum((group.value for group in c.reporting.spending_by_category(start, end, depth=depth)
                        if group.code == category_code), ZERO)
        spending_total = selected_spending(first, last)
        prior_spending = selected_spending(prior_from, prior_to) if prior else None
        for item in trend:
            item["outflows"] = selected_spending(item["date_from"], item["date_to"])
    else:
        spending_total = flow.outflows
        prior_spending = prior.outflows if prior else None
    trend_chart = line_chart([item["outflows"] for item in trend])
    groups = l2 if l2 else l1
    bar_rows = [{"group": g.label.split(" › ")[0], "label": g.label.split(" › ")[-1], "value": g.value,
                 "href": f"/transactions?category_id={g.category_id}&date_from={fmt_date(first)}&date_to={fmt_date(last)}"}
                for g in groups if g.value > 0]
    category_bars = charts.grouped_bars(bar_rows, limit=10)
    spend_trend = visuals.spending_trend(c, last, category_code, count=max(6, min(len(trend), 24)))
    prior_label = (prior_from.strftime("%Y-%m") if selected.key == "month" else "the period before") if prior else ""
    notes = [n for n in (keynotes.top_category(bar_rows, spending_total, ""),
                         keynotes.compared(spending_total, prior_spending, prior_label)) if n]
    usual = []
    if selected.key == "month":  # "your usual month" only compares like with like: one month
        usual = [r for r in c.reporting.spending_vs_usual(first, last)
                 if not category_code or r["code"].startswith(category_code)]
    largest = c.reporting.largest_payments(first, last, 6)
    for row in largest:
        row["category"] = c.categories.get(row["category_id"]).name if row["category_id"] else ""
    return render(request, "birdview/expenses.html", notes=notes, category_bars=category_bars, spend_trend=spend_trend,
                  usual=visuals.usual_rows(usual), who_bars=visuals.counterparty_bars(c, first, last),
                  account_bars=visuals.account_bars(c, first, last), largest=largest,
                  period=selected.key, month=last.strftime("%Y-%m"),
                  custom_from=request.query_params.get("date_from", ""), custom_to=request.query_params.get("date_to", ""),
                  date_from=fmt_date(first), date_to=fmt_date(last), start_display=selected.start_display,
                  end_display=selected.end_display, flow=flow, l1=l1, l2=l2, prior=prior, trend=trend,
                  category_filter=category_filter, category_code=category_code, category_name=category_name, error=error,
                  spending_total=spending_total, prior_spending=prior_spending,
                  trend_truncated=trend_truncated, trend_chart=trend_chart,
                  base=c.reporting.base_currency)


@router.post("/settings")
async def save_legacy_settings(request: Request):
    c = container(request)
    form = await request.form()
    try:
        factor = to_decimal(str(form.get("factor", "")), "factor")
        if not ZERO <= factor <= Decimal(100):
            raise ValidationError("Enter a liquidation factor from 0 to 100.", "factor")
    except LightningError as exc:
        return Response(exc.message, status_code=400, media_type="text/plain")
    c.investments.set_all_liquidation_factors(factor)
    c.settings.set("investment_liquidation_factor", str(factor))
    return Response(status_code=204)


@router.get("/settings")
async def settings_legacy(request: Request):
    return redirect("/settings?section=assets-valuations&return_to=%2Fbirdview")
