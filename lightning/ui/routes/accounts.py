from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.accounts.domain import DEFAULT_CASH_CLASS, OFFERED_TYPES, TYPE_LABELS
from lightning.core.dates import today
from lightning.core.errors import LightningError

from . import register
from ..web import container, redirect, render

router = APIRouter(prefix="/accounts")

FIELDS = ("name", "account_type", "last4", "notes", "opening_balance", "opening_balance_date")


def _form_context(request: Request, values: dict, account=None, error: LightningError | None = None):
    c = container(request)
    return dict(
        values=values,
        account=account,
        types=sorted(((t.value, TYPE_LABELS[t]) for t in OFFERED_TYPES), key=lambda row: row[1].casefold()),
        # where each type shows up in "What your wealth is made of", in plain words
        groups={t.value: c.assets.display_name(c.assets.get_class_by_code(DEFAULT_CASH_CLASS[t]).id)
                for t in OFFERED_TYPES},
        error=error.message if error else "",
        error_field=(error.field or "") if error else "",
    )


@router.get("")
async def list_accounts(request: Request):
    c = container(request)
    rows = []
    for account in c.accounts.list():
        rows.append((account, c.reporting.account_value(account.id, today()),
                     c.reporting.owned_account_value(account.id, today()),
                     c.transactions.count_for_account(account.id)))
    net_worth = c.reporting.net_worth(today())
    gross_total = sum((row[1] for row in rows if row[0].active), start=0)
    return render(request, "accounts/list.html", rows=rows, net_worth=net_worth, gross_total=gross_total)


@router.get("/new")
async def new_account(request: Request):
    values = {"account_type": request.query_params.get("type", "BANK"), "opening_balance": "",
              "opening_balance_date": today().isoformat()}
    return render(request, "accounts/form.html", **_form_context(request, values))


@router.post("/new")
async def create_account(request: Request):
    c = container(request)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in FIELDS}
    try:
        # The internal start date is intentionally not shown: users can enter their first
        # transaction on its real date, including history predating account setup.
        account = c.account_flows.open_account(
            name=values["name"], account_type=values["account_type"],
            opening_date="1900-01-01", opening_balance=values["opening_balance"],
            opening_balance_date=values["opening_balance_date"],
            last4=values["last4"], notes=values["notes"],
        )
    except LightningError as exc:
        return render(request, "accounts/form.html", status_code=400, **_form_context(request, values, error=exc))
    return redirect(f"/accounts/{account.id}", f"Account {account.label} is ready.")


@router.get("/{account_id:int}")
async def account_register(request: Request, account_id: int):
    return register.page(request, account_id)


@router.get("/{account_id:int}/reconcile")
async def reconcile_account(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
    through = str(request.query_params.get("date", today().isoformat()))
    raw_balance = str(request.query_params.get("balance", ""))
    error = ""
    try:
        through = c.reconciliation.validate_date(through)
        statement_balance = c.reconciliation.parse_statement_balance(raw_balance) if raw_balance.strip() else None
    except LightningError as exc:
        statement_balance, error = None, exc.message
    return render(request, "accounts/reconcile.html", account=account, through=through,
                  balance_input=raw_balance, lines=c.reconciliation.lines(account_id, through),
                  summary=c.reconciliation.summary(account_id, through, statement_balance), error=error)


@router.post("/{account_id:int}/reconcile")
async def update_reconciliation(request: Request, account_id: int):
    c = container(request)
    form = await request.form()
    try:
        through = c.reconciliation.validate_date(str(form.get("date", "")))
        raw_balance = str(form.get("balance", ""))
        action = str(form.get("action", ""))
        line_id = int(str(form.get("line_id", "")))
        if action not in {"clear", "unclear"}:
            raise LightningError("Choose whether to clear or mark uncleared this transaction.")
        c.reconciliation.set_cleared(account_id, line_id, action == "clear")
    except (ValueError, LightningError) as exc:
        msg = exc.message if isinstance(exc, LightningError) else "Choose a transaction to update."
        return redirect(f"/accounts/{account_id}/reconcile", msg)
    from urllib.parse import urlencode
    return redirect(f"/accounts/{account_id}/reconcile?{urlencode({'date': through, 'balance': raw_balance})}")


@router.post("/{account_id:int}/investment-entry")
async def investment_entry(request: Request, account_id: int):
    """Add a stock/fund trade or dividend inline from this account's register."""
    result = await register.create_investment_entry(request, account_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    c = container(request)
    c.reserves.auto_link_transaction(txn.id)
    feedback = register._budget_feedback(container(request), txn)
    return redirect(f"/accounts/{account_id}?date={txn.date}", f"Saved {txn.ref}. {feedback}".strip())


@router.post("/{account_id:int}/register")
async def register_entry(request: Request, account_id: int):
    """Save one row typed into the register, then come back ready for the next one."""
    result = await register.create(request, account_id)
    if not isinstance(result, tuple):
        return result  # the page again, with the error
    txn, _ = result
    feedback = register._budget_feedback(container(request), txn)
    return redirect(f"/accounts/{account_id}?date={txn.date}", f"Saved {txn.ref}. {feedback}".strip())


@router.post("/{account_id:int}/register/{txn_id:int}")
async def register_update(request: Request, account_id: int, txn_id: int):
    result = await register.update(request, account_id, txn_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    c = container(request)
    c.reserves.auto_link_transaction(txn.id)
    message = f"Saved as {txn.ref}. The original transaction is kept in history." if txn.id != txn_id else f"Saved {txn.ref}."
    message = f"{message} {register._budget_feedback(container(request), txn)}".strip()
    return redirect(f"/accounts/{account_id}", message)


@router.get("/{account_id:int}/edit")
async def edit_account(request: Request, account_id: int):
    c = container(request)
    a = c.accounts.get(account_id)
    opening_id = c.transactions.opening_txn_id(account_id)
    opening_txn = c.transactions.get(opening_id) if opening_id else None
    first_activity = c.transactions.earliest_activity(account_id)
    values = {
        "name": a.name, "account_type": a.account_type.value,
        "opening_date": a.opening_date, "opening_balance": str(c.account_flows.opening_of(a)),
        "opening_balance_date": opening_txn.date if opening_txn else (first_activity or today().isoformat()),
        "last4": a.last4 or "",
        "notes": a.notes,
    }
    return render(request, "accounts/form.html", **_form_context(request, values, account=a))


@router.post("/{account_id:int}/edit")
async def update_account(request: Request, account_id: int):
    c = container(request)
    account = c.accounts.get(account_id)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in FIELDS}
    try:
        account = c.account_flows.update_account(
            account_id, name=values["name"], account_type=values["account_type"],
            opening_date=account.opening_date, opening_balance=str(c.account_flows.opening_of(account)),
            institution=account.institution, last4=values["last4"], notes=values["notes"],
            opening_balance_date=values["opening_balance_date"],
        )
    except LightningError as exc:
        return render(request, "accounts/form.html", status_code=400,
                      **_form_context(request, values, account=account, error=exc))
    return redirect(f"/accounts/{account.id}", "Account saved.")


@router.post("/{account_id:int}/deactivate")
async def deactivate(request: Request, account_id: int):
    c = container(request)
    try:
        account = c.account_flows.deactivate(account_id)
    except LightningError as exc:
        return redirect(f"/accounts/{account_id}", exc.message)
    return redirect(f"/accounts/{account.id}", f"{account.label} is now inactive.")


@router.post("/{account_id:int}/reactivate")
async def reactivate(request: Request, account_id: int):
    account = container(request).account_flows.reactivate(account_id)
    return redirect(f"/accounts/{account.id}", f"{account.label} is active again.")
