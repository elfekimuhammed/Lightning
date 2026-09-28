"""Budgeting — how much you plan to spend per category per month, against what you actually spent.

Rules
- Budgets exist for money-out categories only (Personal, Work, Fees… and their categories).
- Repeat until changed: an amount set for a month applies to every later month until changed.
  "This month only" overrides a single month.
- Either level: a group budget (Personal 20,000) is the ceiling for everything in the group;
  category budgets (Food 6,000) are part of it. A group without its own amount = sum of its categories.
- Actual = money out in the month for the category and everything under it (refunds reduce it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from lightning.core.money import ZERO


@dataclass
class BudgetEntry:
    """One stored row (see migration 0005)."""

    id: int
    category_id: int
    month: str  # yyyy-mm
    one_off: bool
    amount: Decimal | None  # None = no budget
    average_months: int | None = None  # rolling average from prior complete months
    income_percent: Decimal | None = None


@dataclass
class BudgetLine:
    category_id: int
    code: str
    name: str
    depth: int  # 1 = group (Personal), 2 = category (Food), 3 = sub-category
    direct: Decimal | None  # amount set on this line for the month (None = not set)
    one_off: bool  # the direct amount is a this-month-only override
    average_months: int | None  # None = manual; 3/6 = auto budget from past spending
    budget: Decimal | None  # effective: direct, else sum of children's budgets, else None
    actual: Decimal  # money out, this line and everything under it
    planned_actual: Decimal  # spending covered by a limit at this line or below
    covered: bool  # an ancestor has a budget, so this spending is inside a budget
    opening_carryover: Decimal = ZERO
    carryover_enabled: bool = False
    income_percent: Decimal | None = None

    @property
    def remaining(self) -> Decimal | None:
        return None if self.budget is None else self.budget + self.opening_carryover - self.planned_actual

    @property
    def available(self) -> Decimal | None:
        return None if self.budget is None else self.budget + self.opening_carryover

    @property
    def used_pct(self) -> int | None:
        if not self.available:
            return None
        return int((self.planned_actual / self.available * 100).to_integral_value())

    @property
    def over(self) -> bool:
        return self.available is not None and self.planned_actual > self.available


@dataclass
class BudgetSection:
    name: str  # Personal / Work
    lines: list[BudgetLine] = field(default_factory=list)
    unbudgeted: Decimal = ZERO  # money out in categories with no budget on them or above them

    @property
    def groups(self) -> list[BudgetLine]:
        return [line for line in self.lines if line.depth == 1]

    @property
    def budget(self) -> Decimal:
        return sum((g.budget or ZERO for g in self.groups), ZERO)

    @property
    def actual(self) -> Decimal:
        return sum((g.actual for g in self.groups), ZERO)

    @property
    def planned_actual(self) -> Decimal:
        """Spending covered by category or ancestor limits."""
        return sum((group.planned_actual for group in self.groups), ZERO)

    @property
    def remaining(self) -> Decimal:
        return self.available - self.planned_actual

    @property
    def available(self) -> Decimal:
        return sum((g.available or ZERO for g in self.groups), ZERO)



@dataclass
class BudgetMonth:
    month: str
    sections: list[BudgetSection]
    income: Decimal  # money in this month, for context
    warnings: list[str]

    @property
    def budget(self) -> Decimal:
        return sum((s.budget for s in self.sections), ZERO)

    @property
    def actual(self) -> Decimal:
        return sum((s.actual for s in self.sections), ZERO)

    @property
    def remaining(self) -> Decimal:
        return sum((section.remaining for section in self.sections), ZERO)

    @property
    def available(self) -> Decimal:
        return sum((s.available for s in self.sections), ZERO)

    @property
    def unbudgeted(self) -> Decimal:
        return sum((s.unbudgeted for s in self.sections), ZERO)
