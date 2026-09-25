from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.accounts.domain import DEFAULT_CASH_CLASS, OFFERED_TYPES, TYPE_LABELS
from lightning.core.dates import today
from lightning.core.errors import LightningError

from . import register
from ..web import container, redirect, render

router = APIRouter(prefix="/accounts")

FIELDS = ("name", "account_type", "last4", "notes")


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
    values = {"account_type": request.query_params.get("type", "BANK")}
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
            opening_date="1900-01-01", opening_balance="0",
            last4=values["last4"], notes=values["notes"],
        )
    except LightningError as exc:
        return render(request, "accounts/form.html", status_code=400, **_form_context(request, values, error=exc))
    return redirect(f"/accounts/{account.id}", f"Account {account.label} is ready.")


@router.get("/{account_id:int}")
async def account_register(request: Request, account_id: int):
    return register.page(request, account_id)


@router.post("/{account_id:int}/investment-entry")
async def investment_entry(request: Request, account_id: int):
    """Add a stock/fund trade or dividend inline from this account's register."""
    result = await register.create_investment_entry(request, account_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    return redirect(f"/accounts/{account_id}?date={txn.date}", f"Saved {txn.ref}.")


@router.post("/{account_id:int}/register")
async def register_entry(request: Request, account_id: int):
    """Save one row typed into the register, then come back ready for the next one."""
    result = await register.create(request, account_id)
    if not isinstance(result, tuple):
        return result  # the page again, with the error
    txn, _ = result
    return redirect(f"/accounts/{account_id}?date={txn.date}", f"Saved {txn.ref}.")


@router.post("/{account_id:int}/register/{txn_id:int}")
async def register_update(request: Request, account_id: int, txn_id: int):
    result = await register.update(request, account_id, txn_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    return redirect(f"/accounts/{account_id}", f"Saved {txn.ref}.")


@router.get("/{account_id:int}/edit")
async def edit_account(request: Request, account_id: int):
    c = container(request)
    a = c.accounts.get(account_id)
    values = {
        "name": a.name, "account_type": a.account_type.value,
        "opening_date": a.opening_date, "opening_balance": str(c.account_flows.opening_of(a)),
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
