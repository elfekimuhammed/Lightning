from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Request

from lightning.core.dates import month_of, parse_month, today
from lightning.core.errors import LightningError, ValidationError

from ..web import container, redirect, render

router = APIRouter(prefix="/budget")


def _month(request: Request) -> str:
    month = request.query_params.get("month") or month_of(today())
    parse_month(month)
    return month


def _neighbours(month: str) -> tuple[str, str]:
    first, last = parse_month(month)
    previous = month_of(first - timedelta(days=1))
    try:
        following = month_of(last + timedelta(days=1))
    except OverflowError:
        following = month
    return previous, following


def _page(request: Request, month: str, values: dict | None = None, error: str = "", status_code: int = 200):
    c = container(request)
    view = c.budgets.month_view(month)
    prev_month, next_month = _neighbours(month)
    return render(request, "budget.html", status_code=status_code, view=view, month=month,
                  prev_month=prev_month, next_month=next_month, values=values or {}, error=error)


@router.get("")
async def budget_page(request: Request):
    try:
        month = _month(request)
    except ValidationError:
        return redirect("/budget", "That month is invalid. Use YYYY-MM, for example 2026-09.")
    return _page(request, month)


@router.post("")
async def save_budget(request: Request):
    c = container(request)
    try:
        month = _month(request)
    except ValidationError:
        return redirect("/budget", "That month is invalid. Use YYYY-MM, for example 2026-09.")
    form = await request.form()
    ids = {int(key[2:]) for key in form if key.startswith(("b_", "m_")) and key[2:].isdigit()}
    amounts = {category_id: str(form.get(f"b_{category_id}", "")) for category_id in ids}
    averages = {int(key[2:]): str(value) for key, value in form.items()
                if key.startswith("m_") and key[2:].isdigit()}
    only = bool(form.get("only_this_month"))
    try:
        changed = c.budgets.save_month(month, amounts, only_this_month=only, average_months=averages)
    except LightningError as exc:
        values = {f"b_{k}": v for k, v in amounts.items()} | {f"m_{k}": v for k, v in averages.items()}
        return _page(request, month, values=values, error=exc.message,
                     status_code=400)
    if not changed:
        return redirect(f"/budget?month={month}", "Nothing changed.")
    scope = f"for {month} only" if only else f"from {month} onward"
    return redirect(f"/budget?month={month}", f"Saved {changed} budget{'s' if changed != 1 else ''} {scope}.")
