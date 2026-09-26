from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.dates import today
from lightning.core.errors import LightningError

from ..web import container, redirect, render

router = APIRouter(prefix="/reserves")


def _context(request: Request, error: str = ""):
    c = container(request)
    cash = c.reporting.owned_liquid_cash(today())
    return {"reserves": c.reserves.list_active(), "summary": c.reserves.cash_summary(cash), "error": error,
            "counterparties": c.counterparties.list_active()}


@router.get("")
async def list_reserves(request: Request):
    return render(request, "reserves.html", **_context(request))


@router.post("")
async def create_reserve(request: Request):
    c = container(request)
    form = await request.form()
    try:
        with c.db.transaction():
            reserve = c.reserves.create(str(form.get("name", "")), str(form.get("target", "")),
                                        str(form.get("kind", "PROJECT")), str(form.get("due_date", "")) or None,
                                        str(form.get("recurrence", "NONE")),
                                        int(str(form.get("counterparty_id", ""))) if str(form.get("counterparty_id", "")).isdigit() else None)
            allocated = str(form.get("allocated", "")).strip()
            if allocated:
                c.reserves.allocate(reserve["id"], allocated)
    except LightningError as exc:
        return render(request, "reserves.html", status_code=400, **_context(request, exc.message))
    return redirect("/reserves", f"Created {reserve['name']}.")


@router.post("/{reserve_id:int}/edit")
async def edit_reserve(request: Request, reserve_id: int):
    c = container(request)
    form = await request.form()
    try:
        reserve = c.reserves.update(reserve_id, str(form.get("name", "")), str(form.get("target", "")),
                                    str(form.get("due_date", "")) or None,
                                    str(form.get("recurrence", "NONE")),
                                    int(str(form.get("counterparty_id", ""))) if str(form.get("counterparty_id", "")).isdigit() else None)
    except LightningError as exc:
        return redirect("/reserves", exc.message)
    return redirect("/reserves", f"Saved {reserve['name']}.")


@router.post("/{reserve_id:int}/allocate")
async def allocate_reserve(request: Request, reserve_id: int):
    c = container(request)
    form = await request.form()
    try:
        reserve = c.reserves.allocate(reserve_id, str(form.get("allocated", "")))
    except LightningError as exc:
        return redirect("/reserves", exc.message)
    return redirect("/reserves", f"Updated cash assigned to {reserve['name']}.")


@router.post("/{reserve_id:int}/complete")
async def complete_reserve(request: Request, reserve_id: int):
    try:
        reserve = container(request).reserves.complete(reserve_id)
    except LightningError as exc:
        return redirect("/reserves", exc.message)
    return redirect("/reserves", f"Completed {reserve['name']}; its assigned cash is free again.")
