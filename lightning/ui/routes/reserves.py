from __future__ import annotations


from fastapi import APIRouter, Request, Response

from lightning.core.dates import month_of, today
from lightning.core.errors import LightningError
from lightning.core.money import ZERO, fmt, from_e6
from lightning.core.money import to_decimal
from lightning.transactions.domain import TxnFilter
from lightning.core.refs import DocType
from lightning.categories.domain import Movement

from .. import charts, keynotes
from ..web import container, redirect, render

router = APIRouter(prefix="/reserves")


def _allocate(c, reserve_id: int, amount: str):
    current = c.reserves.get(reserve_id)
    value = to_decimal(amount, "allocated")
    cash = c.reporting.owned_liquid_cash(today())
    assigned = c.reserves.cash_summary(cash)["allocated"]
    next_effective = max(value - current["spent"], ZERO)
    if assigned - current["effective_allocated"] + next_effective > cash:
        raise LightningError("Reserves cannot be more than the cash you own.")
    return c.reserves.allocate(reserve_id, value)


def _context(request: Request, error: str = ""):
    c = container(request)
    reserves = c.reserves.list_active()
    emergency = next((item for item in reserves if item["kind"] == "EMERGENCY"), None)
    # Emergency coverage uses Average monthly income, the same figure the budget and forecast use.
    income = c.budgets.income_average(month_of(today()))
    emergency_months = (emergency["effective_allocated"] / income.amount) if emergency and income.amount else None
    listed = [item for item in reserves if item["kind"] != "EMERGENCY"]
    for item in listed:
        item["payments"] = [row | {"amount": from_e6(row["amount_e6"])}
                            for row in c.reserves.links_for_reserve(item["id"])]
    # Completed dated rows are payment occurrences; undated project goals remain
    # a separate savings-goal workflow.
    completed = [item for item in c.reserves.list_completed() if item.get("due_date")]
    for item in completed:
        item["payments"] = [row | {"amount": from_e6(row["amount_e6"])}
                            for row in c.reserves.links_for_reserve(item["id"])]
    set_aside = emergency["effective_allocated"] if emergency else ZERO
    emergency_meter = charts.meter(set_aside, income.six_months) if income.six_months else None
    position = c.position.at(today())
    notes = [n for n in (keynotes.emergency(emergency_months, income.six_months),
                         keynotes.note("info", f"{fmt(position.free_cash)} free cash",
                                       "Cash you own after reserves and bills due. Reserves stay in your accounts.")
                         if position.free_cash is not None else None) if n]
    return {"reserves": listed, "completed_reserves": completed, "notes": notes, "emergency_meter": emergency_meter,
            "emergency_set_aside": set_aside,
            "emergency": emergency, "income": income, "emergency_months": emergency_months,
            "pos": position, "error": error,
            "counterparties": c.counterparties.list_active(),
            "accounts": [account for account in c.accounts.list(active_only=True)
                         if account.account_type.value in ("CASH", "BANK", "DEPOSIT", "BROKERAGE")],
            "categories": c.categories.pickable(Movement.OUTFLOW),
            "category_parent_names": {cat.id: cat.name for cat in c.categories.tree() if cat.depth == 1}}


@router.get("")
async def list_reserves(request: Request):
    # Reserves live under Cash planning; old links and form redirects land there.
    query = request.url.query
    return redirect("/plan/reserves" + (f"?{query}" if query else ""))


@router.post("")
async def create_reserve(request: Request):
    c = container(request)
    form = await request.form()
    try:
        with c.db.transaction():
            reserve = c.reserves.create(str(form.get("name", "")), str(form.get("target", "")),
                                        "PROJECT", str(form.get("due_date", "")) or None,
                                        str(form.get("recurrence", "NONE")),
                                        int(str(form.get("counterparty_id", ""))) if form.get("match_by") == "counterparty" and str(form.get("counterparty_id", "")).isdigit() else None,
                                        int(str(form.get("category_id", ""))) if form.get("match_by") == "category" and str(form.get("category_id", "")).isdigit() else None,
                                        int(str(form.get("account_id", ""))) if form.get("match_by") == "account" and str(form.get("account_id", "")).isdigit() else None)
            allocated = str(form.get("allocated", "")).strip()
            if allocated:
                _allocate(c, reserve["id"], allocated)
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return render(request, "reserves.html", status_code=400, **_context(request, exc.message))
    return redirect("/reserves", f"Created {reserve['name']}.")


@router.post("/emergency")
async def save_emergency_fund(request: Request):
    c = container(request)
    form = await request.form()
    try:
        salary_target = (c.budgets.income_average(month_of(today())).amount or ZERO) * 6
        amount = str(form.get("allocated", ""))
        existing = next((row for row in c.reserves.list_active() if row["kind"] == "EMERGENCY"), None)
        assigned = c.reserves.cash_summary(c.reporting.owned_liquid_cash(today()))["allocated"]
        value = to_decimal(amount, "allocated")
        old_effective = existing["effective_allocated"] if existing else ZERO
        if assigned - old_effective + value > c.reporting.owned_liquid_cash(today()):
            raise LightningError("Reserves cannot be more than the cash you own.")
        reserve = c.reserves.set_emergency_fund(amount, salary_target)
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return render(request, "reserves.html", status_code=400, **_context(request, exc.message))
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/reserves", f"Saved Emergency Fund: {reserve['allocated']} reserved.")


@router.post("/{reserve_id:int}/edit")
async def edit_reserve(request: Request, reserve_id: int):
    c = container(request)
    form = await request.form()
    try:
        reserve = c.reserves.update(reserve_id, str(form.get("name", "")), str(form.get("target", "")),
                                    str(form.get("due_date", "")) or None,
                                    str(form.get("recurrence", "NONE")),
                                    int(str(form.get("counterparty_id", ""))) if form.get("match_by") == "counterparty" and str(form.get("counterparty_id", "")).isdigit() else None,
                                    int(str(form.get("category_id", ""))) if form.get("match_by") == "category" and str(form.get("category_id", "")).isdigit() else None,
                                    int(str(form.get("account_id", ""))) if form.get("match_by") == "account" and str(form.get("account_id", "")).isdigit() else None)
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect("/reserves", exc.message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/reserves", f"Saved {reserve['name']}.")


@router.post("/{reserve_id:int}/allocate")
async def allocate_reserve(request: Request, reserve_id: int):
    c = container(request)
    form = await request.form()
    try:
        reserve = _allocate(c, reserve_id, str(form.get("allocated", "")))
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect("/reserves", exc.message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/reserves", f"Updated cash assigned to {reserve['name']}.")


@router.post("/{reserve_id:int}/complete")
async def complete_reserve(request: Request, reserve_id: int):
    try:
        reserve = container(request).reserves.complete(reserve_id)
    except LightningError as exc:
        return redirect("/reserves", exc.message)
    return redirect("/reserves", f"Completed {reserve['name']}; its assigned cash is free again.")


@router.get("/{reserve_id:int}/payments")
async def reserve_payments(request: Request, reserve_id: int):
    c = container(request)
    reserve = c.reserves.get(reserve_id)
    payments, _ = c.transactions.find(TxnFilter(types=[DocType.OUT], limit=100))
    return render(request, "reserve_payments.html", reserve=reserve, payments=payments)


@router.post("/{reserve_id:int}/payments")
async def link_reserve_payment(request: Request, reserve_id: int):
    c = container(request)
    form = await request.form()
    try:
        txn_id = int(str(form.get("transaction_id", "")))
        c.reserves.set_expense_link(reserve_id, txn_id, str(form.get("amount", "")))
    except (ValueError, LightningError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Choose a posted expense."
        return redirect(f"/reserves/{reserve_id}/payments", message)
    return redirect("/reserves", "Payment linked; funded and paid amounts have been updated.")
