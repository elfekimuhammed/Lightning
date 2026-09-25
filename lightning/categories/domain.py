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
    default_reimbursable: bool
    is_system: bool
    active: bool
    sort_order: int

    @property
    def depth(self) -> int:
        return self.code.count(".")

    @property
    def label(self) -> str:
        return f"{self.code} · {self.name}"

    @property
    def is_root(self) -> bool:
        return self.parent_id is None
