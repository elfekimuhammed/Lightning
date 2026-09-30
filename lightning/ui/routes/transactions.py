from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.transactions.domain import TxnFilter, TxnStatus

from lightning.core.errors import LightningError
from lightning.core.dates import fmt_date, parse_date
from lightning.core.money import to_decimal
from lightning.core.errors import ValidationError

from . import register
from ..web import container, redirect, render

router = APIRouter()


@router.get("/transactions/{txn_id:int}/edit-popup")
async def edit_transaction_popup(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    if txn.type.value not in {"OUT", "IN", "TRF"} or txn.is_void:
        return redirect(f"/transactions/{txn_id}", "This transaction is edited from its account or investment workflow.")
    cash_lines = [line for line in txn.lines if c.assets.get_asset(line.asset_id).is_cash]
    if not cash_lines:
        return redirect(f"/transactions/{txn_id}", "This transaction has no cash account to edit.")
    if txn.type.value == "TRF":
        source = next((line for line in cash_lines if line.quantity < 0), cash_lines[0])
        target = next((line for line in cash_lines if line.account_id != source.account_id), None)
        kind, category_id, amount = "transfer", "", abs(source.quantity)
    else:
        source = cash_lines[0]
        target = None
        kind = "out" if source.quantity < 0 else "in"
        split_categories = sorted({line.category_id for line in cash_lines if line.category_id})
        is_split = len(cash_lines) > 1
        category_id = "" if is_split else str(source.category_id or "")
        amount = abs(sum((line.quantity for line in cash_lines), start=0)) if is_split else abs(source.quantity)
    owner_id = next((line.owner_id for line in txn.lines if line.owner_id is not None), None)
    values = {"kind": kind, "date": txn.date, "amount": str(amount), "category_id": category_id,
              "counterparty": txn.counterparty or "", "owner_id": str(owner_id or ""),
              "to_account_id": str(target.account_id) if target else "", "notes": txn.notes,
              "return_to": _back(request, f"/accounts/{source.account_id}"), "account_id": str(source.account_id)}
    from .accounts import _transaction_popup_context
    return render(request, "transactions/form_popup.html", **_transaction_popup_context(
        request, c.accounts.get(source.account_id), values, f"/transactions/{txn_id}/edit-popup", txn_id=txn_id,
        split_categories=[c.categories.display_name(category_id) for category_id in split_categories]
        if txn.type.value != "TRF" and is_split else []))


@router.post("/transactions/{txn_id:int}/edit-popup")
async def save_transaction_popup(request: Request, txn_id: int):
    c = container(request)
    form = await request.form()
    values = {key: str(form.get(key, "")) for key in
              ("kind", "date", "amount", "category_id", "counterparty", "owner_id", "to_account_id", "notes", "account_id")}
    from .accounts import _safe_return, _transaction_popup_context
    txn = c.transactions.get(txn_id)
    account_id = int(values["account_id"]) if values["account_id"].isdigit() else txn.lines[0].account_id
    account = c.accounts.get(account_id)
    values["return_to"] = _safe_return(form.get("return_to"), f"/accounts/{account_id}")
    try:
        cash_lines = [line for line in txn.lines if c.assets.get_asset(line.asset_id).is_cash]
        split_categories = {line.category_id for line in cash_lines if line.category_id}
        if txn.type.value == "OUT" and len(cash_lines) > 1:
            from .accounts import _popup_counterparty
            cp = _popup_counterparty(c, values["counterparty"])
            updated = c.transactions.update_metadata(txn_id, values["date"], cp, values["notes"])
            return redirect(values["return_to"], f"Saved {updated.ref}; split amounts are unchanged.")
        if values["kind"] not in {"out", "in", "transfer"}:
            raise ValidationError("Choose a transaction type.", "kind")
        day = fmt_date(parse_date(values["date"], "date"))
        amount = to_decimal(values["amount"], "amount")
        if amount <= 0: raise ValidationError("Enter an amount greater than zero.", "amount")
        owner_id = int(values["owner_id"]) if values["owner_id"].isdigit() else None
        if values["kind"] == "transfer":
            other = int(values["to_account_id"]) if values["to_account_id"].isdigit() else None
            if not other or other == account_id: raise ValidationError("Choose a different destination account.", "to_account_id")
            signed = -amount
            category_id = None
        else:
            category_id = int(values["category_id"]) if values["category_id"].isdigit() else None
            if not category_id: raise ValidationError("Choose a category.", "category")
            expected = "OUTFLOW" if values["kind"] == "out" else "INFLOW"
            if c.categories.get(category_id).movement.value != expected:
                raise ValidationError("Choose a category that matches this transaction type.", "category")
            other = None
            signed = -amount if values["kind"] == "out" else amount
        from .accounts import _popup_counterparty
        cp = _popup_counterparty(c, values["counterparty"])
        updated = c.transactions.update_in_account(txn_id, account_id, day, signed, category_id, other,
                                                   counterparty=cp, notes=values["notes"], owner_id=owner_id)
        c.reserves.auto_link_transaction(updated.id)
        return redirect(values["return_to"], f"Saved {updated.ref}. {register._budget_feedback(c, updated)}".strip())
    except (LightningError, ValueError) as exc:
        error = exc if isinstance(exc, LightningError) else ValidationError("Choose valid values for this transaction.")
        return render(request, "transactions/form_popup.html", status_code=400,
                      **_transaction_popup_context(request, account, values, f"/transactions/{txn_id}/edit-popup", error,
                                                   txn_id, [c.categories.display_name(category_id)
                                                            for category_id in split_categories]
                                                   if txn.type.value == "OUT" and len(cash_lines) > 1 else []))


def _back(request: Request, default: str) -> str:
    back = request.query_params.get("back", "")
    return back if back.startswith("/") and not back.startswith("//") else default


@router.get("/transactions")
async def all_accounts(request: Request):
    """Every account in one register."""
    return register.page(request, None)


@router.get("/transactions/deleted")
async def deleted_transactions(request: Request):
    c = container(request)
    rows, _ = c.transactions.find(TxnFilter(include_void=True, limit=1000))
    # System revaluations replaced by a recalculation were never deleted by the
    # user and can't be restored, so they stay out of this list.
    replaced = c.transactions.replaced_revaluation_ids()
    deleted = [row for row in rows if row.status == TxnStatus.VOID and row.id not in replaced]
    return render(request, "transactions/deleted.html", rows=deleted)


@router.post("/transactions/register")
async def all_accounts_entry(request: Request):
    result = await register.create(request, None)
    if not isinstance(result, tuple):
        return result
    txn, entry = result
    matched_reserve = container(request).reserves.auto_link_transaction(txn.id)
    feedback = register._budget_feedback(container(request), txn)
    if matched_reserve < 0:
        feedback = (feedback + " Several reserves match; choose beside the transaction in its account list.").strip()
    return redirect(f"/transactions?date={txn.date}&new_acct={entry['account_id']}",
                    f"Saved {txn.ref}. {feedback}".strip())


@router.post("/transactions/register/{txn_id:int}")
async def all_accounts_update(request: Request, txn_id: int):
    result = await register.update(request, None, txn_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    matched_reserve = container(request).reserves.auto_link_transaction(txn.id)
    message = (f"Saved as {txn.ref}. The original transaction is kept in history." if txn.id != txn_id
               else f"Saved {txn.ref}.")
    feedback = register._budget_feedback(container(request), txn)
    if matched_reserve < 0:
        feedback = (feedback + " Several reserves match; choose beside the transaction in its account list.").strip()
    message = f"{message} {feedback}".strip()
    return redirect("/transactions", message)


@router.get("/transactions/{txn_id:int}")
async def transaction_detail(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    lines = []
    cash_effects = []
    for line in txn.lines:
        asset = c.assets.get_asset(line.asset_id)
        account = c.accounts.get(line.account_id)
        lines.append(dict(
            ref=txn.line_ref(line), account=account.label, account_id=line.account_id,
            asset=asset.code, quantity=line.quantity, amount_base=line.amount_base,
            effect=line.effect.value, category=c.categories.get(line.category_id).label if line.category_id else "",
            memo=line.memo, owner_id=line.owner_id,
            owner_name=c.counterparties.get(line.owner_id)["name"] if line.owner_id else "",
        ))
        if asset.is_cash and line.quantity:
            cash_effects.append({"account": account.label, "quantity": line.quantity, "currency": account.currency,
                                 "owner": c.counterparties.get(line.owner_id)["name"] if line.owner_id else "you"})
    can_split = txn.type.value == "OUT" and bool(txn.lines) and all(
        c.assets.get_asset(line.asset_id).is_cash for line in txn.lines)
    expense_categories = [{"id": cat.id, "label": c.categories.display_name(cat.id)}
                          for cat in c.categories.pickable() if cat.movement.value == "OUTFLOW"]
    split_lines = [{"category_id": line.category_id, "amount": -line.quantity}
                   for line in txn.lines if line.category_id is not None]
    budget_impacts = []
    expense_lines = [line for line in txn.lines if line.category_id and line.effect.value == "OUTFLOW"]
    if expense_lines and not txn.is_void:
        budget_month = c.budgets.month_view(txn.date[:7])
        budget_by_id = {line.category_id: line for section in budget_month.sections for line in section.lines}
        seen_categories = set()
        for posting in expense_lines:
            if posting.category_id in seen_categories:
                continue
            seen_categories.add(posting.category_id)
            budget_line = budget_by_id.get(posting.category_id)
            if budget_line:
                shown = budget_line
                if shown.remaining is None and shown.covered:
                    parent = c.categories.get(posting.category_id).parent_id
                    while parent:
                        ancestor = budget_by_id.get(parent)
                        if ancestor and ancestor.remaining is not None:
                            shown = ancestor
                            break
                        parent = c.categories.get(parent).parent_id
                budget_impacts.append({"name": budget_line.name, "remaining": budget_line.remaining,
                                       "covered_by": shown.name if shown is not budget_line else "",
                                       "covered_remaining": shown.remaining if shown is not budget_line else None,
                                       "month": txn.date[:7]})
    return render(request, "transactions/detail.html", txn=txn, summary=c.transactions.summarize(txn),
                  replaced_revaluation=txn.id in c.transactions.replaced_revaluation_ids(),
                  lines=lines, history=c.transactions.history(txn_id), can_split=can_split,
                  cash_effects=cash_effects,
                  expense_categories=expense_categories, split_lines=split_lines,
                  budget_impacts=budget_impacts,
                  reserve_links=c.reserves.links_for_transaction(txn_id), reserves=c.reserves.list_active())


@router.post("/transactions/{txn_id:int}/split")
async def update_transaction_split(request: Request, txn_id: int):
    c = container(request)
    form = await request.form()
    category_ids, amounts = form.getlist("split_category_id"), form.getlist("split_amount")
    allocations = []
    try:
        for category_id, amount in zip(category_ids, amounts):
            if not str(category_id).strip() and not str(amount).strip():
                continue
            if not str(category_id).strip() or not str(amount).strip():
                raise LightningError("Choose a category and amount for every split row.")
            allocations.append((int(category_id), str(amount)))
        txn = c.transactions.update_expense_split(txn_id, allocations)
    except (ValueError, LightningError) as exc:
        msg = exc.message if isinstance(exc, LightningError) else "Choose a valid category for each split row."
        return redirect(f"/transactions/{txn_id}", msg)
    return redirect(f"/transactions/{txn_id}", f"Updated {txn.ref} category split.")


@router.post("/transactions/{txn_id:int}/reserve")
async def link_transaction_reserve(request: Request, txn_id: int):
    c = container(request)
    form = await request.form()
    action = str(form.get("action", "link"))
    try:
        reserve_id = int(str(form.get("reserve_id", "")))
        if action == "unlink":
            c.reserves.unlink_expense(reserve_id, txn_id)
            return redirect(f"/transactions/{txn_id}", "Removed the payment from its reserve.")
        if action != "link":
            raise LightningError("Choose a valid reserve action.")
        c.reserves.set_expense_link(reserve_id, txn_id, str(form.get("amount", "")))
        if form.get("complete") == "1" and c.reserves.get(reserve_id)["status"] == "ACTIVE":
            c.reserves.complete(reserve_id)
    except (ValueError, LightningError) as exc:
        msg = exc.message if isinstance(exc, LightningError) else "Choose a reserve."
        return redirect(_back(request, f"/transactions/{txn_id}"), msg)
    return redirect(_back(request, f"/transactions/{txn_id}"), "Payment matched and reserve completed." if form.get("complete") == "1" else "Assigned this payment to its reserve.")


@router.post("/transactions/{txn_id:int}/void")
async def void_transaction(request: Request, txn_id: int):
    try:
        txn = container(request).transactions.void(txn_id)
    except LightningError as exc:
        return redirect(_back(request, f"/transactions/{txn_id}"), exc.message)
    return redirect(_back(request, f"/transactions/{txn.id}"), f"{txn.ref} is void — it no longer counts.")


@router.post("/transactions/{txn_id:int}/delete")
async def delete_transaction(request: Request, txn_id: int):
    c = container(request)
    try:
        reevaluation = c.transactions.get(txn_id).type.value == "VAL"
        c.transactions.delete_many([txn_id])
        if reevaluation:
            c.reevaluations.process_due()
    except LightningError as exc:
        return redirect(_back(request, f"/transactions/{txn_id}"), exc.message)
    return redirect(_back(request, "/transactions"), "Transaction deleted. You can restore it from its history page.")


@router.post("/transactions/bulk-delete")
async def delete_transactions(request: Request):
    c = container(request)
    form = await request.form()
    ids = [int(value) for value in form.getlist("txn_ids") if str(value).isdigit()]
    back = str(form.get("back", ""))
    destination = back if back.startswith("/") and not back.startswith("//") else "/transactions"
    if not ids:
        return redirect(destination, "Choose at least one transaction.")
    try:
        reevaluation = any(c.transactions.get(txn_id).type.value == "VAL" for txn_id in ids)
        count = c.transactions.delete_many(ids)
        if reevaluation:
            c.reevaluations.process_due()
    except LightningError as exc:
        return redirect(destination, exc.message)
    return redirect(destination, f"Deleted {count} transaction(s). You can restore them from history.")


@router.post("/transactions/{txn_id:int}/restore")
async def restore_transaction(request: Request, txn_id: int):
    try:
        c = container(request)
        txn = c.transactions.restore(txn_id)
        if txn.type.value == "VAL":
            c.reevaluations.process_due()
    except LightningError as exc:
        return redirect(f"/transactions/{txn_id}", exc.message)
    return redirect(_back(request, f"/transactions/{txn.id}"), f"{txn.ref} restored.")


@router.get("/t/{ref}")
async def by_ref(request: Request, ref: str):
    txn = container(request).transactions.get_by_ref(ref)
    return redirect(f"/transactions/{txn.id}")
