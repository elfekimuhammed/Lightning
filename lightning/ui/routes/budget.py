from __future__ import annotations

from datetime import timedelta
from datetime import date
from decimal import Decimal
import json
import uuid

from fastapi import APIRouter, Request, Response

from lightning.core.dates import month_of, parse_month, today
from lightning.core.errors import LightningError, ValidationError
from lightning.categories.domain import CategoryFamily, Movement, Scope
from lightning.core.money import ZERO, to_decimal

from ..web import container, redirect, render
from ..periods import parse_period

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
    earliest = c.budgets.first_owned_spending_date()
    try:
        period = parse_period(request.query_params, today(), earliest)
    except ValidationError:
        period = parse_period({"period": "month", "month": month}, today())
    month = period.end.strftime("%Y-%m")
    view = c.budgets.month_view(month)
    cursor = period.start.replace(day=1)
    month_views = []
    while cursor <= period.end:
        key = cursor.strftime("%Y-%m")
        month_views.append((key, c.budgets.month_view(key)))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    period_base = ZERO
    period_opening = ZERO
    period_carryover = ZERO
    if month_views:
        period_opening = month_views[0][1].available - month_views[0][1].budget
        period_carryover = period_opening
        if period.key == "custom":
            first_month = parse_month(month_views[0][0])
            overlap_start, overlap_end = max(first_month[0], period.start), min(first_month[1], period.end)
            opening_factor = Decimal((overlap_end-overlap_start).days+1) / Decimal((first_month[1]-first_month[0]).days+1)
            period_opening *= opening_factor
            period_carryover *= opening_factor
    period_budgeted = period_base + period_opening
    group_totals = {}
    for _, month_view in month_views:
        m_first, m_last = parse_month(month_view.month)
        overlap_start, overlap_end = max(m_first, period.start), min(m_last, period.end)
        # A monthly plan is a full-month limit even when today's activity ends mid-month.
        factor = (Decimal(1) if period.key == "month" else
                  Decimal((overlap_end-overlap_start).days+1) / Decimal((m_last-m_first).days+1)
                  if overlap_end >= overlap_start else ZERO)
        period_base += month_view.budget * factor
        for section in month_view.sections:
            for group in section.groups:
                row = group_totals.setdefault(group.category_id, {"name": group.name, "section": section.name,
                    "budgeted": ZERO, "carryover": ZERO, "spent": ZERO, "left": ZERO})
                row["budgeted"] += (group.budget or ZERO) * factor
                if month_views and month_view.month == month_views[0][0]:
                    row["budgeted"] += group.opening_carryover * factor
                    row["carryover"] += group.opening_carryover * factor
    for row in group_totals.values():
        row["left"] = row["budgeted"] - row["spent"]
    if period.key == "month":
        for section in view.sections:
            for group in section.groups:
                row = group_totals.get(group.category_id)
                if row:
                    row["budgeted"] = group.available or ZERO
                    row["carryover"] = group.opening_carryover
                    row["left"] = row["budgeted"] - row["spent"]
        # Keep the headline aligned with the L1 group rows, including carryover.
        period_budgeted = sum((row["budgeted"] for row in group_totals.values()), ZERO)
    prev_month, next_month = _neighbours(month)
    has_plan = c.budgets.has_plan(month)
    suggestions = c.budgets.suggested_plan(month) if not has_plan else {}
    suggestions_view = {category_id: (c.categories.display_name(category_id), amount)
                        for category_id, amount in suggestions.items()}
    tracked = {line.category_id for section in view.sections for line in section.lines
               if line.direct is not None or line.average_months or line.income_percent is not None}
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
    category_amounts = c.budgets._owned_spending(completed_first, completed_last)
    six_months = []
    month_end = completed_last
    for _ in range(6):
        month_first, _ = parse_month(month_of(month_end))
        six_months.append(c.budgets._owned_spending(month_first, month_end))
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

    averages = {}; averages6 = {}; average_observations = {}; average_observations6 = {}
    for section in view.sections:
        for line in section.lines:
            descendants = category_tree_ids(line.category_id)
            observed3 = [sum((amounts.get(category_id, ZERO) for category_id in descendants), ZERO)
                         for amounts in six_months[:3] if any(category_id in amounts for category_id in descendants)]
            observed6 = [sum((amounts.get(category_id, ZERO) for category_id in descendants), ZERO)
                         for amounts in six_months if any(category_id in amounts for category_id in descendants)]
            observed = observed3
            averages[line.category_id] = (sum(observed, ZERO) / len(observed)).quantize(Decimal("0.01")) if observed else None
            averages6[line.category_id] = (sum(observed6, ZERO) / len(observed6)).quantize(Decimal("0.01")) if observed6 else None
            average_observations[line.category_id] = len(observed3)
            average_observations6[line.category_id] = len(observed6)
    by_group = {}
    for section in view.sections:
        for group in section.groups:
            by_group[group.category_id] = sorted(category_tree_ids(group.category_id) - {group.category_id})
    background_counts, background_totals = {}, {}
    for group_id, child_ids in by_group.items():
        untracked_lines = [line for section in view.sections for line in section.lines
                           if line.category_id in child_ids and line.category_id not in tracked]
        background_counts[group_id] = len(untracked_lines)
        background_totals[group_id] = sum((averages.get(line.category_id) or ZERO for line in untracked_lines), ZERO)
    income_basis = c.budgets.budgeting_income(month)
    threshold_raw = c.settings.get("budget_track_suggestion_percent")
    threshold = to_decimal(threshold_raw, "suggestion_percent") if threshold_raw else None
    fixed_threshold = to_decimal(c.settings.get("budget_track_suggestion_fixed") or "0")
    try:
        raw_exclusions = c.settings.get("budget_one_off_exclusions") or "[]"
        exclusions = {int(x) for x in json.loads(raw_exclusions)} if raw_exclusions.strip().startswith("[") else set()
    except (ValueError, TypeError):
        exclusions = set()
    background_counts, background_totals = {}, {}
    for group_id, child_ids in by_group.items():
        background = [line for section in view.sections for line in section.lines
                      if line.category_id in child_ids and line.category_id not in tracked and not line.covered
                      and not children.get(line.category_id) and line.category_id not in exclusions]
        background_counts[group_id] = len(background)
        background_totals[group_id] = sum((averages.get(line.category_id) or ZERO for line in background), ZERO)
    suppressed = json.loads(c.settings.get("budget_suppressed_categories") or "{}")
    if isinstance(suppressed, list):
        suppressed = {str(category_id): "never" for category_id in suppressed}
    tracking_suggestions = []
    for line in (line for section in view.sections for line in section.lines
                 if line.depth > 1 and line.category_id not in tracked):
        category = by_id.get(line.category_id)
        dismissal = suppressed.get(str(line.category_id))
        if not category or dismissal in {"never", month}:
            continue
        descendants = category_tree_ids(category.id)
        spent_six = sum((amounts.get(category_id, ZERO) for amounts in six_months
                         for category_id in descendants), ZERO)
        if category.id in exclusions:
            continue
        observed_count = sum(1 for amounts in six_months if any(cid in amounts for cid in descendants))
        monthly_average = (spent_six / observed_count).quantize(Decimal("0.01")) if observed_count else None
        share = (monthly_average / income_basis * 100) if income_basis and monthly_average is not None else ZERO
        crossed_percent = threshold is not None and income_basis is not None and monthly_average is not None and share >= threshold
        crossed_fixed = fixed_threshold > ZERO and monthly_average is not None and monthly_average >= fixed_threshold
        if (crossed_percent or crossed_fixed) and spent_six > ZERO:
            parent = category
            while parent.depth > 1 and parent.parent_id and by_id.get(parent.parent_id):
                parent = by_id[parent.parent_id]
            group_id = parent.id
            tracking_suggestions.append({"id": category.id, "name": line.name, "share": share,
                                         "group_id": group_id, "spent": spent_six,
                                         "reason": (f"{share:.1f}% of budgeting income" if crossed_percent else
                                                    f"Average {monthly_average:,.2f} EGP crossed fixed threshold")})

    # Background estimates are monthly expectations for untracked leaf
    # categories. Parent direct plans already cap these expenses, so children
    # under those caps are not added a second time.
    for _, month_view in month_views:
        m_first, m_last = parse_month(month_view.month)
        overlap_start, overlap_end = max(m_first, period.start), min(m_last, period.end)
        # A monthly plan is a full-month limit even when today's activity ends mid-month.
        factor = (Decimal(1) if period.key == "month" else
                  Decimal((overlap_end-overlap_start).days+1) / Decimal((m_last-m_first).days+1)
                  if overlap_end >= overlap_start else ZERO)
        for section in month_view.sections:
            for line in section.lines:
                if (line.depth <= 1 or line.category_id in tracked or line.covered or children.get(line.category_id)
                        or line.category_id in exclusions):
                    continue
                estimate = c.budgets._rolling_average(line.category_id, month_view.month, 3, children, {})
                if estimate is None:
                    continue
                parent = by_id.get(line.category_id)
                while parent and parent.depth > 1 and parent.parent_id:
                    parent = by_id.get(parent.parent_id)
                group_id = parent.id if parent else None
                if group_id in group_totals:
                    group_totals[group_id]["budgeted"] += estimate * factor
                    period_base += estimate * factor
    period_budgeted = period_base + period_opening
    period_spending = c.budgets._owned_spending(period.start, period.end)
    period_actual = sum(period_spending.values(), ZERO)
    category_periods = {}
    for _, month_view in month_views:
        m_first, m_last = parse_month(month_view.month)
        overlap_start, overlap_end = max(m_first, period.start), min(m_last, period.end)
        # A monthly plan is a full-month limit even when today's activity ends mid-month.
        factor = (Decimal(1) if period.key == "month" else
                  Decimal((overlap_end-overlap_start).days+1) / Decimal((m_last-m_first).days+1)
                  if overlap_end >= overlap_start else ZERO)
        for section in month_view.sections:
            for line in section.lines:
                if line.depth <= 1:
                    continue
                row = category_periods.setdefault(line.category_id, {
                    "base_budget": ZERO, "carryover": ZERO, "current_budget": ZERO,
                    "budgeted": ZERO, "spent": ZERO,
                })
                row["base_budget"] += (line.budget or ZERO) * factor
                if month_views and month_view.month == month_views[0][0]:
                    row["carryover"] += line.opening_carryover * factor
    for category_id, row in category_periods.items():
        row["current_budget"] = row["base_budget"] + row["carryover"]
        row["budgeted"] = row["current_budget"]
        row["spent"] = sum((period_spending.get(cid, ZERO) for cid in category_tree_ids(category_id)), ZERO)
        row["left"] = row["current_budget"] - row["spent"]
    for group_id, child_ids in by_group.items():
        row = group_totals.get(group_id)
        if row:
            row["spent"] = sum((period_spending.get(cid, ZERO) for cid in child_ids), ZERO)
            row["left"] = row["budgeted"] - row["spent"]
    period_income = ZERO
    for key, _ in month_views:
        basis = c.budgets.budgeting_income(key) or ZERO
        m_first, m_last = parse_month(key)
        overlap_start, overlap_end = max(m_first, period.start), min(m_last, period.end)
        # A monthly plan is a full-month limit even when today's activity ends mid-month.
        factor = (Decimal(1) if period.key == "month" else
                  Decimal((overlap_end-overlap_start).days+1) / Decimal((m_last-m_first).days+1)
                  if overlap_end >= overlap_start else ZERO)
        period_income += basis * factor
    ceiling_percent = to_decimal(c.settings.get("budget_monthly_ceiling_percent") or "100")
    ceiling = period_income * ceiling_percent / Decimal(100)
    ceiling_warning = ("" if period_income <= ZERO else
                       "Planned amounts exceed 100% of budgeting income" if period_base > period_income else
                       f"Base plan exceeds the {ceiling_percent}% monthly spending ceiling" if period_base > ceiling else "")
    period_left = period_budgeted-period_actual
    group_rows = sorted(group_totals.items(),
                        key=lambda item: (item[1]["left"] >= ZERO, -item[1]["spent"], item[1]["name"].casefold()))
    unplanned_spending = period_actual - sum((row["spent"] for row in group_totals.values()), ZERO)
    plan_outside_groups = period_budgeted - sum((row["budgeted"] for row in group_totals.values()), ZERO)
    grouped_category_ids = {category_id for child_ids in by_group.values() for category_id in child_ids}
    outside_spending_rows = sorted(({"id": category_id, "name": c.categories.display_name(category_id),
                                    "amount": amount}
                                   for category_id, amount in period_spending.items()
                                   if category_id not in grouped_category_ids and amount != ZERO),
                                  key=lambda row: -abs(row["amount"]))
    bulk_undo = None
    token = str(request.query_params.get("undo", ""))
    if token:
        try:
            snapshot = json.loads(c.settings.get("budget_bulk_undo") or "{}")
            if snapshot.get("token") == token and snapshot.get("month") == month:
                bulk_undo = token
        except (ValueError, TypeError):
            pass
    return render(request, "budget.html", status_code=status_code, view=view, month=month,
                  prev_month=prev_month, next_month=next_month, values=values or {}, error=error,
                  has_plan=has_plan, suggestions=suggestions_view,
                  tracked=tracked, averages=averages,
                  averages6=averages6, average_observations=average_observations,
                  average_observations6=average_observations6,
                  tracking_suggestions=tracking_suggestions, suggestion_threshold=threshold,
                  carryover=c.settings.get("budget_carryover_global") == "1",
                  overall_ceiling=c.settings.get("budget_overall_ceiling"), this_month=month_of(today()),
                  personal_group=next((cat.id for cat in c.categories.tree(Movement.OUTFLOW)
                                       if cat.depth == 1 and cat.scope == Scope.PERSONAL), None),
                  free_cash=c.reserves.cash_summary(c.reporting.owned_liquid_cash(today()), c.planning.what_you_owe().bills_due)["free_cash"],
                  period=period, period_actual=period_actual, period_budgeted=period_budgeted,
                  period_left=period_left, period_carryover=period_carryover, group_totals=group_totals,
                  group_rows=group_rows,
                  unplanned_spending=unplanned_spending, plan_outside_groups=plan_outside_groups,
                  outside_spending_rows=outside_spending_rows, base=c.reporting.base_currency,
                  by_group=by_group, background_counts=background_counts, background_totals=background_totals,
                  period_income=period_income, ceiling_warning=ceiling_warning,
                  monthly_income_basis=income_basis,
                  category_periods=category_periods,
                  bulk_undo=bulk_undo,
                  effective_month=month, previous_month=_neighbours(month)[0],
                  previous_bridge=c.budgets.month_view(_neighbours(month)[0]))


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
            c.budgets.set_budget(category_id, month, "", average_months=3)
        elif action in {"later", "never"}:
            suppressed = json.loads(c.settings.get("budget_suppressed_categories") or "{}")
            if isinstance(suppressed, list):
                suppressed = {str(item): "never" for item in suppressed}
            suppressed[str(category_id)] = "never" if action == "never" else month
            c.settings.set("budget_suppressed_categories", json.dumps(suppressed))
    except (ValueError, TypeError):
        return redirect("/budget", "Choose a valid category.")
    return redirect(f"/budget?month={month}", "Preference saved.")


@router.post("/one-off")
async def mark_budget_one_off(request: Request):
    c = container(request); form = await request.form()
    try:
        category_id = int(str(form.get("category_id", "")))
        month = str(form.get("month", month_of(today()))); parse_month(month)
        c.budgets._budgetable(category_id)
        excluded = {int(x) for x in json.loads(c.settings.get("budget_one_off_exclusions") or "[]")}
        excluded.add(category_id)
        c.settings.set("budget_one_off_exclusions", json.dumps(sorted(excluded)))
    except (ValueError, TypeError, LightningError) as exc:
        return redirect("/budget", exc.message if isinstance(exc, LightningError) else "Choose a valid category.")
    return redirect(f"/budget?period=month&month={month}", "Category excluded from background estimates.")


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


def _budget_return_to(raw: str | None) -> str:
    value = str(raw or "")
    if not (value.startswith("/budget") or value.startswith("/settings")) or value.startswith("//") or "\\" in value:
        return "/budget"
    try:
        from urllib.parse import urlsplit, parse_qs
        parts = urlsplit(value)
        if parts.netloc or parts.scheme or not (parts.path == "/budget" or parts.path.startswith("/budget/")):
            return "/budget"
        if parts.query:
            parse_period({key: values[-1] for key, values in parse_qs(parts.query).items()}, today())
    except (ValueError, ValidationError):
        return "/budget"
    return value


@router.get("/settings")
async def budget_settings_page(request: Request):
    return redirect("/settings?section=budget&return_to=%2Fbudget")
    c = container(request)
    c = container(request)
    categories = [x for x in c.categories.tree() if not x.is_root and x.movement == Movement.INFLOW
                  and x.income_class is not None and x.code != "EXP.INVEST"
                  and not any(word in x.code.casefold() for word in ("sale", "opening", "valuation"))]
    expense_categories = [x for x in c.categories.tree(Movement.OUTFLOW) if not x.is_root]
    raw_selected = c.settings.get("budget_income_categories")
    try:
        selected = {int(x) for x in json.loads(raw_selected)} if raw_selected is not None else {
            x.id for x in categories if x.family == CategoryFamily.WORK or
            any(w in x.name.casefold() for w in ("salary", "pay", "wage"))}
    except (ValueError, TypeError):
        selected = set()
    try:
        excluded = {int(x) for x in json.loads(c.settings.get("budget_one_off_exclusions") or "[]")}
    except (ValueError, TypeError):
        excluded = set()
    return render(request, "budget_settings.html", income_categories=categories, selected_income=selected,
                  expense_categories=expense_categories, excluded_categories=excluded,
                  return_to=_budget_return_to(request.query_params.get("return_to")),
                  carryover=c.settings.get("budget_carryover_global") == "1",
                  carryover_month=c.settings.get("budget_carryover_month") or month_of(today()),
                  income_months=c.settings.get("budget_income_months") or "3",
                  manual_income=c.settings.get("budget_manual_monthly_income") or "",
                  suggestion_percent=(c.settings.get("budget_track_suggestion_percent")
                                      if c.settings.get("budget_track_suggestion_percent") is not None else "20"),
                  suggestion_fixed=c.settings.get("budget_track_suggestion_fixed") or "",
                  ceiling_percent=c.settings.get("budget_monthly_ceiling_percent") or "100",
                  exclusions=c.settings.get("budget_one_off_exclusions") or "")


@router.post("/settings/full")
async def save_budget_settings(request: Request):
    c = container(request); form = await request.form()
    return_to = _budget_return_to(str(form.get("return_to", "")))
    try:
        income_months = str(form.get("income_months", "3"))
        if income_months not in {"3", "6"}:
            raise ValidationError("Income basis must use three or six completed months.")
        for key, label, upper in (("ceiling_percent", "Monthly spending ceiling", 10000),):
            number = to_decimal(str(form.get(key, "")), key)
            if number < ZERO or number > upper:
                raise ValidationError(f"{label} must be between 0 and {upper}.")
        suggestion_percent = str(form.get("suggestion_percent", "")).strip()
        if suggestion_percent:
            value = to_decimal(suggestion_percent, "suggestion_percent")
            if value < ZERO or value > 100:
                raise ValidationError("Suggestion percentage must be between 0 and 100.")
        manual = str(form.get("manual_income", "")).strip()
        if manual and to_decimal(manual, "manual_income") < ZERO:
            raise ValidationError("Manual monthly income cannot be negative.")
        fixed = str(form.get("suggestion_fixed", "")).strip()
        if fixed and to_decimal(fixed, "suggestion_fixed") < ZERO:
            raise ValidationError("Fixed suggestion threshold cannot be negative.")
        enabled = form.get("carryover") == "1"
        carry_month = str(form.get("carryover_month", month_of(today())))
        parse_month(carry_month)
        categories = [int(x) for x in form.getlist("income_category") if str(x).isdigit()]
        exclusions = [int(x) for x in form.getlist("exclusion_category") if str(x).isdigit()]
        c.settings.set("budget_income_categories", json.dumps(sorted(set(categories))))
        c.settings.set("budget_income_months", income_months)
        c.settings.set("budget_manual_monthly_income", manual)
        c.settings.set("budget_track_suggestion_percent", suggestion_percent)
        c.settings.set("budget_track_suggestion_fixed", fixed)
        c.settings.set("budget_monthly_ceiling_percent", str(to_decimal(form.get("ceiling_percent"), "ceiling_percent")))
        c.settings.set("budget_one_off_exclusions", json.dumps(sorted(set(exclusions))))
        c.settings.set("budget_carryover_global", "1" if enabled else "0")
        c.settings.set("budget_carryover_month", carry_month)
        tracked = set(c.budgets.amounts_for(carry_month))
        c.budgets.set_carryover(carry_month, {category_id: enabled for category_id in tracked})
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(status_code=204)
    except (LightningError, ValueError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Check the entered values."
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(message, status_code=400, media_type="text/plain")
        categories = [x for x in c.categories.tree() if not x.is_root and x.movement == Movement.INFLOW
                      and x.income_class is not None and x.code != "EXP.INVEST"
                      and not any(word in x.code.casefold() for word in ("sale", "opening", "valuation"))]
        expense_categories = [x for x in c.categories.tree(Movement.OUTFLOW) if not x.is_root]
        return render(request, "budget_settings.html", status_code=400, error=message,
                      income_categories=categories, expense_categories=expense_categories,
                      selected_income={int(x) for x in form.getlist("income_category") if str(x).isdigit()},
                      excluded_categories={int(x) for x in form.getlist("exclusion_category") if str(x).isdigit()}, return_to=return_to,
                      carryover=form.get("carryover")=="1", carryover_month=str(form.get("carryover_month", "")),
                      income_months=str(form.get("income_months", "3")), manual_income=str(form.get("manual_income", "")),
                      suggestion_percent=str(form.get("suggestion_percent", "20")),
                      suggestion_fixed=str(form.get("suggestion_fixed", "")),
                      ceiling_percent=str(form.get("ceiling_percent", "100")))
    return redirect(return_to, "Budget settings updated.")


@router.get("/carryover/reset/{category_id:int}")
async def carryover_reset_popup(request: Request, category_id: int):
    c = container(request); month = str(request.query_params.get("month", month_of(today())))
    try:
        parse_month(month)
    except ValidationError as exc:
        return redirect("/budget", exc.message)
    category = c.categories.get(category_id)
    line = next((line for section in c.budgets.month_view(month).sections for line in section.lines
                 if line.category_id == category_id), None)
    if line is None:
        return redirect(f"/budget?month={month}", "This category has no active budget in that month.")
    return render(request, "budget_reset_popup.html", category=category, month=month, amount=line.opening_carryover)


@router.get("/carryover-bridge")
async def carryover_bridge(request: Request):
    c = container(request); month = str(request.query_params.get("month", month_of(today())))
    try:
        parse_month(month)
    except ValidationError as exc:
        return redirect("/budget", exc.message)
    previous, _ = _neighbours(month)
    prior_view = c.budgets.month_view(previous); current_view = c.budgets.month_view(month)
    prior = {line.category_id: line for section in prior_view.sections for line in section.lines}
    current = {line.category_id: line for section in current_view.sections for line in section.lines}
    categories = []
    for category_id in sorted(set(prior) | set(current)):
        before, after = prior.get(category_id), current.get(category_id)
        if not after or not after.carryover_enabled:
            continue
        categories.append({"name": after.name, "prior_budget": before.available if before else ZERO,
                          "prior_spent": before.actual if before else ZERO,
                          "incoming": after.opening_carryover,
                          "base": after.budget or ZERO,
                          "current": after.available or ZERO})
    return render(request, "budget_bridge.html", month=month, previous=previous, categories=categories)


@router.post("/carryover/reset/{category_id:int}")
async def reset_carryover(request: Request, category_id: int):
    c = container(request); form = await request.form(); month = str(form.get("month", month_of(today())))
    try:
        c.budgets.reset_carryover(category_id, month)
    except LightningError as exc:
        return redirect(f"/budget?month={month}", exc.message)
    return redirect(f"/budget?month={month}", "Carryover reset from this month.")


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


@router.post("/percentage/{category_id:int}")
async def inline_percentage(request: Request, category_id: int):
    c = container(request); form = await request.form()
    month = str(form.get("month", month_of(today())))
    try:
        raw = str(form.get("percentage", "")).strip()
        if raw:
            c.budgets.set_income_percentage(category_id, month, raw)
        else:
            c.budgets.set_budget(category_id, month, "")
        current = set(json.loads(c.settings.get("budget_tracked_categories") or "[]")); current.add(category_id)
        c.settings.set("budget_tracked_categories", json.dumps(sorted(current)))
    except (LightningError, ValueError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Enter a valid percentage."
        return Response(message, status_code=400, media_type="text/plain") if request.headers.get("X-Requested-With")=="fetch" else redirect(f"/budget?month={month}", message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response(status_code=204)
    return redirect(f"/budget?month={month}", "Income percentage saved.")


@router.post("/bulk")
async def bulk_budget_rule(request: Request):
    c = container(request); form = await request.form()
    month = str(form.get("month", month_of(today())))
    selected = sorted({int(x) for x in form.getlist("category_id") if str(x).isdigit()})
    action = str(form.get("action", ""))
    if not selected:
        return redirect(f"/budget?period=month&month={month}", "Select at least one category.")
    if action not in {"percentage", "average3", "average6"}:
        return redirect(f"/budget?period=month&month={month}", "Choose a bulk rule.")
    # Store the exact affected rows so the immediate result can be undone.
    before = c.budgets.snapshot_rows(selected)
    token = uuid.uuid4().hex
    try:
        with c.db.transaction():
            if action == "percentage":
                percentage = form.get("percentage", "")
                for category_id in selected:
                    c.budgets.set_income_percentage(category_id, month, percentage)
            else:
                period = 3 if action == "average3" else 6
                c.budgets.save_month(month, {category_id: "" for category_id in selected},
                                     average_months={category_id: period for category_id in selected})
        c.settings.set("budget_bulk_undo", json.dumps({"token": token, "month": month,
            "category_ids": selected, "rows": before}))
    except LightningError as exc:
        return redirect(f"/budget?period=month&month={month}", exc.message)
    return redirect(f"/budget?period=month&month={month}&undo={token}", f"Updated {len(selected)} categories.")


@router.post("/bulk/undo")
async def undo_bulk_budget_rule(request: Request):
    c = container(request); form = await request.form(); token = str(form.get("token", ""))
    try:
        snapshot = json.loads(c.settings.get("budget_bulk_undo") or "{}")
        if not token or token != snapshot.get("token"):
            raise ValidationError("This bulk change can no longer be undone.")
        ids = [int(x) for x in snapshot["category_ids"]]
        rows = snapshot["rows"]
        c.budgets.restore_rows(ids, rows)
        c.settings.set("budget_bulk_undo", "")
        return redirect(f"/budget?period=month&month={snapshot['month']}", "Bulk change undone.")
    except (LightningError, ValueError, KeyError, TypeError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Undo is unavailable."
        return redirect("/budget", message)


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
