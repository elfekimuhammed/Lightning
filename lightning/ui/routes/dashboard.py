from __future__ import annotations

from decimal import InvalidOperation
from datetime import timedelta
import json

from fastapi import APIRouter, Request

from lightning.core.dates import fmt_date, month_of, parse_date, parse_month, today
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, fmt, to_decimal

from ..web import container, render
from ..web import redirect
from ..periods import Period, parse_period

router = APIRouter()


def _owned_wealth_rows(c, net_worth, as_of):
    """Allocate held-for-others balances to their classes for reconciled breakdowns."""
    values = {group.code: group.value for group in net_worth.by_class if group.code != "CUSTODY"}
    labels = {group.code: group.label for group in net_worth.by_class if group.code != "CUSTODY"}

    def root_code(class_id):
        return c.assets.get_class(class_id).code.split(".", 1)[0]

    for account in c.accounts.list(active_only=True):
        held = c.money_from_others.cash_total_for_account(account.id, as_of)
        if held:
            valuation = c.reporting.value_of(c.assets.cash_asset(account.currency).id, held, as_of)
            code = root_code(account.cash_class_id)
            if valuation.value is not None and code in values:
                values[code] -= valuation.value
    for position in c.money_from_others.investment_positions(as_of):
        asset = c.assets.get_asset(position["asset_id"])
        valuation = c.reporting.value_of(asset.id, position["units"], as_of)
        code = root_code(asset.asset_class_id)
        if valuation.value is not None and code in values:
            values[code] -= valuation.value
    brokerage_cash = c.reporting.owned_brokerage_cash(as_of)
    if brokerage_cash:
        if "CASH" in values:
            values["CASH"] -= brokerage_cash
        values["BROKERAGE_CASH"] = brokerage_cash
        labels["BROKERAGE_CASH"] = "Brokerage cash"
    return [{"code": code, "label": labels[code], "value": value,
             "percentage": value / net_worth.total * 100 if net_worth.total else ZERO}
            for code, value in values.items()]


@router.get("/")
async def dashboard(request: Request):
    c = container(request)
    month = str(request.query_params.get("month", month_of(today())))
    first_activity = c.reporting.first_activity_date()
    try:
        period = parse_period(request.query_params, today(), first_activity)
        period_error = ""
    except ValidationError as exc:
        fallback = parse_period({"period": "month", "month": month_of(today())}, today(), first_activity)
        selected = str(request.query_params.get("period", "month"))
        period = Period(selected, "Custom" if selected == "custom" else fallback.label,
                        fallback.start, fallback.end) if selected in {"all", "ytd", "month", "custom"} else fallback
        period_error = exc.message
    first, as_of = period.start, period.end
    accounts = c.accounts.list()
    if not accounts:
        return render(request, "dashboard/welcome.html")
    net_worth = c.reporting.net_worth(as_of)
    eligible_cash = c.reporting.owned_liquid_cash(as_of)
    brokerage_cash = c.reporting.owned_brokerage_cash(as_of)
    assigned = c.reserves.allocation_at(fmt_date(as_of))
    reserve_summary = (None if assigned is None else {
        "eligible_cash": eligible_cash, "allocated": assigned, "free_cash": eligible_cash - assigned,
        "shortfall": max(assigned - eligible_cash, ZERO),
    })
    now_checks = c.integrity.checks(today())
    attention = [{"label": check.name, "detail": check.detail, "href": f"/checks?date={fmt_date(today())}", "priority": 0}
                 for check in now_checks if check.status != "PASS"]
    attention.extend({"label": "Missing valuation", "detail": item, "href": "/investments/prices", "priority": 0}
                     for item in c.reporting.net_worth(today()).unvalued)
    pending_rows = c.bank_imports.db.all("SELECT r.id,r.batch_id,r.row_number,r.raw_json,b.account_id,b.file_name,b.created_at FROM bank_import_rows r JOIN bank_import_batches b ON b.id=r.batch_id WHERE r.status='REVIEW' ORDER BY r.id LIMIT 1")
    if pending_rows:
        row = pending_rows[0]
        try:
            source = json.loads(row["raw_json"])
        except (TypeError, ValueError):
            source = {}
        if not isinstance(source, dict):
            source = {}
        date_value = next((str(value) for key, value in source.items() if "date" in key.casefold() and value),
                          str(row["created_at"])[:10])
        attention.append({"label": "Imported activity needs a decision",
                          "detail": f"{row['file_name']} · row {row['row_number']} · {date_value}.",
                          "href": f"/accounts/{row['account_id']}/import/{row['batch_id']}#import-row-{row['id']}", "priority": 1})
    for reserve in c.reserves.list_active():
        if reserve.get("due_date") and reserve["due_date"] < fmt_date(today()) and reserve["effective_allocated"] > ZERO:
            attention.append({"label": f"Overdue reserve: {reserve['name']}",
                              "detail": f"Due {reserve['due_date']} · {fmt(reserve['effective_allocated'])} {c.base_currency} remains assigned.",
                              "href": "/reserves", "priority": 2})
    current_budget = c.budgets.month_view(month_of(today()))
    for section in current_budget.sections:
        if section.available > ZERO and section.actual > section.available:
            attention.append({"label": f"Budget exceeded: {section.name}",
                              "detail": f"{fmt(section.actual - section.available)} {c.base_currency} over plan this month.",
                              "href": "/budget", "priority": 2})
    attention = sorted(attention, key=lambda item: item["priority"])[:3]
    change, change_reason = None, "No recorded position is available for comparison."
    change_label = "Change during this period"
    if not net_worth.unvalued:
        if period.key == "all":
            initial = c.reporting.net_worth(first) if first_activity else None
            change = net_worth.total - initial.total if initial is not None and not initial.unvalued else None
            if initial is not None and initial.unvalued:
                change_reason = "The first recorded position is missing a required valuation."
            change_label = "Change since first recorded position"
        else:
            before = c.reporting.net_worth(first - timedelta(days=1))
            if not before.unvalued:
                change = net_worth.total - before.total
            else:
                change_reason = "The position immediately before this period is missing a required valuation."
    else:
        change_reason = "A required valuation is missing from the ending position."
    return render(
        request,
        "dashboard/index.html",
        month=month, period=period, period_error=period_error,
        date_from=fmt_date(first), date_to=fmt_date(as_of), as_of=fmt_date(as_of),
        range_label=(f"No recorded activity · Position as of {fmt_date(as_of)}"
                     if period.key == "all" and not first_activity else f"{fmt_date(first)} to {fmt_date(as_of)} · Position as of {fmt_date(as_of)}"),
        eligible_cash=eligible_cash, brokerage_cash=brokerage_cash, reserve_summary=reserve_summary,
        change=change, change_reason=change_reason, change_label=change_label,
        attention=attention,
        net_worth=net_worth,
        cash_flow=c.reporting.cash_flow(first, as_of),
    )


@router.get("/explain/{kind}")
async def explain_overview_figure(request: Request, kind: str):
    c = container(request)
    try:
        period = parse_period(request.query_params, today(), c.reporting.first_activity_date())
    except ValidationError:
        period = parse_period({"period": "month", "month": month_of(today())}, today(), c.reporting.first_activity_date())
    day, first = fmt_date(period.end), fmt_date(period.start)
    destination = "/birdview?" + request.url.query
    if kind == "owned":
        position = c.reporting.net_worth(day)
        title = "Known owned value" if position.unvalued else "What you own"
        explanation = "Owned value is the value in your accounts after money and investments owned by others are excluded."
        rows = [{"label": account.label, "value": c.reporting.owned_account_value(account.id, day),
                 "href": f"/accounts/{account.id}"} for account in c.accounts.list()]
        total = position.total
        missing = f" Missing valuation: {'; '.join(position.unvalued)}." if position.unvalued else ""
        if period.key == "all":
            initial = c.reporting.net_worth(first) if c.reporting.first_activity_date() else None
            change_value = (position.total - initial.total if not position.unvalued and initial and not initial.unvalued else None)
            change_label = "Change since first recorded position"
            change_reason = "The first recorded position is missing a required valuation." if initial and initial.unvalued else "No reliable first recorded position is available."
        else:
            initial = c.reporting.net_worth(period.start - timedelta(days=1))
            change_value = position.total - initial.total if not position.unvalued and not initial.unvalued else None
            change_label = "Change during this period"
            change_reason = "The position immediately before this period is missing a required valuation."
        rows.append({"label": change_label if change_value is not None else f"Change unavailable · {change_reason}",
                     "value": change_value})
        foot = f"Position as of {day}. Change is tracked wealth movement, not investment return. The total excludes custody balances and assets.{missing}"
        action = ("Open Birdview", destination)
    elif kind == "free-cash":
        title = "Cash available to spend"
        eligible = c.reporting.owned_liquid_cash(day)
        allocated = c.reserves.allocation_at(day)
        explanation = "Eligible cash includes owned bank and wallet balances. Brokerage cash is part of owned wealth, but is not immediately spendable until moved to a bank or wallet."
        rows = [{"label": f"{account.label} · eligible cash", "value": c.reporting.owned_account_value(account.id, day), "href": f"/accounts/{account.id}"}
                for account in c.accounts.list() if account.account_type.value in {"CASH", "BANK"}]
        if allocated is None:
            total, foot = None, "Historical free cash unavailable: reserve assignments cannot be reconstructed for this date."
        else:
            rows.append({"label": "Assigned to reserves", "value": -allocated, "href": "/reserves"})
            total, foot = eligible - allocated, f"Eligible cash {eligible} less reserve assignments {allocated}. Period end: {day}."
        action = ("Open Reserves", "/reserves")
    elif kind == "flow":
        title = "Income and spending"
        flow = c.reporting.cash_flow(first, day)
        explanation = "Money in is owned posted income. Money out is owned posted expenses net of refunds; transfers, investment trades, custody activity, and valuation entries are excluded."
        rows = [{"label": "Money in", "value": flow.inflows}, {"label": "Money out", "value": flow.outflows},
                {"label": "Net income less spending", "value": flow.net}]
        total = flow.net
        foot = f"Selected period: {first} to {day}. This is cash flow, not wealth change or investment return."
        action = ("Open Birdview", destination)
    else:
        return render(request, "not_found.html", status_code=404, message="Explanation not found.")
    return render(request, "dashboard/explanation.html", title=title, explanation=explanation,
                  rows=rows, total=total, foot=foot, recent=[], action=action)


@router.get("/money-from-others")
async def money_from_others(request: Request):
    c = container(request)
    return render(request, "money_from_others.html", accounts=c.accounts.list(active_only=True),
                  counterparties=c.counterparties.list_active(),
                  owners=c.reporting.money_from_others_by_owner(today()),
                  investments=c.reporting.money_from_others_investments(today()),
                  entries=c.reporting.money_from_others_history(),
                  investment_entries=c.money_from_others.investment_history())


@router.post("/money-from-others")
async def add_money_from_others(request: Request):
    c = container(request)
    form = await request.form()
    try:
        owner_text = str(form.get("owner", "")).strip()
        party = c.counterparties.resolve(owner_text)
        if not party or not party["active"]:
            raise ValidationError("Choose an active saved Counterparty as Whom.", "owner")
        owner = party["name"]
        account = c.accounts.require_usable(int(form.get("account_id", "0")))
        amount = to_decimal(form.get("amount", ""))
        if amount == 0:
            raise ValidationError("Use a positive amount for money received and a negative amount when it is returned.", "amount")
        day = parse_date(form.get("date", today().isoformat())).isoformat()
        c.money_from_others.record(day, owner, account.id, amount, str(form.get("notes", "")))
    except (ValueError, ValidationError, InvalidOperation) as exc:
        message = exc.message if isinstance(exc, ValidationError) else "Check the amount, date, and account."
        return redirect("/money-from-others", message)
    return redirect("/money-from-others", "Money-from-others entry saved; your net worth has been adjusted.")
