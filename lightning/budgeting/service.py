"""Public API of the budgeting module: the month view (budget vs actual) and saving budgets."""

from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from lightning.categories.domain import Category, Movement, Scope
from lightning.categories.service import CategoryService
from lightning.core.dates import month_of, parse_month
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, check_places, fmt, to_decimal
from lightning.database.connection import Database
from lightning.reporting.service import ReportingService

from .domain import BudgetLine, BudgetMonth, BudgetSection
from .repository import BudgetRepository

SECTION_NAMES = {Scope.PERSONAL: "Personal", Scope.WORK: "Work"}


class BudgetService:
    def __init__(self, db: Database, categories: CategoryService, reporting: ReportingService):
        self.db = db
        self.repo = BudgetRepository(db)
        self.categories = categories
        self.reporting = reporting

    # ------------------------------------------------------------------ reading
    def amounts_for(self, month: str) -> dict[int, tuple[Decimal | None, bool, int | None]]:
        """Configured amount, one-off flag, and optional rolling-average period by category."""
        parse_month(month)
        repeating: dict[int, tuple[Decimal | None, int | None]] = {}
        one_off: dict[int, tuple[Decimal | None, int | None]] = {}
        for e in self.repo.entries_up_to(month):  # ordered by category, month
            if e.one_off:
                one_off[e.category_id] = (e.amount, e.average_months)
            else:
                repeating[e.category_id] = (e.amount, e.average_months)
        result = {cid: (amount, False, period) for cid, (amount, period) in repeating.items()}
        result.update({cid: (amount, True, period) for cid, (amount, period) in one_off.items()})
        return {cid: v for cid, v in result.items() if v[0] is not None or v[2] is not None}

    def has_plan(self, month: str) -> bool:
        return bool(self.amounts_for(month))

    def month_view(self, month: str) -> BudgetMonth:
        first, last = parse_month(month)
        direct = self.amounts_for(month)
        spent = self.reporting.money_out_by_category(first, last)
        cats = [c for c in self.categories.tree(Movement.OUTFLOW) if not c.is_root]
        by_id = {c.id: c for c in cats}
        children: dict[int, list[int]] = {}
        for c in cats:
            if c.parent_id in by_id:
                children.setdefault(c.parent_id, []).append(c.id)

        actual: dict[int, Decimal] = {}
        budget: dict[int, Decimal | None] = {}
        average_cache: dict[tuple[int, int], Decimal] = {}
        for c in reversed(cats):  # children before parents
            kids = children.get(c.id, [])
            actual[c.id] = spent.get(c.id, ZERO) + sum((actual[k] for k in kids), ZERO)
            if c.id in direct:
                amount, _, period = direct[c.id]
                if period:
                    amount = self._rolling_average(c.id, month, period, children, average_cache)
                budget[c.id] = amount
            else:
                kid_budgets = [budget[k] for k in kids if budget[k] is not None]
                budget[c.id] = sum(kid_budgets, ZERO) if kid_budgets else None

        def ancestor_has_direct(c: Category) -> bool:
            parent = by_id.get(c.parent_id)
            while parent is not None:
                if parent.id in direct:
                    return True
                parent = by_id.get(parent.parent_id)
            return False

        sections = {scope: BudgetSection(name) for scope, name in SECTION_NAMES.items()}
        warnings: list[str] = []
        carryover_settings = self.repo.carryover_settings(month)
        opening_carryovers = {category_id: self._opening_carryover(category_id, month,
                                                                    carryover_settings.get(category_id, False) and category_id in direct,
                                                                    children)
                              for category_id in carryover_settings if carryover_settings[category_id]}
        for category in reversed(cats):
            if category.id not in direct:
                opening_carryovers[category.id] = sum(
                    (opening_carryovers.get(child_id, ZERO) for child_id in children.get(category.id, [])), ZERO)
        for c in cats:
            section = sections[c.scope or Scope.PERSONAL]
            covered = ancestor_has_direct(c)
            if c.id not in direct and not covered:
                section.unbudgeted += spent.get(c.id, ZERO)
            shows = c.active or actual[c.id] != ZERO or c.id in direct
            if c.is_system and actual[c.id] == ZERO and c.id not in direct:
                shows = False
            if not shows:
                continue
            amount, one_off, average_months = direct.get(c.id, (None, False, None))
            section.lines.append(BudgetLine(
                category_id=c.id, code=c.code, name=c.name, depth=c.depth, direct=amount, one_off=one_off,
                average_months=average_months, budget=budget[c.id], actual=actual[c.id], covered=covered,
                opening_carryover=opening_carryovers.get(c.id, ZERO),
                carryover_enabled=carryover_settings.get(c.id, False),
            ))
            kids_total = sum(((budget[k] or ZERO) + opening_carryovers.get(k, ZERO)
                              for k in children.get(c.id, []) if budget[k] is not None), ZERO)
            parent_available = (budget[c.id] or ZERO) + opening_carryovers.get(c.id, ZERO)
            if budget[c.id] is not None and kids_total > parent_available:
                warnings.append(f"{self.categories.display_name(c.id)}: its categories add up to "
                                f"{fmt(kids_total)}, more than its budget / available limit of {fmt(parent_available)}.")
        income = self.reporting.cash_flow(first, last).inflows
        return BudgetMonth(month, [s for s in sections.values() if s.lines], income, warnings)

    def suggested_plan(self, month: str) -> dict[int, Decimal]:
        """Return stable, rounded suggestions for categories with recent spending."""
        parse_month(month)
        cats = [c for c in self.categories.tree(Movement.OUTFLOW) if not c.is_root]
        children: dict[int, list[int]] = {}
        by_id = {c.id: c for c in cats}
        for category in cats:
            if category.parent_id in by_id:
                children.setdefault(category.parent_id, []).append(category.id)
        cache: dict[tuple[int, int], Decimal] = {}
        result = {}
        for category in cats:
            if children.get(category.id):
                continue
            avg = self._rolling_average(category.id, month, 3, children, cache)
            if avg > ZERO:
                result[category.id] = avg
        return result

    def set_carryover(self, month: str, settings: dict[int, bool]) -> int:
        parse_month(month)
        changed = 0
        current = self.repo.carryover_settings(month)
        with self.db.transaction():
            for category_id, enabled in settings.items():
                self._budgetable(category_id)
                if enabled and category_id not in self.amounts_for(month):
                    raise ValidationError("Carryover needs a monthly limit on that category or group first.")
                if current.get(category_id, False) == enabled:
                    continue
                self.repo.set_carryover(category_id, month, enabled)
                changed += 1
        return changed

    def _opening_carryover(self, category_id: int, month: str, enabled_now: bool,
                           children: dict[int, list[int]]) -> Decimal:
        if not enabled_now:
            return ZERO
        first, _ = parse_month(month)
        earliest = self.repo.first_carryover_month(category_id, month)
        if not earliest:
            return ZERO
        cursor = parse_month(earliest)[0]
        settings = self.repo.carryover_settings_up_to(month, category_id)
        active = False
        setting_index = 0
        balance = ZERO
        descendants = {category_id}
        pending = [category_id]
        while pending:
            kids = children.get(pending.pop(), [])
            descendants.update(kids)
            pending.extend(kids)
        while cursor < first:
            current_month = month_of(cursor)
            while setting_index < len(settings) and settings[setting_index][0] <= current_month:
                active = settings[setting_index][1]
                setting_index += 1
            next_cursor = (parse_month(current_month)[1] + timedelta(days=1))
            if active:
                direct = self.amounts_for(current_month).get(category_id)
                if direct:
                    amount, _, period = direct
                    if period:
                        amount = self._rolling_average(category_id, current_month, period, children, {})
                    start, end = parse_month(current_month)
                    spent = self.reporting.money_out_by_category(start, end)
                    actual = sum((spent.get(cid, ZERO) for cid in descendants), ZERO)
                    balance = max(ZERO, (amount or ZERO) + balance - actual)
                else:
                    balance = ZERO
            else:
                balance = ZERO
            cursor = next_cursor
        return balance

    # ------------------------------------------------------------------ writing
    def set_budget(self, category_id: int, month: str, amount: object, only_this_month: bool = False,
                   average_months: int | None = None) -> bool:
        return self.save_month(month, {category_id: amount}, only_this_month,
                               {category_id: average_months} if average_months else None) > 0

    def save_month(self, month: str, amounts: dict[int, object], only_this_month: bool = False,
                   average_months: dict[int, object] | None = None) -> int:
        """Save several budget cells at once (the budget page). Returns how many changed."""
        parse_month(month)
        current = self.amounts_for(month)
        average_months = average_months or {}
        changed = 0
        carryover_now = self.repo.carryover_settings(month)
        with self.db.transaction():
            for category_id, raw in amounts.items():
                category = self._budgetable(category_id)
                period = self._average_period(average_months.get(category_id))
                value = None if period else self._parse(raw, category)
                old = current.get(category_id, (None, False, None))
                if old[0] == value and old[2] == period:
                    continue
                before = self._repeating_before(category_id, month)
                desired = (value, period)
                if only_this_month:
                    if desired == self._repeating_through(category_id, month):
                        self.repo.delete(category_id, month, one_off=True)
                    else:
                        self.repo.upsert(category_id, month, True, value, period)
                else:
                    self.repo.delete(category_id, month, one_off=True)
                    if desired == before:
                        self.repo.delete(category_id, month, one_off=False)  # same as before: nothing to store
                    else:
                        self.repo.upsert(category_id, month, False, value, period)
                if value is None and period is None and carryover_now.get(category_id, False):
                    self.repo.set_carryover(category_id, month, False)
                changed += 1
        return changed

    # ------------------------------------------------------------------ helpers
    def _repeating_before(self, category_id: int, month: str) -> tuple[Decimal | None, int | None]:
        rows = [e for e in self.repo.entries_up_to(month) if e.category_id == category_id and not e.one_off
                and e.month < month]
        return (rows[-1].amount, rows[-1].average_months) if rows else (None, None)

    def _repeating_through(self, category_id: int, month: str) -> tuple[Decimal | None, int | None]:
        rows = [e for e in self.repo.entries_up_to(month) if e.category_id == category_id and not e.one_off]
        return (rows[-1].amount, rows[-1].average_months) if rows else (None, None)

    def _rolling_average(self, category_id: int, month: str, months: int,
                         children: dict[int, list[int]], cache: dict[tuple[int, int], Decimal]) -> Decimal:
        key = (category_id, months)
        if key in cache:
            return cache[key]
        total = ZERO
        cursor = parse_month(month)[0]
        descendants = {category_id}
        pending = [category_id]
        while pending:
            child_ids = children.get(pending.pop(), [])
            descendants.update(child_ids)
            pending.extend(child_ids)
        for _ in range(months):
            start, end = parse_month((cursor - timedelta(days=1)).strftime("%Y-%m"))
            actual = self.reporting.money_out_by_category(start, end)
            total += sum((actual.get(cid, ZERO) for cid in descendants), ZERO)
            cursor = start
        cache[key] = (total / months).quantize(Decimal("0.01"))
        return cache[key]

    @staticmethod
    def _average_period(raw: object) -> int | None:
        value = str(raw or "").strip()
        if value in ("", "manual"):
            return None
        if value not in ("3", "6"):
            raise ValidationError("Choose a 3-month or 6-month average, or enter a manual budget.", "budget")
        return int(value)

    def _budgetable(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if category.movement != Movement.OUTFLOW or category.is_root:
            raise ValidationError(f"{category.name} cannot have a budget — budgets are for money out.", "budget")
        return category

    @staticmethod
    def _parse(raw: object, category: Category) -> Decimal | None:
        if raw is None or str(raw).strip() == "":
            return None
        value = check_places(to_decimal(raw, "budget"), 2, "budget")
        if value < ZERO:
            raise ValidationError(f"The budget for {category.name} cannot be negative.", "budget")
        return value
