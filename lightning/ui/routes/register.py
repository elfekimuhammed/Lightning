"""The register — an account's transactions with a quick-add bar and in-place editing.

One signed Amount (+ money in, − money out). "Counterparty" is the person or account on the other side;
typing or picking one of your own accounts there makes the row a transfer.
Used by one account (/accounts/{id}) and by all accounts (/transactions). Only calls services.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

from lightning.accounts.domain import INVESTMENT_ACCOUNT_TYPES
from lightning.assets.catalog import instruments as catalog_instruments
from lightning.core.codes import slug
from lightning.core.dates import fmt_date, parse_date, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.core.refs import DocType

from ..web import container, render

ENTRY_FIELDS = ("date", "account_id", "counterparty", "counterparty_choice", "category", "category_choice", "whom", "notes", "amount")
FAR_PAST, FAR_FUTURE = "1900-01-01", "9999-12-31"


def _int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _lists(request: Request) -> dict:
    """Data for register typeahead pickers."""
    c = container(request)
    categories = [{"id": cat.id, "name": cat.name,
                   "parent": c.categories.get(cat.parent_id).name if cat.parent_id else "",
                   "label": c.categories.display_name(cat.id)} for cat in c.categories.pickable()]
    categories.sort(key=lambda row: (row["parent"].casefold(), row["name"].casefold(), row["id"]))
    accounts = c.accounts.list(active_only=True)
    counterparty_options = c.counterparties.search_names()
    counterparty_categories = {}
    for name in counterparty_options:
        party = c.counterparties.resolve(name)
        # Keep every saved Counterparty available to the register picker;
        # the default category is optional and only affects autofill.
        counterparty_categories[name] = None
        if party and party["default_category_id"]:
            counterparty_categories[name] = c.categories.display_name(party["default_category_id"])
    return {
        "category_choices": categories,
        "account_options": [a.name for a in accounts],
        "counterparty_options": counterparty_options,
        "counterparty_categories": counterparty_categories,
        "accounts": accounts,
    }


def _counterparty_matches(c, value: str):
    matches = []
    for name, score in c.counterparties.suggestions(value):
        party = c.counterparties.resolve(name)
        if party:
            matches.append({"id": party["id"], "name": name, "score": score})
    return matches


def _category_matches(c, value: str):
    return [{"id": category.id, "name": c.categories.display_name(category.id), "score": score}
            for category, score in c.categories.suggestions(value)]


def _budget_feedback(c, txn) -> str:
    if txn.status.value != "POSTED":
        return ""
    budget_effect_lines = [line for line in txn.lines if line.category_id and line.effect.value == "OUTFLOW"]
    if not budget_effect_lines:
        return ""
    month = txn.date[:7]
    view = c.budgets.month_view(month)
    by_id = {line.category_id: line for section in view.sections for line in section.lines}
    impacts = []
    seen = set()
    for line in budget_effect_lines:
        if not line.category_id or line.category_id not in by_id or line.category_id in seen:
            continue
        seen.add(line.category_id)
        budget_line = by_id[line.category_id]
        shown = budget_line
        if shown.remaining is None and shown.covered:
            parent = c.categories.get(line.category_id).parent_id
            while parent:
                ancestor = by_id.get(parent)
                if ancestor and ancestor.remaining is not None:
                    shown = ancestor
                    break
                parent = c.categories.get(parent).parent_id
        label = budget_line.name if shown is budget_line else f"inside {shown.name}"
        impacts.append(f"{label}: " + (f"{fmt(shown.remaining)} {c.base_currency} left this month"
                                       if shown.remaining is not None else "no covering limit"))
    return "Budget · " + "; ".join(impacts[:2]) if impacts else ""


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
    from_query, to_query = qp.get("date_from", "").strip(), qp.get("date_to", "").strip()
    if from_query or to_query:
        try:
            if not from_query or not to_query:
                raise ValidationError("Choose both start and end dates.")
            date_from, date_to = fmt_date(parse_date(from_query)), fmt_date(parse_date(to_query))
            if date_to < date_from:
                raise ValidationError("End date must be on or after the start date.")
        except ValidationError as exc:
            error, from_query, to_query = error or exc.message, "", ""
    elif month:
        try:
            first, last = parse_month(month)
            date_from, date_to = fmt_date(first), fmt_date(last)
        except ValidationError as exc:
            error, month = error or exc.message, ""
    rows = c.reporting.register(account_id, date_from, date_to, c.transactions.search_ids(q) if q else None)
    custody_owners = {row.txn_id: c.money_from_others.transaction_owner(row.txn_id) for row in rows}
    edit_id = edit_id or _int(qp.get("edit"))
    edit_acct = edit_acct or _int(qp.get("acct")) or account_id
    if edit_id and edit_values is None:
        row = next((r for r in rows if r.txn_id == edit_id and r.account_id == edit_acct), None)
        if row is not None:
            edit_values = {
                "date": row.date, "account_id": str(row.account_id), "notes": row.notes,
                "counterparty": row.other_account_label if row.type == DocType.TRF else (row.counterparty or ""),
                "category": row.category_label if row.category_id else "",
                "amount": str(row.amount),
                "whom": c.money_from_others.transaction_owner(row.txn_id),
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
    keep = {k: v for k, v in (("q", q), ("month", month), ("date_from", from_query), ("date_to", to_query)) if v}
    base_url = (f"/accounts/{account_id}" if account_id else "/transactions")
    return render(
        request, "register.html", status_code=status_code,
        account=account,
        group=c.accounts.reporting_group(account) if account else "",
        balance=c.reporting.account_balance(account_id, today()) if account else None,
        owned_cash=(c.reporting.account_balance(account_id, today()) -
                    c.money_from_others.cash_total_for_account(account_id, fmt_date(today()))) if account else None,
        account_value=account_value, holdings=holdings,
        owned_account_value=c.reporting.owned_account_value(account_id, today()) if account else None,
        can_invest=can_invest, trade_choices=trade_choices,
        investment_entry=investment_entry, investment_error_field=investment_error_field,
        cash_accounts=[a for a in c.accounts.list(active_only=True) if account and a.id != account.id]
                      if can_invest and account.account_type.value != "BROKERAGE" else [],
        rows=rows, **_lists(request),
        custody_owners=custody_owners,
        custody_present=any(custody_owners.values()),
        entry=entry or {"date": qp.get("date") or fmt_date(today()), "account_id": qp.get("new_acct", "")},
        edit_id=edit_id if edit_values is not None else None, edit_acct=edit_acct, edit=edit_values or {},
        q=q, month=month, date_from=from_query, date_to=to_query, base_url=base_url, keep_qs=urlencode(keep),
        post_url=(f"/accounts/{account_id}/register" if account_id else "/transactions/register"),
        show_account=account is None, error=error, error_field=error_field,
        counterparty_matches=_counterparty_matches(c, (entry or {}).get("counterparty", "")),
        category_matches=_category_matches(c, (entry or {}).get("category", "")),
        review_mode=("counterparty" if error_field == "counterparty_review" else
                     ("category" if error_field == "category_review" else "")),
    )


def _resolve(request: Request, row_account: int | None, values: dict):
    """Typed counterparty text -> internal account transfer or external transaction party."""
    c = container(request)
    if row_account is None:
        raise ValidationError("Choose an account.", "account")
    raw = values["counterparty"].strip()
    other = c.accounts.find_by_text(raw)
    if other is not None:
        if other.id == row_account:
            raise ValidationError("That is this same account — pick a different counterparty for a transfer.", "counterparty")
        return other.id, None, ""
    party = c.counterparties.resolve(raw)
    choice = values.get("counterparty_choice", "")
    if not raw:
        canonical = ""
    elif party:
        canonical = party["name"]
    else:
        guesses = c.counterparties.suggestions(raw)
        if guesses:
            if choice.startswith("existing:"):
                selected_id = _int(choice.split(":", 1)[1])
                selected = c.counterparties.get(selected_id) if selected_id else None
                if not selected or selected["name"] not in {name for name, _ in guesses}:
                    raise ValidationError("Choose one of the suggested counterparties, or explicitly create this name.", "counterparty")
                c.counterparties.add_alias(int(selected["id"]), raw)
                canonical = selected["name"]
            elif choice == "create":
                canonical = raw
                c.counterparties.create(canonical)
            else:
                names = ", ".join(name for name, _ in guesses[:3])
                raise ValidationError(f"Review similar Counterparties before saving: {names}.", "counterparty_review")
        else:
            if choice == "create":
                canonical = raw
                c.counterparties.create(canonical)
            else:
                raise ValidationError("Confirm whether to create this new Counterparty.", "counterparty_review")

    category_text = values["category"].strip()
    category_choice = _int(values.get("category_choice"))
    if not category_text and category_choice is None and party and party.get("default_category_id"):
        default_category_id = int(party["default_category_id"])
        if default_category_id in {item.id for item in c.categories.pickable()}:
            category_choice = default_category_id
    if category_choice is not None:
        category = c.categories.get(category_choice)
        if category.id not in {item.id for item in c.categories.pickable()}:
            raise ValidationError("Choose one of the suggested broad categories.", "category")
    else:
        exact = [item for item in c.categories.pickable()
                 if category_text.casefold() in {item.name.casefold(), c.categories.display_name(item.id).casefold(),
                                                 item.code.casefold()}]
        if not exact:
            exact = [item for item in c.categories.tree(active_only=False)
                     if not item.is_root and item.depth == 2 and item.code.startswith("EXP.")
                     and category_text.casefold() in {item.name.casefold(), c.categories.display_name(item.id).casefold(),
                                                      item.code.casefold()}]
        if len(exact) == 1:
            category = exact[0]
        elif len(exact) > 1 or c.categories.suggestions(category_text):
            raise ValidationError("Review similar categories and choose the one you mean.", "category_review")
        else:
            try:
                category = c.categories.find_by_text(category_text)
            except ValidationError:
                # System categories are intentionally absent from the picker,
                # but an imported row must be editable without changing its
                # category first.
                system = [item for item in c.categories.tree(active_only=True)
                          if item.is_system and category_text.casefold() in {
                              item.name.casefold(), c.categories.display_name(item.id).casefold(),
                              item.code.casefold()}]
                if len(system) != 1:
                    raise
                category = system[0]
    return None, category.id, canonical


async def create(request: Request, account_id: int | None):
    """Save the quick-add row; come back ready for the next one."""
    c = container(request)
    form = await request.form()
    entry = {k: str(form.get(k, "")) for k in ENTRY_FIELDS}
    row_account = account_id or _int(entry["account_id"])
    try:
        with c.db.transaction():
            other_id, category_id, counterparty = _resolve(request, row_account, entry)
            txn = c.transactions.record_in_account(row_account, entry["date"], entry["amount"], category_id, other_id,
                                                   counterparty, entry["notes"])
            category = c.categories.get(category_id) if category_id else None
            amount = to_decimal(entry["amount"], "amount")
            if other_id:
                source, target = (other_id, row_account) if amount > ZERO else (row_account, other_id)
                owner = _transfer_custody_owner(c, entry)
                c.money_from_others.sync_transfer(txn.id, txn.date, owner, source, target, abs(amount), entry["notes"])
            else:
                owner = _custody_owner(c, entry, category)
                c.money_from_others.sync_transaction(txn.id, txn.date, owner, row_account, amount, entry["notes"])
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
        with c.db.transaction():
            other_id, category_id, counterparty = _resolve(request, row_account, values)
            txn = c.transactions.update_in_account(txn_id, row_account, values["date"], values["amount"], category_id,
                                                   other_id, counterparty, values["notes"])
            category = c.categories.get(category_id) if category_id else None
            if txn.id != txn_id:
                c.money_from_others.sync_transaction(txn_id, values["date"], None, row_account, ZERO, "")
            amount = to_decimal(values["amount"], "amount")
            if other_id:
                source, target = (other_id, row_account) if amount > ZERO else (row_account, other_id)
                owner = _transfer_custody_owner(c, values)
                c.money_from_others.sync_transfer(txn.id, txn.date, owner, source, target, abs(amount), values["notes"])
            else:
                owner = _custody_owner(c, values, category)
                c.money_from_others.sync_transaction(txn.id, txn.date, owner, row_account, amount, values["notes"])
    except LightningError as exc:
        return page(request, account_id, edit_values=values, error=exc.message, error_field=exc.field or "",
                    status_code=400, edit_id=txn_id, edit_acct=row_account)
    return txn, values


def _custody_owner(c, values: dict, category) -> str | None:
    if not category or category.code != "EXP.PERSONAL.CUSTODY":
        return None
    name = values.get("whom", "").strip()
    party = c.counterparties.resolve(name)
    if not party:
        raise ValidationError("Choose a saved Counterparty in Whom. Add a new person from the Counterparties tab first.",
                              "whom")
    if not party["active"]:
        raise ValidationError("That Counterparty is archived. Activate it before using it as Whom.", "whom")
    return party["name"]


def _transfer_custody_owner(c, values: dict) -> str | None:
    """Transfer custody only when the user explicitly identifies its owner."""
    name = values.get("whom", "").strip()
    if name.casefold() in {"self", "me", "my money", "my own money"}:
        return None
    if name:
        party = c.counterparties.resolve(name)
        if not party or not party["active"]:
            raise ValidationError("Choose an active saved Counterparty in Whom.", "whom")
        return party["name"]
    return None


async def create_investment_entry(request: Request, account_id: int):
    """Record a buy, sell, or dividend from the account's inline transaction row."""
    c = container(request)
    account = c.accounts.get(account_id)
    form = await request.form()
    values = {key: str(form.get(key, "")).strip() for key in
              ("date", "instrument_key", "trade_action", "units", "total", "unit_price", "price_basis", "fees",
               "fees_included", "cash_account_id", "notes", "whom")}
    values["instrument_label"] = str(form.get("instrument_label", ""))
    values["is_others"] = "1" if form.get("is_others") else ""
    try:
        if account.account_type not in INVESTMENT_ACCOUNT_TYPES:
            raise ValidationError("Investment entries can only be added to an investment account.")
        key = values["instrument_key"]
        if not key:
            raise ValidationError("Type a stock or fund and choose it from the results.", "instrument")
        action = values["trade_action"] or "buy"
        if action not in {"buy", "sell", "dividend"}:
            raise ValidationError("Choose Buy, Sell, or Dividend.", "trade_action")
        units = to_decimal(values["units"], "units") if values["units"] and action != "dividend" else None
        if units is not None and units < ZERO:
            raise ValidationError("Enter units as a positive quantity; choose Sell for a sale.", "units")
        if units is not None and action == "sell":
            units = -units
        signed_units = units or ZERO
        total = values["total"]
        unit_price = values["unit_price"]
        if (action == "dividend" or units is None) and not total:
            raise ValidationError("Enter a dividend amount, or add units for a buy or sell.", "total")
        if action != "dividend" and units is None:
            raise ValidationError("Enter the number of units.", "units")
        if units == ZERO:
            raise ValidationError("Units must be greater than zero.", "units")
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
                                            fees=values["fees"],
                                            cash_account_id=int(values["cash_account_id"] or 0) or None,
                                            notes=values["notes"])
                else:
                    if not total:
                        raise ValidationError("Enter the total paid or a price per unit.", "total")
                    txn = c.investments.buy_total(values["date"], account.id, asset.id, units, total,
                                                  fees=values["fees"], fees_included=values["fees_included"] != "0",
                                                  cash_account_id=int(values["cash_account_id"] or 0) or None,
                                                  notes=values["notes"])
            else:
                units = -units
                basis = values["price_basis"]
                if basis == "unit_price" or (unit_price and not total):
                    if not unit_price:
                        raise ValidationError("Enter a price per unit or the total received.", "unit_price")
                    txn = c.investments.sell(values["date"], account.id, asset.id, units, unit_price,
                                             fees=values["fees"],
                                             cash_account_id=int(values["cash_account_id"] or 0) or None,
                                             notes=values["notes"])
                else:
                    if not total:
                        raise ValidationError("Enter the total received or a price per unit.", "total")
                    txn = c.investments.sell_total(values["date"], account.id, asset.id, units, total,
                                                   fees=values["fees"], fees_included=values["fees_included"] != "0",
                                                   cash_account_id=int(values["cash_account_id"] or 0) or None,
                                                   notes=values["notes"])
            owner = None
            if values["is_others"]:
                party = c.counterparties.resolve(values["whom"])
                if not party or not party["active"]:
                    raise ValidationError("Choose an active saved Counterparty in Whom.", "whom")
                owner = party["name"]
            c.money_from_others.sync_investment(txn.id, txn.date, owner, account.id, asset.id, signed_units)
            if owner:
                cash_line = next((line for line in txn.lines if c.assets.get_asset(line.asset_id).is_cash), None)
                if cash_line:
                    cash_amount = cash_line.quantity
                    if cash_amount < ZERO:
                        available = c.money_from_others.cash_balance(owner, cash_line.account_id, txn.date)
                        cash_amount = -min(abs(cash_amount), max(available, ZERO))
                    c.money_from_others.sync_transaction(txn.id, txn.date, owner, cash_line.account_id,
                                                         cash_amount, values["notes"])
    except LightningError as exc:
        return page(request, account_id, investment_entry=values, error=exc.message,
                    investment_error_field=exc.field or "", status_code=400)
    return txn, values
