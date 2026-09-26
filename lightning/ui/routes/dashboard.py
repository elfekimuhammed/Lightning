from __future__ import annotations

from decimal import InvalidOperation

from fastapi import APIRouter, Request

from lightning.core.dates import fmt_date, month_of, parse_date, parse_month, today
from lightning.core.errors import ValidationError
from lightning.core.money import to_decimal
from lightning.transactions.domain import TxnFilter

from ..web import container, render
from ..web import redirect

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    c = container(request)
    requested_month = request.query_params.get("month")
    month = requested_month or month_of(today())
    try:
        first, last = parse_month(month)
    except ValidationError:
        return redirect("/", "That month is invalid. Use YYYY-MM, for example 2026-09.")
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
        custody_total=c.reporting.money_from_others_total(as_of),
        custody_by_account=c.reporting.custody_value_by_account(as_of),
        owners=c.reporting.money_from_others_by_owner(as_of),
        # everything on the page is measured to the same day: today in the current month, else month end
        cash_flow=c.reporting.cash_flow(first, as_of),
        bridge=c.reporting.bridge(first, as_of),
        spending=c.reporting.spending_by_category(first, as_of, depth=2)[:8],
        trend=c.reporting.monthly_trend(month, 6),
        recent=recent,
        budget=c.budgets.month_view(month),
    )


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
