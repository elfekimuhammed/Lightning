"""The register — an account's transactions with a quick-add bar and in-place editing.

One signed Amount (+ money in, − money out). "To" is who the money went to or came from;
typing or picking one of your own accounts there makes the row a transfer.
Used by one account (/accounts/{id}) and by all accounts (/transactions). Only calls services.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

from lightning.categories.domain import Movement
from lightning.core.dates import fmt_date, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.core.refs import DocType

from ..web import container, render

ENTRY_FIELDS = ("date", "account_id", "to", "category", "notes", "amount")
FAR_PAST, FAR_FUTURE = "1900-01-01", "9999-12-31"


def _int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _lists(request: Request) -> dict:
    """Data for the type-and-pick boxes (HTML datalists)."""
    c = container(request)
    categories = []
    for movement, hint in ((Movement.OUTFLOW, "money out"), (Movement.INFLOW, "money in")):
        for cat in c.categories.pickable(movement):
            categories.append((c.categories.display_name(cat.id), hint))
    accounts = c.accounts.list(active_only=True)
    payees = c.transactions.payee_suggestions()
    return {
        "category_options": categories,
        "account_options": [a.label for a in accounts],
        "payee_options": list(payees),
        "payee_categories": {p: c.categories.display_name(cid) for p, cid in payees.items()},
        "accounts": accounts,
    }


def page(request: Request, account_id: int | None, entry: dict | None = None, edit_values: dict | None = None,
         error: str = "", error_field: str = "", status_code: int = 200,
         edit_id: int | None = None, edit_acct: int | None = None):
    """Render the register for one account, or all accounts when account_id is None."""
    c = container(request)
    qp = request.query_params
    account = c.accounts.get(account_id) if account_id else None
    q, month = qp.get("q", "").strip(), qp.get("month", "").strip()
    date_from, date_to = FAR_PAST, FAR_FUTURE
    if month:
        try:
            first, last = parse_month(month)
            date_from, date_to = fmt_date(first), fmt_date(last)
        except ValidationError as exc:
            error, month = error or exc.message, ""
    rows = c.reporting.register(account_id, date_from, date_to, c.transactions.search_ids(q) if q else None)
    edit_id = edit_id or _int(qp.get("edit"))
    edit_acct = edit_acct or _int(qp.get("acct")) or account_id
    if edit_id and edit_values is None:
        row = next((r for r in rows if r.txn_id == edit_id and r.account_id == edit_acct), None)
        if row is not None:
            edit_values = {
                "date": row.date, "account_id": str(row.account_id), "notes": row.notes,
                "to": row.other_account_label if row.type == DocType.TRF else (row.payee or ""),
                "category": row.category_label if row.category_id else "",
                "amount": str(row.amount),
            }
    holdings, account_value = [], None
    if account:
        holdings = c.investments.portfolio(fmt_date(today()), account.id).open
        account_value = c.reporting.account_value(account.id, today())
    keep = {k: v for k, v in (("q", q), ("month", month)) if v}
    base_url = (f"/accounts/{account_id}" if account_id else "/transactions")
    return render(
        request, "register.html", status_code=status_code,
        account=account,
        group=c.accounts.reporting_group(account) if account else "",
        balance=c.reporting.account_balance(account_id, today()) if account else None,
        account_value=account_value, holdings=holdings,
        can_invest=bool(account and account.account_type.value in ("BROKERAGE", "PHYSICAL_ASSET", "OTHER_ASSET")),
        rows=rows, **_lists(request),
        entry=entry or {"date": qp.get("date") or fmt_date(today()), "account_id": qp.get("new_acct", "")},
        edit_id=edit_id if edit_values is not None else None, edit_acct=edit_acct, edit=edit_values or {},
        q=q, month=month, base_url=base_url, keep_qs=urlencode(keep),
        post_url=(f"/accounts/{account_id}/register" if account_id else "/transactions/register"),
        show_account=account is None, error=error, error_field=error_field,
    )


def _resolve(request: Request, row_account: int | None, values: dict):
    """Typed text -> (other account for a transfer | category, to-text)."""
    c = container(request)
    if row_account is None:
        raise ValidationError("Choose an account.", "account")
    other = c.accounts.find_by_text(values["to"])
    if other is not None:
        if other.id == row_account:
            raise ValidationError("That is this same account — pick a different one for a transfer.", "to")
        return other.id, None, ""
    return None, c.categories.find_by_text(values["category"]).id, values["to"].strip()


async def create(request: Request, account_id: int | None):
    """Save the quick-add row; come back ready for the next one."""
    c = container(request)
    form = await request.form()
    entry = {k: str(form.get(k, "")) for k in ENTRY_FIELDS}
    row_account = account_id or _int(entry["account_id"])
    try:
        other_id, category_id, to = _resolve(request, row_account, entry)
        txn = c.transactions.record_in_account(row_account, entry["date"], entry["amount"], category_id, other_id,
                                               to, entry["notes"])
    except LightningError as exc:
        return page(request, account_id, entry=entry, error=exc.message, error_field=exc.field or "",
                    status_code=400)
    return txn, entry


async def update(request: Request, account_id: int | None, txn_id: int):
    """Save an edited row in place."""
    c = container(request)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ENTRY_FIELDS}
    row_account = account_id or _int(values["account_id"])
    try:
        other_id, category_id, to = _resolve(request, row_account, values)
        txn = c.transactions.update_in_account(txn_id, row_account, values["date"], values["amount"], category_id,
                                               other_id, to, values["notes"])
    except LightningError as exc:
        return page(request, account_id, edit_values=values, error=exc.message, error_field=exc.field or "",
                    status_code=400, edit_id=txn_id, edit_acct=row_account)
    return txn, values
