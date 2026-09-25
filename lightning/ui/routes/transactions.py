from __future__ import annotations

from fastapi import APIRouter, Request

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


@router.post("/transactions/register")
async def all_accounts_entry(request: Request):
    result = await register.create(request, None)
    if not isinstance(result, tuple):
        return result
    txn, entry = result
    return redirect(f"/transactions?date={txn.date}&new_acct={entry['account_id']}", f"Saved {txn.ref}.")


@router.post("/transactions/register/{txn_id:int}")
async def all_accounts_update(request: Request, txn_id: int):
    result = await register.update(request, None, txn_id)
    if not isinstance(result, tuple):
        return result
    txn, _ = result
    return redirect("/transactions", f"Saved {txn.ref}.")


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
    return render(request, "transactions/detail.html", txn=txn, summary=c.transactions.summarize(txn),
                  lines=lines, history=c.transactions.history(txn_id))


@router.post("/transactions/{txn_id:int}/void")
async def void_transaction(request: Request, txn_id: int):
    txn = container(request).transactions.void(txn_id)
    return redirect(_back(request, f"/transactions/{txn.id}"), f"{txn.ref} is void — it no longer counts.")


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
