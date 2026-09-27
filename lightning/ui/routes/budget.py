from __future__ import annotations

from datetime import timedelta
import json

from fastapi import APIRouter, Request, Response

from lightning.core.dates import month_of, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.categories.domain import Movement, Scope
from lightning.core.money import ZERO, to_decimal

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
    tracked = {line.category_id for section in view.sections for line in section.lines
               if line.direct is not None or line.average_months or line.covered}
    try:
        tracked |= set(json.loads(c.settings.get("budget_tracked_categories") or "[]"))
    except (ValueError, TypeError):
        pass
    tracked = {int(item) for item in tracked}
    first, _ = parse_month(month)
    completed_last = first - timedelta(days=1)
    completed_first = completed_last.replace(day=1)
    for _ in range(5):
        completed_first = (completed_first - timedelta(days=1)).replace(day=1)
    category_amounts = c.reporting.money_out_by_category(completed_first, completed_last)
    six_months = []
    month_end = completed_last
    for _ in range(6):
        month_first, _ = parse_month(month_of(month_end))
        six_months.append(c.reporting.money_out_by_category(month_first, month_end))
        month_end = month_first - timedelta(days=1)
    categories = c.categories.tree(Movement.OUTFLOW)
    by_id = {category.id: category for category in categories}
    children: dict[int, list[int]] = {}
    for category in categories:
        if category.parent_id:
            children.setdefault(category.parent_id, []).append(category.id)
    def category_tree_ids(category_id):
        descendants = {category_id}
        pending = [category_id]
        while pending:
            kids = children.get(pending.pop(), [])
            descendants.update(kids)
            pending.extend(kids)
        return descendants

    averages = {}
    for section in view.sections:
        for line in section.lines:
            descendants = category_tree_ids(line.category_id)
            averages[line.category_id] = float(sum(
                (sum((amounts.get(category_id, ZERO) for category_id in descendants), ZERO)
                 for amounts in six_months), ZERO) / 6)
    personal_ids = {category.id for category in categories if category.scope == Scope.PERSONAL and not category.is_root}
    personal_total = sum((amount for category_id, amount in category_amounts.items() if category_id in personal_ids), ZERO)
    threshold = to_decimal(c.settings.get("budget_track_suggestion_percent") or "20")
    suppressed = json.loads(c.settings.get("budget_suppressed_categories") or "{}")
    if isinstance(suppressed, list):
        suppressed = {str(category_id): "never" for category_id in suppressed}
    tracking_suggestions = []
    for line in (line for section in view.sections for line in section.lines
                 if line.depth > 1 and line.category_id not in tracked):
        category = by_id.get(line.category_id)
        dismissal = suppressed.get(str(line.category_id))
        if not category or category.scope != Scope.PERSONAL or dismissal in {"never", month}:
            continue
        descendants = category_tree_ids(category.id)
        spent_six = sum((category_amounts.get(category_id, ZERO) for category_id in descendants), ZERO)
        share = (spent_six / personal_total * 100) if personal_total else ZERO
        if share >= threshold and spent_six > ZERO:
            tracking_suggestions.append({"id": category.id, "name": line.name, "share": share})
    return render(request, "budget.html", status_code=status_code, view=view, month=month,
                  prev_month=prev_month, next_month=next_month, values=values or {}, error=error,
                  has_plan=has_plan, suggestions=suggestions_view,
                  tracked=tracked, averages=averages,
                  tracking_suggestions=tracking_suggestions, suggestion_threshold=threshold,
                  carryover=c.settings.get("budget_carryover_global") == "1",
                  overall_ceiling=c.settings.get("budget_overall_ceiling"), this_month=month_of(today()),
                  personal_group=next((cat.id for cat in c.categories.tree(Movement.OUTFLOW)
                                       if cat.depth == 1 and cat.scope == Scope.PERSONAL), None),
                  free_cash=c.reserves.cash_summary(c.reporting.owned_liquid_cash(today()))["free_cash"])


@router.post("/tracking")
async def update_tracking(request: Request):
    c = container(request)
    form = await request.form()
    selected = sorted(int(key[8:]) for key in form if key.startswith("trackon_") and key[8:].isdigit())
    c.settings.set("budget_tracked_categories", json.dumps(selected))
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/budget", "Tracked categories updated.")


@router.post("/suggestions")
async def budget_suggestions(request: Request):
    c = container(request)
    form = await request.form()
    try:
        category_id = int(str(form.get("category_id", "")))
        action = str(form.get("action", ""))
        month = str(form.get("month", month_of(today())))
        parse_month(month)
        if action == "track":
            selected = set(json.loads(c.settings.get("budget_tracked_categories") or "[]"))
            selected.add(category_id)
            c.settings.set("budget_tracked_categories", json.dumps(sorted(selected)))
        elif action in {"later", "never"}:
            suppressed = json.loads(c.settings.get("budget_suppressed_categories") or "{}")
            if isinstance(suppressed, list):
                suppressed = {str(item): "never" for item in suppressed}
            suppressed[str(category_id)] = "never" if action == "never" else month
            c.settings.set("budget_suppressed_categories", json.dumps(suppressed))
    except (ValueError, TypeError):
        return redirect("/budget", "Choose a valid category.")
    return redirect(f"/budget?month={month}", "Preference saved.")


@router.post("/settings")
async def budget_settings(request: Request):
    c = container(request)
    form = await request.form()
    try:
        value = to_decimal(str(form.get("suggestion_percent", "")), "suggestion_percent")
        if value < ZERO or value > 100:
            raise ValidationError("Enter a percentage from 0 to 100.")
        c.settings.set("budget_track_suggestion_percent", str(value))
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect("/budget", exc.message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/budget", "Budget settings saved.")


@router.post("/limit/{category_id:int}")
async def inline_limit(request: Request, category_id: int):
    c = container(request)
    form = await request.form()
    month = str(form.get("month", month_of(today())))
    try:
        c.budgets.set_budget(category_id, month, str(form.get("amount", "")))
        current = set(json.loads(c.settings.get("budget_tracked_categories") or "[]"))
        current.add(category_id)
        c.settings.set("budget_tracked_categories", json.dumps(sorted(current)))
    except (LightningError, ValueError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Enter a valid monthly limit."
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(message, status_code=400, media_type="text/plain")
        return redirect(f"/budget?month={month}", message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect(f"/budget?month={month}", "Limit saved.")


@router.post("/ceiling")
async def save_ceiling(request: Request):
    c = container(request)
    form = await request.form()
    amount = str(form.get("amount", "")).strip()
    try:
        if amount:
            from lightning.core.money import to_decimal
            if to_decimal(amount, "amount") < 0:
                raise ValidationError("Ceiling cannot be negative.")
        c.settings.set("budget_overall_ceiling", amount)
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect("/budget", exc.message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect("/budget", "Overall ceiling saved.")


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


@router.post("/carryover/global")
async def update_global_carryover(request: Request):
    c = container(request)
    form = await request.form()
    month = str(form.get("month", month_of(today())))
    try:
        parse_month(month)
        enabled = form.get("enabled") == "1"
        c.budgets.set_carryover(month, {category_id: enabled for category_id in c.budgets.amounts_for(month)})
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain")
        return redirect(f"/budget?month={month}", exc.message)
    c.settings.set("budget_carryover_global", "1" if enabled else "0")
    if request.headers.get("X-Requested-With") == "fetch":
        return Response("Saved", status_code=204)
    return redirect(f"/budget?month={month}", "Carryover setting updated.")
