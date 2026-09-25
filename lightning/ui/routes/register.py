"""The register — an account's transactions with a quick-add bar and in-place editing.

One signed Amount (+ money in, − money out). "To" is who the money went to or came from;
typing or picking one of your own accounts there makes the row a transfer.
Used by one account (/accounts/{id}) and by all accounts (/transactions). Only calls services.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

from lightning.accounts.domain import INVESTMENT_ACCOUNT_TYPES
from lightning.assets.catalog import instruments as catalog_instruments
from lightning.categories.domain import Movement
from lightning.core.codes import slug
from lightning.core.dates import fmt_date, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.core.money import ZERO, to_decimal
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
            categories.append(c.categories.display_name(cat.id))
    accounts = c.accounts.list(active_only=True)
    payees = c.transactions.payee_suggestions()
    return {
        "category_options": categories,
        "account_options": [a.label for a in accounts],
        "payee_options": list(payees),
        "payee_categories": {p: c.categories.display_name(cid) for p, cid in payees.items()},
        "accounts": accounts,
    }


def _trade_choices(c, account, positions) -> list[dict]:
    """Typeahead choices: bundled stocks/funds plus any custom assets already in this account."""
    if not account or account.account_type not in INVESTMENT_ACCOUNT_TYPES:
        return []
    assets = c.assets.investments(active_only=True)
    by_code = {asset.code: asset for asset in assets}
    held = {position.asset_id: position.quantity for position in positions}
    choices, included_ids = [], set()
    for item in catalog_instruments():
        prefix = "STK" if item["class_code"] == "STOCK" else "FND"
        code = f"{prefix}:{slug(item['ticker'], 20)}"
        asset = by_code.get(code)
        if asset:
            included_ids.add(asset.id)
        choices.append({
            "key": f"asset:{asset.id}" if asset else f"catalog:{item['ticker']}",
            "name": asset.name if asset else item["name"],
            "ticker": item["ticker"],
            "kind": "Stock" if item["class_code"] == "STOCK" else "Fund",
            "holding": str(held.get(asset.id, ZERO)) if asset else "0",
            "unit": asset.unit if asset else ("share" if item["class_code"] == "STOCK" else "unit"),
            "decimals": asset.quantity_decimals if asset else (0 if item["class_code"] == "STOCK" else 4),
        })
    for asset in assets:
        if asset.id in included_ids:
            continue
        ticker = asset.code.split(":", 1)[-1]
        choices.append({"key": f"asset:{asset.id}", "name": asset.name, "ticker": ticker,
                        "kind": c.assets.display_name(asset.asset_class_id),
                        "holding": str(held.get(asset.id, ZERO)), "unit": asset.unit,
                        "decimals": asset.quantity_decimals})
    return sorted(choices, key=lambda item: (item["name"].casefold(), item["ticker"].casefold()))


def page(request: Request, account_id: int | None, entry: dict | None = None, edit_values: dict | None = None,
         error: str = "", error_field: str = "", status_code: int = 200,
         edit_id: int | None = None, edit_acct: int | None = None,
         investment_entry: dict | None = None, investment_error_field: str = ""):

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
    can_invest = bool(account and account.account_type in INVESTMENT_ACCOUNT_TYPES)
    trade_choices = _trade_choices(c, account, holdings)
    investment_entry = investment_entry or {"date": fmt_date(today()), "instrument_key": "", "units": "",
                                            "total": "", "unit_price": "", "price_basis": "total", "notes": ""}
    if investment_entry.get("instrument_key") and not investment_entry.get("instrument_label"):
        picked = next((item for item in trade_choices if item["key"] == investment_entry["instrument_key"]), None)
        if picked:
            investment_entry["instrument_label"] = f"{picked['name']} · {picked['ticker']}"
    keep = {k: v for k, v in (("q", q), ("month", month)) if v}
    base_url = (f"/accounts/{account_id}" if account_id else "/transactions")
    return render(
        request, "register.html", status_code=status_code,
        account=account,
        group=c.accounts.reporting_group(account) if account else "",
        balance=c.reporting.account_balance(account_id, today()) if account else None,
        account_value=account_value, holdings=holdings,
        can_invest=can_invest, trade_choices=trade_choices,
        investment_entry=investment_entry, investment_error_field=investment_error_field,
        cash_accounts=[a for a in c.accounts.list(active_only=True) if account and a.id != account.id]
                      if can_invest and account.account_type.value != "BROKERAGE" else [],
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


async def create_investment_entry(request: Request, account_id: int):
    """Record a buy, sell, or dividend from the account's inline transaction row."""
    c = container(request)
    account = c.accounts.get(account_id)
    form = await request.form()
    values = {key: str(form.get(key, "")).strip() for key in
              ("date", "instrument_key", "units", "total", "unit_price", "price_basis", "cash_account_id", "notes")}
    values["instrument_label"] = str(form.get("instrument_label", ""))
    try:
        if account.account_type not in INVESTMENT_ACCOUNT_TYPES:
            raise ValidationError("Investment entries can only be added to an investment account.")
        key = values["instrument_key"]
        if not key:
            raise ValidationError("Type a stock or fund and choose it from the results.", "instrument")
        units = to_decimal(values["units"], "units") if values["units"] else None
        total = values["total"]
        unit_price = values["unit_price"]
        if units is None and not total:
            raise ValidationError("Enter a dividend amount, or add units for a buy or sell.", "total")
        if units == ZERO:
            raise ValidationError("Units must be positive for a buy or negative for a sell.", "units")
        ticker_row = None
        asset = None
        with c.db.transaction():
            if key.startswith("asset:") and key[6:].isdigit():
                asset = c.assets.get_asset(int(key[6:]))
                if asset.is_cash or not asset.active:
                    raise ValidationError("Choose an active investment.", "instrument")
            elif key.startswith("catalog:"):
                ticker = key[8:]
                ticker_row = next((row for row in catalog_instruments() if row["ticker"].casefold() == ticker.casefold()), None)
                if ticker_row is None:
                    raise ValidationError("That instrument is not in the local catalogue. Search and choose a result.",
                                          "instrument")
                prefix = "STK" if ticker_row["class_code"] == "STOCK" else "FND"
                code = f"{prefix}:{slug(ticker_row['ticker'], 20)}"
                asset = next((item for item in c.assets.investments() if item.code == code), None)
                if asset is None:
                    if units is not None and units < ZERO:
                        raise ValidationError(f"You do not hold {ticker_row['name']} in this account yet.", "units")
                    asset = c.assets.create_investment(ticker_row["name"], ticker_row["class_code"],
                                                       ticker_row["ticker"])
            else:
                raise ValidationError("Choose an investment from the results.", "instrument")
            if units is None:
                if not total:
                    raise ValidationError("Enter the dividend amount.", "total")
                txn = c.investments.dividend(values["date"], account.id, asset.id, total, values["notes"])
            elif units > ZERO:
                basis = values["price_basis"]
                if basis == "unit_price" or (unit_price and not total):
                    if not unit_price:
                        raise ValidationError("Enter a price per unit or the total paid.", "unit_price")
                    txn = c.investments.buy(values["date"], account.id, asset.id, units, unit_price,
                                            cash_account_id=int(values["cash_account_id"] or 0) or None,
                                            notes=values["notes"])
                else:
                    if not total:
                        raise ValidationError("Enter the total paid or a price per unit.", "total")
                    txn = c.investments.buy_total(values["date"], account.id, asset.id, units, total,
                                                  cash_account_id=int(values["cash_account_id"] or 0) or None,
                                                  notes=values["notes"])
            else:
                units = -units
                basis = values["price_basis"]
                if basis == "unit_price" or (unit_price and not total):
                    if not unit_price:
                        raise ValidationError("Enter a price per unit or the total received.", "unit_price")
                    txn = c.investments.sell(values["date"], account.id, asset.id, units, unit_price,
                                             cash_account_id=int(values["cash_account_id"] or 0) or None,
                                             notes=values["notes"])
                else:
                    if not total:
                        raise ValidationError("Enter the total received or a price per unit.", "total")
                    txn = c.investments.sell_total(values["date"], account.id, asset.id, units, total,
                                                   cash_account_id=int(values["cash_account_id"] or 0) or None,
                                                   notes=values["notes"])
    except LightningError as exc:
        return page(request, account_id, investment_entry=values, error=exc.message,
                    investment_error_field=exc.field or "", status_code=400)
    return txn, values
