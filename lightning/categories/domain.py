"""Categories — WHY money moved. An editable tree, never hardcoded in the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Movement(StrEnum):
    INFLOW = "INFLOW"  # money in
    OUTFLOW = "OUTFLOW"  # money out


class Scope(StrEnum):
    PERSONAL = "PERSONAL"
    WORK = "WORK"


class CategoryFamily(StrEnum):
    PERSONAL = "PERSONAL"
    WORK = "WORK"
    INVESTMENT = "INVESTMENT"


class Direction(StrEnum):
    IN = "IN"  # + income only
    OUT = "OUT"  # − expense only
    BOTH = "BOTH"  # ± either way


SYSTEM_CODE = "EXP.SYSTEM"  # the fourth L1: categories the app relies on (held for others, loan payments)
MAX_DEPTH = 3  # L1 activity family · L2 category · L3 detail


class IncomeClass(StrEnum):
    HOUSEHOLD = "HOUSEHOLD"  # salary, gifts -> household income
    INVESTMENT = "INVESTMENT"  # interest, dividends -> kept apart from household income


@dataclass
class Category:
    id: int
    code: str  # dotted path, e.g. EXP.WORK.SOFTWARE
    name: str
    parent_id: int | None
    movement: Movement
    scope: Scope | None  # outflows only; inherited from the parent
    income_class: IncomeClass | None  # inflows only; inherited from the parent
    family: CategoryFamily | None  # cross-cutting analysis group, inherited from parent
    default_reimbursable: bool
    is_system: bool
    active: bool
    sort_order: int
    direction_set: Direction | None = None  # None: the default for its movement

    @property
    def direction(self) -> Direction:
        """+ income, − expense, or ± both. Defaults from the movement unless set by hand."""
        if self.direction_set is not None:
            return self.direction_set
        return Direction.IN if self.movement == Movement.INFLOW else Direction.OUT

    @property
    def sign(self) -> str:
        return {Direction.IN: "+", Direction.OUT: "−", Direction.BOTH: "±"}[self.direction]

    @property
    def depth(self) -> int:
        return self.code.count(".")

    @property
    def label(self) -> str:
        return f"{self.code} · {self.name}"

    @property
    def is_root(self) -> bool:
        return self.parent_id is None
