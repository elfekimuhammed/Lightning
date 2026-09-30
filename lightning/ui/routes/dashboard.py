from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import timedelta
from collections import defaultdict
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Request

from lightning.accounts.domain import AccountType
from lightning.core.dates import fmt_date, month_of, parse_date, parse_month, today
from lightning.core.errors import ValidationError
from lightning.core.figures import FIGURES, label
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.investments.report import investment_period, results_by_asset

from ..web import container, render
from ..web import redirect
from ..periods import Period, parse_period

router = APIRouter()

_ACCOUNT_TYPE_LABELS = {
    AccountType.CASH: "Cash",
    AccountType.BANK: "Bank",
    AccountType.DEPOSIT: "Deposits",
    AccountType.BROKERAGE: "Brokerage",
    AccountType.PHYSICAL_ASSET: "Physical assets",
    AccountType.OTHER_ASSET: "Other assets",
}


def _owned_account_type_rows(c, accounts, as_of, include_types=None):
    groups = {}
    for account in accounts:
        if include_types is not None and account.account_type not in include_types:
            continue
        value = c.reporting.owned_account_value(account.id, as_of)
        group = groups.setdefault(account.account_type, {"label": _ACCOUNT_TYPE_LABELS[account.account_type],
                                                         "value": ZERO, "accounts": []})
        group["value"] += value
        group["accounts"].append({"id": account.id, "label": account.label, "value": value})
    return [groups[account_type] for account_type in AccountType if account_type in groups]


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
    # Every position figure comes from one calculation; see lightning/planning/position.py.
    position = c.position.at(as_of)
    net_worth = c.reporting.net_worth(as_of)
    account_contributions = _owned_account_type_rows(c, accounts, as_of)
    cash_accounts = [
        {"id": account.id, "label": account.label,
         "value": c.reporting.owned_account_value(account.id, as_of),
         "type": _ACCOUNT_TYPE_LABELS[account.account_type]}
        for account in accounts if account.account_type in {AccountType.CASH, AccountType.BANK}
    ]
    cash_accounts.extend({**row, "type": "Brokerage cash"}
                         for row in c.reporting.owned_brokerage_cash_by_account(as_of))
    owe = position.owe
    # The Overview lists actions a user can take. Reconciliation diagnostics
    # remain in the dedicated Integrity checks management view.
    attention = [{"label": "Missing valuation", "detail": item, "href": "/investments/prices", "priority": 0}
                 for item in c.reporting.net_worth(today()).unvalued]
    pending_row = c.bank_imports.first_pending_review()
    if pending_row:
        row = pending_row
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
                              "href": "/plan/reserves", "priority": 2})
    # Payments that are due and unpaid today, whatever period is selected.
    for payment in c.planning.what_you_owe(today()).bills_due_items:
        kind = "Loan payment due" if payment.item.kind.value == "LOAN" else "Bill due"
        attention.append({"label": f"{kind}: {payment.item.name}",
                          "detail": f"Due {payment.due_date} · {fmt(payment.amount)} {c.base_currency} · not paid yet.",
                          "href": f"/plan/items/{payment.item.id}/pay?due={payment.due_date}&back=%2F",
                          "popup": True, "action": "Mark paid", "priority": 1})
    lowest = c.forecaster.forecast(today()).lowest
    if lowest is not None and lowest.closing < ZERO:
        attention.append({"label": "Cash may run short",
                          "detail": f"The cash forecast ends {lowest.month} at {fmt(lowest.closing)} {c.base_currency}.",
                          "href": "/plan", "priority": 1})
    current_budget = c.budgets.month_view(month_of(today()))
    for section in current_budget.sections:
        if section.planned_actual > section.available:
            attention.append({"label": f"Budget exceeded: {section.name}",
                              "detail": f"{fmt(section.planned_actual - section.available)} {c.base_currency} over plan this month.",
                              "href": "/budget", "priority": 2})
    attention = sorted(attention, key=lambda item: item["priority"])
    change, change_reason = c.position.change_in_what_you_own(first, as_of, since_first_record=period.key == "all")
    change_label = (f"{label('change_in_what_you_own')} since your first record" if period.key == "all"
                    else label("change_in_what_you_own"))
    cash_flow = c.reporting.cash_flow(first, as_of)
    spending_groups = c.reporting.spending_by_category(first, as_of, depth=2)
    categorized_spending = sum((max(group.value, ZERO) for group in spending_groups), ZERO)
    expense_groups = []
    expense_group_index = {}
    for group in spending_groups:
        category = c.categories.get_by_code(group.code)
        parent = c.categories.get(category.parent_id) if category.parent_id else category
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first),
                           "date_to": fmt_date(as_of)})
        child = {"label": category.name, "value": group.value,
                 "share": max(group.value, ZERO) / categorized_spending * 100
                 if categorized_spending else ZERO,
                 "category_id": category.id, "href": f"/transactions?{query}"}
        if parent.id not in expense_group_index:
            expense_group_index[parent.id] = {"id": parent.id, "label": parent.name,
                                              "children": [], "total": ZERO}
            expense_groups.append(expense_group_index[parent.id])
        expense_group_index[parent.id]["children"].append(child)
        expense_group_index[parent.id]["total"] += group.value
    # Give every L1 group its two largest L2 categories first, then fill the
    # remaining places with the next-largest categories overall, capped at 8.
    selected_ids = set()
    for parent in expense_groups:
        for child in parent["children"][:2]:
            if len(selected_ids) < 8:
                selected_ids.add(child["category_id"])
    remaining_children = sorted(
        (child for parent in expense_groups for child in parent["children"]
         if child["category_id"] not in selected_ids),
        key=lambda child: child["value"], reverse=True)
    for child in remaining_children:
        if len(selected_ids) >= 8:
            break
        selected_ids.add(child["category_id"])
    selected_groups = []
    for parent in expense_groups:
        children = [child for child in parent["children"] if child["category_id"] in selected_ids]
        if children:
            other_children = [child for child in parent["children"] if child["category_id"] not in selected_ids]
            selected_groups.append({
                "id": parent["id"], "label": parent["label"], "children": children,
                "total": parent["total"], "other_count": len(other_children),
                "other_total": sum((child["value"] for child in other_children), ZERO),
            })
    expense_groups = selected_groups
    closing_report = investment_period(c.db, c.accounts, c.assets, c.reporting, fmt_date(first), fmt_date(as_of))
    opening_report = closing_report["opening"]
    period_result = closing_report["result"]
    holdings_value = closing_report["value"]
    investment_cash = closing_report["investment_cash"]
    portfolio_value = (holdings_value + investment_cash
                       if holdings_value is not None and investment_cash is not None else None)
    investment_report = {
        "holdings_value": holdings_value, "brokerage_cash": investment_cash,
        "portfolio_value": portfolio_value, "new_money": closing_report["net_money"],
        "period_result": period_result, "period_result_available": period_result is not None,
        "missing": closing_report["missing"] + opening_report["missing"],
        "holdings_count": sum(1 for row in closing_report["holdings"] if row["price_source"] != "CASH"),
    }
    investment_holdings = [
        {"label": f"{row['asset']} · {row['account']}", "value": row["value"],
         "weight": (row["value"] / portfolio_value * 100
                    if row["value"] is not None and portfolio_value else None)}
        for row in sorted((row for row in closing_report["holdings"] if row["price_source"] != "CASH"),
                          key=lambda row: (row["value"] is None, -(row["value"] or ZERO), row["asset"]))[:5]
    ]
    # Reuse the investment ledger's dated positions for asset-class and asset
    # performance. Returns combine each holding's unrealized movement,
    # realized gain/loss and distributions across the selected range.
    class_results, asset_results = results_by_asset(c.investments, c.money_from_others, c.reporting,
                                                    fmt_date(first - timedelta(days=1)), fmt_date(as_of))
    class_rows = [{"label": name, "result": value} for name, value in
                  sorted(class_results.items(), key=lambda item: (-abs(item[1]), item[0].casefold()))]
    asset_result_rows = list(asset_results.values())
    winners = sorted((row for row in asset_result_rows if row["result"] > ZERO),
                     key=lambda row: row["result"], reverse=True)[:2]
    losers = sorted((row for row in asset_result_rows if row["result"] < ZERO),
                    key=lambda row: row["result"])[:2]
    class_scale = max((abs(row["result"]) for row in class_rows), default=ZERO) or Decimal(1)
    investment_flow = closing_report["new_money"]
    investment_share = (investment_flow / cash_flow.inflows * 100
                        if cash_flow.inflows > ZERO else None)
    savings_rate = cash_flow.savings_rate
    return render(
        request,
        "dashboard/index.html",
        month=month, this_month=month_of(today()), period=period, period_error=period_error,
        date_from=fmt_date(first), date_to=fmt_date(as_of), as_of=fmt_date(as_of),
        range_label=(f"No recorded activity · Position as of {fmt_date(as_of)}"
                     if period.key == "all" and not first_activity else f"{fmt_date(first)} to {fmt_date(as_of)} · Position as of {fmt_date(as_of)}"),
        pos=position, cash_accounts=cash_accounts, owe=owe,
        change=change, change_reason=change_reason, change_label=change_label,
        attention=attention,
        net_worth=net_worth,
        account_contributions=account_contributions, expense_groups=expense_groups,
        categorized_spending=categorized_spending,
        investment_report=investment_report, investment_holdings=investment_holdings,
        investment_class_returns=class_rows, investment_class_scale=class_scale,
        investment_winners=winners, investment_losers=losers,
        cash_flow=cash_flow, investment_flow=investment_flow,
        investment_share=investment_share, savings_rate=savings_rate,
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
    position = c.position.at(day)
    if kind == "owned":
        title = f"{label('what_you_own')} · known subtotal" if position.unvalued else label("what_you_own")
        figure = "what_you_own"
        explanation = FIGURES["what_you_own"].meaning + " Money and units held for others are left out."
        rows = [{"label": label("cash_you_own"), "value": position.cash_you_own},
                {"label": label("deposits"), "value": position.deposits},
                {"label": label("holdings_value"), "value": position.holdings_value}]
        if position.other_you_own:
            rows.append({"label": label("other_you_own"), "value": position.other_you_own})
        total = position.what_you_own
        missing = f" Missing valuation: {'; '.join(position.unvalued)}." if position.unvalued else ""
        change_value, change_reason = c.position.change_in_what_you_own(first, day, since_first_record=period.key == "all")
        change_label = (f"{label('change_in_what_you_own')} since your first record" if period.key == "all"
                        else label("change_in_what_you_own"))
        foot = (f"Position as of {day}. {change_label}: "
                + (fmt(change_value, 2, True) if change_value is not None else f"unavailable · {change_reason}")
                + f". This is wealth movement, not investment return.{missing}")
        action = ("Open Birdview", destination)
    elif kind == "free-cash":
        title = label("free_cash")
        figure = "free_cash"
        explanation = (FIGURES["free_cash"].meaning + " " + FIGURES["bills_due"].meaning
                       + " Brokerage cash counts, but move it to a bank or wallet before everyday spending.")
        rows = [{"label": label("bank_and_wallet_cash"), "value": position.bank_and_wallet_cash},
                {"label": label("brokerage_cash"), "value": position.brokerage_cash}]
        if position.reserves is None:
            total, foot = None, "Free cash is unavailable: reserve history cannot be rebuilt for this date."
        else:
            rows.append({"label": label("reserves"), "value": -position.reserves, "href": "/plan/reserves"})
            if position.bills_due:
                rows.append({"label": label("bills_due"), "value": -position.bills_due, "href": "/plan"})
            total, foot = position.free_cash, f"Position as of {day}."
        action = ("Open Cash planning", "/plan")
    elif kind == "flow":
        title = label("net_flow")
        figure = "net_flow"
        flow = c.reporting.cash_flow(first, day)
        explanation = FIGURES["money_in"].meaning + " " + FIGURES["money_out"].meaning
        rows = [{"label": label("money_in"), "value": flow.inflows}, {"label": label("money_out"), "value": -flow.outflows}]
        total = flow.net
        foot = f"{first} to {day}. This is cash flow, not wealth change or investment return."
        action = ("Open Birdview", destination)
    else:
        return render(request, "not_found.html", status_code=404, message="Explanation not found.")
    return render(request, "dashboard/explanation.html", title=title, explanation=explanation, figure=figure,
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
