from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Request

from lightning.core.dates import today
from lightning.core.errors import LightningError
from lightning.core.money import ZERO

from ..web import container, redirect, render

router = APIRouter(prefix="/reserves")


def _context(request: Request, error: str = ""):
    c = container(request)
    cash = c.reporting.owned_liquid_cash(today())
    reserves = c.reserves.list_active()
    emergency = next((item for item in reserves if item["kind"] == "EMERGENCY"), None)
    last_month = date(today().year, today().month, 1) - timedelta(days=1)
    month_index = last_month.year * 12 + last_month.month - 1 - 5
    first_month = date(month_index // 12, month_index % 12 + 1, 1)
    salary_root = c.categories.get_by_code("EXP.WORK.SALARY")
    salary_total = ZERO
    if salary_root:
        for group in c.reporting.money_in_by_category(first_month, last_month):
            if group.code == salary_root.code or group.code.startswith(salary_root.code + "."):
                salary_total += group.value
    average_salary = salary_total / Decimal(6)
    salary_months = (emergency["effective_allocated"] / average_salary) if emergency and average_salary else None
    return {"reserves": [item for item in reserves if item["kind"] != "EMERGENCY"],
            "emergency": emergency, "salary_average": average_salary, "salary_months": salary_months,
            "salary_period": f"{first_month.strftime('%b %Y')}–{last_month.strftime('%b %Y')}",
            "summary": c.reserves.cash_summary(cash), "error": error,
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
                                        "PROJECT", str(form.get("due_date", "")) or None,
                                        str(form.get("recurrence", "NONE")),
                                        int(str(form.get("counterparty_id", ""))) if str(form.get("counterparty_id", "")).isdigit() else None)
            allocated = str(form.get("allocated", "")).strip()
            if allocated:
                c.reserves.allocate(reserve["id"], allocated)
    except LightningError as exc:
        return render(request, "reserves.html", status_code=400, **_context(request, exc.message))
    return redirect("/reserves", f"Created {reserve['name']}.")


@router.post("/emergency")
async def save_emergency_fund(request: Request):
    c = container(request)
    form = await request.form()
    try:
        salary_target = _context(request)["salary_average"] * 6
        reserve = c.reserves.set_emergency_fund(str(form.get("allocated", "")), salary_target)
    except LightningError as exc:
        return render(request, "reserves.html", status_code=400, **_context(request, exc.message))
    return redirect("/reserves", f"Saved Emergency Fund: {reserve['allocated']} reserved.")


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
