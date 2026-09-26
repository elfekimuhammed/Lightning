from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.transactions.domain import TxnFilter, TxnStatus

from lightning.core.errors import LightningError

from . import register
from ..web import container, redirect, render

router = APIRouter()


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
    deleted = [row for row in rows if row.status == TxnStatus.VOID]
    return render(request, "transactions/deleted.html", rows=deleted)


@router.post("/transactions/register")
async def all_accounts_entry(request: Request):
    result = await register.create(request, None)
    if not isinstance(result, tuple):
        return result
    txn, entry = result
    container(request).reserves.auto_link_transaction(txn.id)
    feedback = register._budget_feedback(container(request), txn)
    return redirect(f"/transactions?date={txn.date}&new_acct={entry['account_id']}",
                    f"Saved {txn.ref}. {feedback}".strip())


@router.post("/transactions/register/{txn_id:int}")
async def all_accounts_update(request: Request, txn_id: int):
    result = await register.update(request, None, txn_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    container(request).reserves.auto_link_transaction(txn.id)
    message = (f"Saved as {txn.ref}. The original transaction is kept in history." if txn.id != txn_id
               else f"Saved {txn.ref}.")
    feedback = register._budget_feedback(container(request), txn)
    message = f"{message} {feedback}".strip()
    return redirect("/transactions", message)


@router.get("/transactions/{txn_id:int}")
async def transaction_detail(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    lines = []
    for line in txn.lines:
        lines.append(dict(
            ref=txn.line_ref(line), account=c.accounts.get(line.account_id).label, account_id=line.account_id,
            asset=c.assets.get_asset(line.asset_id).code, quantity=line.quantity, amount_base=line.amount_base,
            effect=line.effect.value, category=c.categories.get(line.category_id).label if line.category_id else "",
            memo=line.memo,
        ))
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
                  lines=lines, history=c.transactions.history(txn_id), can_split=can_split,
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
    except (ValueError, LightningError) as exc:
        msg = exc.message if isinstance(exc, LightningError) else "Choose a reserve."
        return redirect(f"/transactions/{txn_id}", msg)
    return redirect(f"/transactions/{txn_id}", "Assigned this payment to its reserve.")


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
        c.transactions.delete_many([txn_id])
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
        count = c.transactions.delete_many(ids)
    except LightningError as exc:
        return redirect(destination, exc.message)
    return redirect(destination, f"Deleted {count} transaction(s). You can restore them from history.")


@router.post("/transactions/{txn_id:int}/restore")
async def restore_transaction(request: Request, txn_id: int):
    try:
        txn = container(request).transactions.restore(txn_id)
    except LightningError as exc:
        return redirect(f"/transactions/{txn_id}", exc.message)
    return redirect(_back(request, f"/transactions/{txn.id}"), f"{txn.ref} restored.")


@router.get("/t/{ref}")
async def by_ref(request: Request, ref: str):
    txn = container(request).transactions.get_by_ref(ref)
    return redirect(f"/transactions/{txn.id}")
