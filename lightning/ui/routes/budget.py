from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Request

from lightning.core.dates import month_of, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.categories.domain import Movement, Scope

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
    has_plan = c.budgets.has_plan(month)
    suggestions = c.budgets.suggested_plan(month) if not has_plan else {}
    suggestions_view = {category_id: (c.categories.display_name(category_id), amount)
                        for category_id, amount in suggestions.items()}
    return render(request, "budget.html", status_code=status_code, view=view, month=month,
                  prev_month=prev_month, next_month=next_month, values=values or {}, error=error,
                  has_plan=has_plan, suggestions=suggestions_view,
                  personal_group=next((cat.id for cat in c.categories.tree(Movement.OUTFLOW)
                                       if cat.depth == 1 and cat.scope == Scope.PERSONAL), None),
                  free_cash=c.reserves.cash_summary(c.reporting.owned_liquid_cash(today()))["free_cash"])


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


@router.post("/setup")
async def accept_plan(request: Request):
    c = container(request)
    try:
        month = _month(request)
    except ValidationError:
        return redirect("/budget", "That month is invalid. Use YYYY-MM, for example 2026-09.")
    form = await request.form()
    amounts = {}
    try:
        for key, value in form.items():
            if key.startswith("suggest_") and key[8:].isdigit():
                amounts[int(key[8:])] = str(value)
        if amounts:
            c.budgets.save_month(month, amounts)
        else:
            group_id = int(str(form.get("group_id", "")))
            c.budgets.set_budget(group_id, month, str(form.get("broad_limit", "")))
    except (ValueError, LightningError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Choose a valid monthly limit."
        return _page(request, month, error=message, status_code=400)
    return redirect(f"/budget?month={month}", "Your monthly spending plan is ready. You can refine it anytime.")


@router.post("/carryover")
async def update_carryover(request: Request):
    c = container(request)
    try:
        month = _month(request)
    except ValidationError:
        return redirect("/budget", "That month is invalid. Use YYYY-MM, for example 2026-09.")
    form = await request.form()
    ids = {int(key[8:]) for key in form if key.startswith("carryon_") and key[8:].isdigit()}
    # The hidden companion includes unchecked controls so opting out is explicit.
    settings = {int(key[11:]): str(value) == "1" for key, value in form.items()
                if key.startswith("carryvalue_") and key[11:].isdigit()}
    settings.update({category_id: True for category_id in ids})
    try:
        changed = c.budgets.set_carryover(month, settings)
    except LightningError as exc:
        return redirect(f"/budget?month={month}", exc.message)
    return redirect(f"/budget?month={month}", f"Updated carryover for {changed} budget line{'s' if changed != 1 else ''}.")
