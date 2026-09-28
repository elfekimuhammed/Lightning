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

router = APIRouter(prefix="/birdview")


def _own_holdings(c, day):
    rows, unvalued = c.reporting.holdings(day)
    custody = {(r["account_id"], r["asset_id"]): r["units"] for r in c.money_from_others.investment_positions(day)}
    result = []
    for row in rows:
        asset = c.assets.get_asset(row.asset_id)
        if asset.is_cash and row.asset_class_code.split(".")[0] == "CASH":
            continue
        held = custody.get((row.account.id, row.asset_id), ZERO)
        if asset.is_cash:
            held = c.money_from_others.cash_total_for_account(row.account.id, day)
        quantity = max(ZERO, row.quantity - held)
        valuation = c.reporting.value_of(row.asset_id, quantity, day) if held else None
        value = valuation.value if held and valuation else row.value
        if held and row.value is not None and value is not None:
            value = max(ZERO, row.value - value)
        elif held and asset.is_cash:
            held_value = c.reporting.value_of(row.asset_id, min(held, row.quantity), day).value
            value = max(ZERO, (row.value or ZERO) - (held_value or ZERO))
        elif held:
            value = None
        result.append({"account_id": row.account.id, "account": row.account.label, "asset_id": row.asset_id,
                       "asset": asset.name, "class_code": row.asset_class_code, "quantity": quantity,
                       "value": value, "unit": asset.unit})
    return result, unvalued


def _period(c, query):
    if str(query.get("period", "month")) == "custom" and (not query.get("date_from") or not query.get("date_to")):
        period = parse_period({"period": "month", "month": query.get("month", month_of(today()))}, today(), c.reporting.first_activity_date())
        return Period("custom", "Custom", period.start, period.end)
    return parse_period(query, today(), c.reporting.first_activity_date())


@router.get("")
async def birdview(request: Request):
    c = container(request)
    try:
        selected = _period(c, request.query_params)
        period_error = ""
    except LightningError as exc:
        fallback = _period(c, {"period": "month", "month": month_of(today())})
        selected = Period("custom", "Custom", fallback.start, fallback.end) if request.query_params.get("period") == "custom" else fallback
        period_error = exc.message
    first, last = selected.start, selected.end
    day = fmt_date(last)
    wealth = c.reporting.net_worth(day)
    holdings, unvalued = _own_holdings(c, day)
    classes_by_code = {a.code: a for a in c.assets.list_classes()}
    class_rows = {}
    for item in holdings:
        cls = classes_by_code.get(item["class_code"])
        if cls is None:
            continue
        row = class_rows.setdefault(cls.id, {"id": cls.id, "code": cls.code, "name": cls.name, "value": ZERO, "items": []})
        row["value"] += item["value"] or ZERO
        row["items"].append(item)
    factor_records = c.investments.liquidation_factors()
    for cls in c.assets.investment_classes():
        if cls.id not in class_rows:
            class_rows[cls.id] = {"id": cls.id, "code": cls.code, "name": cls.name, "value": ZERO, "items": []}
    for cls in c.assets.list_classes():
        if cls.id not in class_rows and cls.code.split(".")[0] not in {"CASH", "CUSTODY"} and cls.active:
            if any(asset.asset_class_id == cls.id and not asset.is_cash and asset.active for asset in c.assets.list_assets()):
                class_rows[cls.id] = {"id": cls.id, "code": cls.code, "name": cls.name, "value": ZERO, "items": []}
    classes = sorted(class_rows.values(), key=lambda x: (-x["value"], x["name"].casefold()))
    for row in classes:
        row["factor"] = factor_records.get(row["id"], Decimal(95))
        row["estimated"] = row["value"] * row["factor"] / 100
    investment_value = sum((r["value"] for r in classes), ZERO)
    estimated_investments = sum((r["estimated"] for r in classes), ZERO)

    brokerage_cash = c.reporting.owned_brokerage_cash(day)
    owned_cash = c.reporting.owned_liquid_cash(day)
    other_owned = wealth.total - owned_cash - investment_value
    wallet_bank = owned_cash - brokerage_cash
    allocation = c.reserves.allocation_at(day)
    reserves_known = allocation is not None
    if last == today() and not reserves_known:
        allocation = c.reserves.cash_summary(owned_cash)["allocated"]
        reserves_known = True
    allocation = allocation or ZERO
    free_cash = owned_cash - allocation if reserves_known else None
    estimated_available = free_cash + estimated_investments if free_cash is not None and not wealth.unvalued else None
    unavailable_reason = ("A required valuation is missing for this date." if wealth.unvalued else
                          "Reserve history is incomplete for this date." if not reserves_known else "")

    cash_flow = c.reporting.cash_flow(first, last)
    spending = c.reporting.spending_by_category(first, last, depth=1)
    income = c.reporting.money_in_by_category(first, last)
    for group in spending:
        group.category_id = c.categories.get_by_code(group.code).id
    for group in income:
        group.category_id = c.categories.get_by_code(group.code).id
    category_filter = str(request.query_params.get("category_id", ""))
    category_name = ""
    if category_filter.isdigit():
        selected_category = c.categories.get(int(category_filter))
        category_name = selected_category.name
        spending = [group for group in spending if selected_category.code.startswith(group.code)]
    monthly_flow = c.reporting.monthly_flow_between(first.replace(day=1), last)
    flow_max = max(cash_flow.inflows, cash_flow.outflows, Decimal("1"))
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
    targets = c.investments.class_targets()
    total_targets = sum(targets.values(), ZERO)
    for row in classes:
        target = targets.get(row["id"])
        row["current_weight"] = row["value"] / investment_value * 100 if investment_value else ZERO
        row["target"] = target
        row["gap"] = target - row["current_weight"] if target is not None else None
        row["target_value"] = investment_value * target / 100 if target is not None else None
        row["to_target"] = row["target_value"] - row["value"] if target is not None else None
    return render(request, "birdview.html", period=selected.key, month=last.strftime("%Y-%m"),
                  custom_from=request.query_params.get("date_from", ""), custom_to=request.query_params.get("date_to", ""),
                  date_from=fmt_date(first), date_to=fmt_date(last), range_start_display=selected.start_display,
                  range_end_display=selected.end_display, as_of=day, net_worth=wealth, cash=wallet_bank,
                  brokerage_cash=brokerage_cash, owned_cash=owned_cash, reserves=allocation, reserves_known=reserves_known,
                  free_cash=free_cash, investment_value=investment_value, other_owned=other_owned,
                  estimated_investments=estimated_investments,
                  unavailable_reason=unavailable_reason,
                  asset_total=estimated_available, classes=classes, spending=spending, income=income,
                  cash_flow=cash_flow, monthly_flow=monthly_flow, prior=prior, period_error=period_error,
                  flow_max=flow_max,
                  unvalued=list(dict.fromkeys(wealth.unvalued + unvalued)), targets_set=bool(targets),
                  targets_complete=total_targets == Decimal(100), first_activity=c.reporting.first_activity_date(),
                  category_filter=category_filter, category_name=category_name,
                  base=c.reporting.base_currency)


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
    return render(request, "birdview/expenses.html", period=selected.key, month=last.strftime("%Y-%m"),
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
