from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request, Response

from lightning.core.dates import fmt_date, month_of, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.core.money import ZERO, to_decimal

from ..web import container, redirect, render
from ..periods import parse_period

router = APIRouter(prefix="/birdview")


def _range(c, query):
    now = today()
    month = str(query.get("month", month_of(now)))
    period = parse_period(query, now, c.reporting.first_activity_date())
    return period.start, period.end, period.key, month, str(now.year), ""


@router.get("")
async def birdview(request: Request):
    c = container(request)
    requested_period = str(request.query_params.get("period", "month"))
    period = requested_period if requested_period in {"all", "ytd", "month", "custom"} else "month"
    month = str(request.query_params.get("month", month_of(today())))
    year = str(today().year)
    custom_from = str(request.query_params.get("date_from", ""))
    custom_to = str(request.query_params.get("date_to", ""))
    period_error = ""
    try:
        first, last, period, month, year, _ = _range(c, request.query_params)
    except LightningError as exc:
        period_error = exc.message
        first, month_end = parse_month(month_of(today()))
        last = min(month_end, today())
    factor = to_decimal(c.settings.get("investment_liquidation_factor") or "95")

    day = fmt_date(today())
    net_worth = c.reporting.net_worth(day)
    cash = c.reporting.owned_liquid_cash(day)
    reserve_summary = c.reserves.cash_summary(cash)
    portfolio = c.investments.portfolio(day)
    custody = {(row["account_id"], row["asset_id"]): row["units"]
               for row in c.money_from_others.investment_positions(day)}
    classes: dict[str, dict] = {}
    own_investment_value = ZERO
    own_investment_cost = ZERO
    realized_return = ZERO
    dividend_return = ZERO
    for position in portfolio.positions:
        custody_units = custody.get((position.account_id, position.asset_id), ZERO)
        held_value = (c.reporting.value_of(position.asset_id, custody_units, day).value
                      if custody_units and position.quantity else ZERO)
        held_value = held_value or ZERO
        held_cost = position.cost_basis * custody_units / position.quantity if custody_units and position.quantity else ZERO
        value = (position.value or ZERO) - held_value if position.is_open else ZERO
        cost = position.cost_basis - held_cost if position.is_open else ZERO
        own_share = max(Decimal(0), (position.quantity - custody_units) / position.quantity) if position.quantity else Decimal(1)
        realized = position.realized * own_share
        dividends = position.dividends * own_share
        own_investment_value += value
        own_investment_cost += cost
        realized_return += realized
        dividend_return += dividends
        group = classes.setdefault(position.asset_class, {"name": position.asset_class, "value": ZERO,
                                                            "capital": ZERO, "unrealized": ZERO, "realized": ZERO,
                                                            "dividends": ZERO, "returns": ZERO, "items": []})
        group["value"] += value
        group["capital"] += cost
        group["unrealized"] += value - cost
        group["realized"] += realized
        group["dividends"] += dividends
        group["returns"] += value - cost + realized + dividends
        group["items"].append({"name": position.asset_name, "account": position.account_label, "account_id": position.account_id,
                               "value": value, "capital": cost, "return": value - cost + realized + dividends,
                               "unrealized": value - cost, "realized": realized, "dividends": dividends,
                               "unit": position.unit, "quantity": position.quantity})

    brokerage_cash = c.reporting.owned_brokerage_cash(day)

    # Deposits and other owned assets keep their full value. Only open investment
    # positions receive the liquidation scenario; brokerage cash stays at face value.
    other_owned = net_worth.total - cash - brokerage_cash - own_investment_value
    if other_owned:
        classes["Other assets"] = {"name": "Other assets", "value": other_owned,
                                   "capital": other_owned, "unrealized": ZERO, "realized": ZERO,
                                   "dividends": ZERO, "returns": ZERO, "items": []}
    investment_assets = own_investment_value
    asset_total = cash + brokerage_cash + other_owned + investment_assets * factor / Decimal(100)
    cash_flow = c.reporting.cash_flow(first, last)
    spending = c.reporting.spending_by_category(first, last, depth=2)
    income = c.reporting.money_in_by_category(first, last)
    chart_start = first.replace(day=1)
    chart_months = (last.year - chart_start.year) * 12 + last.month - chart_start.month + 1
    if chart_months > 24:
        for _ in range(chart_months - 24):
            chart_start = (chart_start.replace(day=1) - timedelta(days=1)).replace(day=1)
    chart_from = max(first, chart_start)
    monthly_flow = c.reporting.monthly_flow_between(chart_from, last)
    reserves = c.reserves.list_active()
    largest_expense = max((group.value for group in spending), default=ZERO)
    largest_income = max((group.value for group in income), default=ZERO)
    largest_month = max((max(item["inflows"], item["outflows"]) for item in monthly_flow), default=ZERO)
    previous = None
    previous_label = ""
    if period != "all":
        duration = last - first
        previous_to = first - timedelta(days=1)
        previous_from = previous_to - duration
        if period == "month":
            previous_from = date(previous_to.year, previous_to.month, 1)
            previous_month_end = date(previous_from.year, previous_from.month,
                                      calendar.monthrange(previous_from.year, previous_from.month)[1])
            previous_to = min(previous_month_end, previous_from + duration)
        elif period == "ytd":
            previous_from = date(first.year - 1, 1, 1)
            previous_to = date(first.year - 1, last.month,
                               min(last.day, calendar.monthrange(first.year - 1, last.month)[1]))
        previous = c.reporting.cash_flow(previous_from, previous_to)
        previous_label = f"{fmt_date(previous_from)} to {fmt_date(previous_to)}"
    class_rows = sorted(classes.values(), key=lambda item: item["value"], reverse=True)
    return render(request, "birdview.html", period=period, month=month, year=year,
                  custom_from=custom_from, custom_to=custom_to, date_from=fmt_date(first), date_to=fmt_date(last),
                  cash=cash, brokerage_cash=brokerage_cash, reserves=reserves, reserve_summary=reserve_summary,
                  investments=investment_assets, portfolio_value=own_investment_value,
                  portfolio_cost=own_investment_cost, portfolio_unrealized=own_investment_value-own_investment_cost,
                  realized_return=realized_return, dividend_return=dividend_return,
                  portfolio_return=own_investment_value-own_investment_cost+realized_return+dividend_return,
                  factor=factor, asset_total=asset_total, net_worth=net_worth, cash_flow=cash_flow,
                  spending=spending, income=income, largest_income=largest_income,
                  monthly_flow=monthly_flow, largest_month=largest_month, chart_start=fmt_date(chart_from),
                  previous=previous, previous_label=previous_label,
                  largest_expense=largest_expense, investment_classes=class_rows,
                  first_activity=c.reporting.first_activity_date(), as_of=day, period_error=period_error)


@router.post("/settings")
async def save_settings(request: Request):
    c = container(request)
    form = await request.form()
    try:
        factor = to_decimal(str(form.get("factor", "")), "factor")
        if factor < ZERO or factor > Decimal(100):
            raise ValidationError("Enter a liquidation factor from 0 to 100.", "factor")
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect("/birdview", exc.message)
    c.settings.set("investment_liquidation_factor", str(factor))
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/birdview", "Investment liquidation factor saved.")


@router.get("/settings")
async def settings_popup(request: Request):
    c = container(request)
    factor = to_decimal(c.settings.get("investment_liquidation_factor") or "95")
    return render(request, "birdview/factor_popup.html", factor=factor)
