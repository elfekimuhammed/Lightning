"""The register — Actual-style list of transactions with an entry row and in-place editing.

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

ENTRY_FIELDS = ("date", "account_id", "payee", "notes", "choice", "payment", "deposit")
FAR_PAST, FAR_FUTURE = "1900-01-01", "9999-12-31"


def choices(request: Request) -> list[tuple[str, list[tuple[str, str]]]]:
    """Category list grouped for a <select>, plus 'Transfer ↔ account' options."""
    c = container(request)
    result = []
    for title, movement in (("Money out", Movement.OUTFLOW), ("Money in", Movement.INFLOW)):
        loose = []
        for group, items in c.categories.groups(movement, include_inactive=False):
            if items:
                result.append((f"{title} · {group.name}",
                               [(f"cat:{i.id}", ("— " * (i.depth - 2)) + i.name) for i in items]))
            else:
                loose.append((f"cat:{group.id}", group.name))
        if loose:
            result.append((title, loose))
    accounts = c.accounts.list(active_only=True)
    if len(accounts) > 1:
        result.append(("Transfer ↔ another account", [(f"acct:{a.id}", a.label) for a in accounts]))
    return result


def parse_choice(value: str) -> tuple[int | None, int | None]:
    kind, _, raw = (value or "").partition(":")
    target = int(raw) if raw.isdigit() else None
    return (target if kind == "cat" else None), (target if kind == "acct" else None)


def _int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


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
                "payee": row.payee or (row.description if row.type == DocType.TRF else ""),
                "choice": f"cat:{row.category_id}" if row.category_id else
                          (f"acct:{row.other_account_id}" if row.other_account_id else ""),
                "payment": str(row.payment) if row.payment else "",
                "deposit": str(row.deposit) if row.deposit else "",
            }
    keep = {k: v for k, v in (("q", q), ("month", month)) if v}
    base_url = (f"/accounts/{account_id}" if account_id else "/transactions")
    return render(
        request, "register.html", status_code=status_code,
        account=account,
        group=c.accounts.reporting_group(account) if account else "",
        balance=c.reporting.account_balance(account_id, today()) if account else None,
        balance_all=c.reporting.account_balance(account_id) if account else None,
        rows=rows, choices=choices(request), accounts=c.accounts.list(active_only=True),
        payees={p: f"cat:{cid}" for p, cid in c.transactions.payee_suggestions().items()},
        entry=entry or {"date": qp.get("date") or fmt_date(today()), "account_id": qp.get("new_acct", "")},
        edit_id=edit_id if edit_values is not None else None, edit_acct=edit_acct, edit=edit_values or {},
        q=q, month=month, base_url=base_url, keep_qs=urlencode(keep),
        post_url=(f"/accounts/{account_id}/register" if account_id else "/transactions/register"),
        show_account=account is None, error=error, error_field=error_field,
    )


async def create(request: Request, account_id: int | None):
    """Save the entry row; come back ready for the next one."""
    c = container(request)
    form = await request.form()
    entry = {k: str(form.get(k, "")) for k in ENTRY_FIELDS}
    category_id, other_id = parse_choice(entry["choice"])
    target_account = account_id or _int(entry["account_id"])
    try:
        if target_account is None:
            raise ValidationError("Choose an account.", "account")
        txn = c.transactions.record_in_account(target_account, entry["date"], entry["payment"], entry["deposit"],
                                               category_id, other_id, entry["payee"], entry["notes"])
    except LightningError as exc:
        return page(request, account_id, entry=entry, error=exc.message, error_field=exc.field or "",
                    status_code=400)
    return txn, entry


async def update(request: Request, account_id: int | None, txn_id: int):
    """Save an edited row in place."""
    c = container(request)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ENTRY_FIELDS}
    category_id, other_id = parse_choice(values["choice"])
    row_account = account_id or _int(values["account_id"])
    try:
        if row_account is None:
            raise ValidationError("Choose an account.", "account")
        txn = c.transactions.update_in_account(txn_id, row_account, values["date"], values["payment"],
                                               values["deposit"], category_id, other_id, values["payee"],
                                               values["notes"])
    except LightningError as exc:
        return page(request, account_id, edit_values=values, error=exc.message, error_field=exc.field or "",
                    status_code=400, edit_id=txn_id, edit_acct=row_account)
    return txn, values
