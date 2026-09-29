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
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.investments.report import build_investment_report

from ..web import container, render
from ..web import redirect
from ..periods import Period, parse_period
from .birdview import _own_holdings

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
    net_worth = c.reporting.net_worth(as_of)
    account_contributions = _owned_account_type_rows(c, accounts, as_of)
    holdings, unvalued = _own_holdings(c, fmt_date(as_of))
    class_values = {}
    classes_by_id = {item.id: item for item in c.assets.list_classes()}
    for holding in holdings:
        cls = next((item for item in classes_by_id.values() if item.code == holding["class_code"]), None)
        if cls is not None:
            class_values[cls.id] = class_values.get(cls.id, ZERO) + (holding["value"] or ZERO)
    factor_records = c.investments.liquidation_factors()
    for cls in c.assets.investment_classes():
        class_values.setdefault(cls.id, ZERO)
    investment_value = sum(class_values.values(), ZERO)
    estimated_investments = sum((value * factor_records.get(class_id, Decimal(95)) / 100
                                 for class_id, value in class_values.items()), ZERO)
    eligible_cash = c.reporting.owned_liquid_cash(as_of)
    brokerage_cash = c.reporting.owned_brokerage_cash(as_of)
    cash_accounts = [
        {"id": account.id, "label": account.label,
         "value": c.reporting.owned_account_value(account.id, as_of),
         "type": _ACCOUNT_TYPE_LABELS[account.account_type]}
        for account in accounts if account.account_type in {AccountType.CASH, AccountType.BANK}
    ]
    cash_accounts.extend({**row, "type": "Brokerage cash"}
                         for row in c.reporting.owned_brokerage_cash_by_account(as_of))
    reserve_rows = c.reserves.breakdown_at(fmt_date(as_of))
    if reserve_rows is None and as_of == today():
        reserve_rows = [{"id": row["id"], "name": row["name"], "kind": row["kind"],
                         "effective_allocated": row["effective_allocated"]}
                        for row in c.reserves.list_active()]
    assigned = (sum((row["effective_allocated"] for row in reserve_rows), ZERO)
                if reserve_rows is not None else None)
    reserve_summary = (None if assigned is None else {
        "eligible_cash": eligible_cash, "allocated": assigned, "free_cash": eligible_cash - assigned,
        "shortfall": max(assigned - eligible_cash, ZERO),
    })
    free_cash = reserve_summary["free_cash"] if reserve_summary is not None else None
    estimated_available = (free_cash + estimated_investments
                           if free_cash is not None and not net_worth.unvalued else None)
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
                              "href": "/reserves", "priority": 2})
    current_budget = c.budgets.month_view(month_of(today()))
    for section in current_budget.sections:
        if section.planned_actual > section.available:
            attention.append({"label": f"Budget exceeded: {section.name}",
                              "detail": f"{fmt(section.planned_actual - section.available)} {c.base_currency} over plan this month.",
                              "href": "/budget", "priority": 2})
    attention = sorted(attention, key=lambda item: item["priority"])
    change, change_reason = None, "No recorded position is available for comparison."
    change_label = "Change during this period"
    if not net_worth.unvalued:
        if period.key == "all":
            initial = c.reporting.net_worth(first - timedelta(days=1)) if first_activity else None
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
    closing_report = build_investment_report(c.db, c.accounts, c.assets, c.reporting,
                                              fmt_date(first), fmt_date(as_of))
    opening_report = build_investment_report(c.db, c.accounts, c.assets, c.reporting,
                                              fmt_date(first), fmt_date(first - timedelta(days=1)))
    unrealized_change = (closing_report["unrealized"] - opening_report["unrealized"]
                         if closing_report["unrealized"] is not None and opening_report["unrealized"] is not None
                         else None)
    period_result = (closing_report["realized"] + closing_report["dividends"] + unrealized_change
                     if unrealized_change is not None else None)
    holdings_value = closing_report["value"]
    investment_cash = closing_report["investment_cash"]
    portfolio_value = (holdings_value + investment_cash
                       if holdings_value is not None and investment_cash is not None else None)
    investment_report = {
        "holdings_value": holdings_value, "investment_cash": investment_cash,
        "portfolio_value": portfolio_value, "new_money": closing_report["new_money"],
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
    current_day, opening_day = fmt_date(as_of), fmt_date(first - timedelta(days=1))
    current_portfolio = c.investments.portfolio(current_day)
    opening_portfolio = c.investments.portfolio(opening_day)
    current_by_key = {(h.account_id, h.asset_id): h for h in current_portfolio.positions}
    opening_by_key = {(h.account_id, h.asset_id): h for h in opening_portfolio.positions}

    def owned_values(portfolio, on_day):
        custody_units = defaultdict(lambda: ZERO)
        for row in c.money_from_others.investment_positions(on_day):
            custody_units[(row["account_id"], row["asset_id"])] += row["units"]
        values = {}
        for holding in portfolio.open:
            key = (holding.account_id, holding.asset_id)
            others = custody_units.get(key, ZERO)
            other_value = (c.reporting.value_of(holding.asset_id, others, on_day).value or ZERO) if others else ZERO
            share = ((holding.value or ZERO) - other_value) / holding.value if holding.value else ZERO
            values[key] = (share, (holding.value or ZERO) - other_value,
                           holding.cost_basis * (holding.quantity - others) / holding.quantity
                           if holding.quantity else ZERO)
        return values

    current_owned = owned_values(current_portfolio, current_day)
    opening_owned = owned_values(opening_portfolio, opening_day)
    class_results = defaultdict(lambda: ZERO)
    asset_results = defaultdict(lambda: {"label": "", "result": ZERO})
    for key, holding in current_by_key.items():
        if not holding.is_open or holding.value is None:
            continue
        share, owned_value, owned_cost = current_owned.get(key, (ZERO, ZERO, ZERO))
        previous = opening_by_key.get(key)
        old_share, old_value, old_cost = opening_owned.get(key, (ZERO, ZERO, ZERO))
        if previous and previous.value is not None:
            unrealized_change = (owned_value - owned_cost) - (old_value - old_cost)
            realized_change = (holding.realized - previous.realized) * share
            distribution_change = (holding.dividends - previous.dividends) * share
        else:
            unrealized_change = owned_value - owned_cost
            realized_change = holding.realized * share
            distribution_change = holding.dividends * share
        result = unrealized_change + realized_change + distribution_change
        class_results[holding.asset_class.split(" › ")[-1]] += result
        asset_result = asset_results[holding.asset_id]
        asset_result["label"] = holding.asset_name
        asset_result["result"] += result
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
    savings_rate = (cash_flow.net / cash_flow.inflows * 100
                    if cash_flow.inflows > ZERO else None)
    return render(
        request,
        "dashboard/index.html",
        month=month, this_month=month_of(today()), period=period, period_error=period_error,
        date_from=fmt_date(first), date_to=fmt_date(as_of), as_of=fmt_date(as_of),
        range_label=(f"No recorded activity · Position as of {fmt_date(as_of)}"
                     if period.key == "all" and not first_activity else f"{fmt_date(first)} to {fmt_date(as_of)} · Position as of {fmt_date(as_of)}"),
        eligible_cash=eligible_cash, brokerage_cash=brokerage_cash, reserve_summary=reserve_summary,
        cash_accounts=cash_accounts, reserve_rows=reserve_rows,
        free_cash=free_cash, investment_value=investment_value,
        estimated_investments=estimated_investments, estimated_available=estimated_available,
        unvalued=unvalued,
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
    if kind == "owned":
        position = c.reporting.net_worth(day)
        title = "Known owned value" if position.unvalued else "What you own"
        explanation = "Owned value is the value in your accounts after money and investments owned by others are excluded."
        rows = _owned_account_type_rows(c, c.accounts.list(), day)
        total = position.total
        missing = f" Missing valuation: {'; '.join(position.unvalued)}." if position.unvalued else ""
        if period.key == "all":
            initial = c.reporting.net_worth(parse_date(first) - timedelta(days=1)) if c.reporting.first_activity_date() else None
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
        title = "Free cash"
        eligible = c.reporting.owned_liquid_cash(day)
        allocated = c.reserves.allocation_at(day)
        explanation = "Free cash = owned liquid cash (wallet, bank, and brokerage cash) − assigned reserves. Brokerage cash is included in the total, but move it to a bank or wallet before everyday spending."
        rows = _owned_account_type_rows(
            c, c.accounts.list(), day, {AccountType.CASH, AccountType.BANK})
        rows.append({"label": "Brokerage cash · transfer before everyday spending",
                     "value": c.reporting.owned_brokerage_cash(day)})
        if allocated is None:
            total, foot = None, "Historical free cash unavailable: reserve assignments cannot be reconstructed for this date."
        else:
            rows.append({"label": "Assigned to reserves", "value": -allocated, "href": "/reserves"})
            total, foot = eligible - allocated, f"Owned liquid cash {eligible} less reserve assignments {allocated}. Period end: {day}."
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
