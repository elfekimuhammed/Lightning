"""Public API of the budgeting module: the month view (budget vs actual) and saving budgets."""

from __future__ import annotations

from decimal import Decimal

from lightning.categories.domain import Category, Movement, Scope
from lightning.categories.service import CategoryService
from lightning.core.dates import parse_month
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
    def amounts_for(self, month: str) -> dict[int, tuple[Decimal | None, bool]]:
        """Direct amount per category for a month: (amount or None, is it a this-month-only override)."""
        parse_month(month)
        repeating: dict[int, Decimal | None] = {}
        one_off: dict[int, Decimal | None] = {}
        for e in self.repo.entries_up_to(month):  # ordered by category, month
            if e.one_off:
                one_off[e.category_id] = e.amount
            else:
                repeating[e.category_id] = e.amount  # later months overwrite earlier ones
        result = {cid: (amount, False) for cid, amount in repeating.items()}
        result.update({cid: (amount, True) for cid, amount in one_off.items()})
        return {cid: v for cid, v in result.items() if v[0] is not None}

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
        for c in reversed(cats):  # children before parents
            kids = children.get(c.id, [])
            actual[c.id] = spent.get(c.id, ZERO) + sum((actual[k] for k in kids), ZERO)
            if c.id in direct:
                budget[c.id] = direct[c.id][0]
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
            amount, one_off = direct.get(c.id, (None, False))
            section.lines.append(BudgetLine(
                category_id=c.id, code=c.code, name=c.name, depth=c.depth, direct=amount, one_off=one_off,
                budget=budget[c.id], actual=actual[c.id], covered=covered,
            ))
            kids_total = sum((budget[k] for k in children.get(c.id, []) if budget[k] is not None), ZERO)
            if amount is not None and kids_total > amount:
                warnings.append(f"{self.categories.display_name(c.id)}: its categories add up to "
                                f"{fmt(kids_total)}, more than its budget of {fmt(amount)}.")
        income = self.reporting.cash_flow(first, last).inflows
        return BudgetMonth(month, [s for s in sections.values() if s.lines], income, warnings)

    # ------------------------------------------------------------------ writing
    def set_budget(self, category_id: int, month: str, amount: object, only_this_month: bool = False) -> bool:
        """Set (or clear, with '') a budget. Returns True if anything changed."""
        return self.save_month(month, {category_id: amount}, only_this_month) > 0

    def save_month(self, month: str, amounts: dict[int, object], only_this_month: bool = False) -> int:
        """Save several budget cells at once (the budget page). Returns how many changed."""
        parse_month(month)
        current = self.amounts_for(month)
        changed = 0
        with self.db.transaction():
            for category_id, raw in amounts.items():
                category = self._budgetable(category_id)
                value = self._parse(raw, category)
                if current.get(category_id, (None, False))[0] == value:
                    continue
                before = self._repeating_before(category_id, month)
                if only_this_month:
                    if value == self._repeating_through(category_id, month):
                        self.repo.delete(category_id, month, one_off=True)
                    else:
                        self.repo.upsert(category_id, month, True, value)
                else:
                    self.repo.delete(category_id, month, one_off=True)
                    if value == before:
                        self.repo.delete(category_id, month, one_off=False)  # same as before: nothing to store
                    else:
                        self.repo.upsert(category_id, month, False, value)
                changed += 1
        return changed

    # ------------------------------------------------------------------ helpers
    def _repeating_before(self, category_id: int, month: str) -> Decimal | None:
        rows = [e for e in self.repo.entries_up_to(month) if e.category_id == category_id and not e.one_off
                and e.month < month]
        return rows[-1].amount if rows else None

    def _repeating_through(self, category_id: int, month: str) -> Decimal | None:
        rows = [e for e in self.repo.entries_up_to(month) if e.category_id == category_id and not e.one_off]
        return rows[-1].amount if rows else None

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
