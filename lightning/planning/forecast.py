"""Cash forecast: free cash today, carried forward month by month.

An estimate. It reads the plan, the budget and reserves and never changes net worth or free cash.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from lightning.core.dates import fmt_date, month_of, parse_month, today
from lightning.core.money import ZERO

from .domain import CashForecast, ForecastMonth, Payment, PaymentStatus, PlanKind

HORIZON_MONTHS = 3


def _months(start: date, count: int) -> list[str]:
    index = start.year * 12 + start.month - 1
    return [f"{(index + i) // 12}-{(index + i) % 12 + 1:02d}" for i in range(count)]


class CashForecaster:
    def __init__(self, planning, reporting, reserves, budgets, categories, position):
        self.planning = planning
        self.position = position
        self.reporting = reporting
        self.reserves = reserves
        self.budgets = budgets
        self.categories = categories

    # -------------------------------------------------------------- inputs
    def average_income(self, as_of: date) -> tuple[Decimal | None, int]:
        """Average monthly income: the same figure the budget uses (BudgetService.income_average)."""
        average = self.budgets.income_average(month_of(as_of))
        return average.amount, average.months_counted

    def free_cash(self, as_of: date) -> Decimal:
        """Free cash from the position: Cash you own − Reserves − Bills due."""
        position = self.position.at(as_of)
        if position.free_cash is not None:
            return position.free_cash
        return position.cash_you_own - self.reserves.cash_summary(ZERO)["allocated"] - position.bills_due

    def _budget(self, month: str, current: bool) -> tuple[Decimal, set[int]]:
        """Budget still to spend in the month, and the categories a budget covers."""
        view = self.budgets.month_view(month)
        covered = {line.category_id for section in view.sections for line in section.lines
                   if line.budget is not None or line.covered}
        room = view.available - (view.actual if current else ZERO)
        return max(room, ZERO), covered

    def _goal_need(self, month: str, as_of: date) -> Decimal:
        """What dated reserve goals still need set aside, spread over the months left."""
        need = ZERO
        month_start, _ = parse_month(month)
        for reserve in self.reserves.list_active():
            if reserve["kind"] == "EMERGENCY" or not reserve.get("due_date"):
                continue
            due = date.fromisoformat(reserve["due_date"])
            if due < month_start:
                continue
            missing = max(reserve["target"] - reserve["effective_allocated"], ZERO)
            months_left = max((due.year - as_of.year) * 12 + due.month - as_of.month + 1, 1)
            need += (missing / months_left).quantize(Decimal("0.01"))
        return need

    # -------------------------------------------------------------- forecast
    def forecast(self, as_of: date | None = None, months: int = HORIZON_MONTHS) -> CashForecast:
        day = as_of or today()
        free = self.free_cash(day)
        average, average_months = self.average_income(day)
        month_keys = _months(day, months)
        horizon_end = parse_month(month_keys[-1])[1]
        upcoming = [p for p in self.planning.all_payments(horizon_end, day)
                    if p.status == PaymentStatus.UPCOMING]
        # Payments already due: bills are in free cash already (Bills due); income not yet received
        # is still expected this month.
        due = [p for p in self.planning.all_payments(day, day) if p.status == PaymentStatus.DUE]
        has_scheduled_income = any(i.kind == PlanKind.INCOME for i in self.planning.items((PlanKind.INCOME,)))

        rows, opening = [], free
        for index, key in enumerate(month_keys):
            current = index == 0
            in_month = [p for p in upcoming if p.due_date[:7] == key]
            due_now = due if current else []
            income = sum((p.amount for p in in_month + due_now if p.item.is_income), ZERO)
            estimated = False
            if not has_scheduled_income and average:
                received = (self.reporting.cash_flow(parse_month(key)[0], day).inflows if current else ZERO)
                income, estimated = max(average - received, ZERO), True
            outgoing = [p for p in in_month if not p.item.is_income]
            budget_room, covered = self._budget(key, current)
            covered_bills = sum((p.amount for p in outgoing if p.item.category_id in covered), ZERO)
            other_bills = sum((p.amount for p in outgoing if p.item.category_id not in covered), ZERO)
            # A bill in a budgeted category is part of that budget, not on top of it. That holds for
            # bills already due too: they come off free cash, so they come off the budget room here.
            due_covered = sum((p.amount for p in due_now if not p.item.is_income
                               and p.item.category_id in covered), ZERO)
            budget_spending = max(budget_room - covered_bills - due_covered, ZERO)
            commitments = covered_bills + other_bills
            goals = self._goal_need(key, day)
            closing = opening + income - commitments - budget_spending - goals
            rows.append(ForecastMonth(key, opening, income, estimated, commitments, budget_spending, goals, closing))
            opening = closing

        next_income = next((p for p in upcoming if p.item.is_income), None)
        if next_income:
            next_date, next_estimated = next_income.due_date, False
        elif average:
            next_date, next_estimated = fmt_date(parse_month(month_keys[1])[0]) if len(month_keys) > 1 else None, True
        else:
            next_date, next_estimated = None, False
        safe, parts = self._safe_to_spend(free, upcoming, next_date, day, rows[0] if rows else None)
        return CashForecast(fmt_date(day), free, average, average_months, next_date, next_estimated,
                            safe, parts, rows, [p for p in upcoming if p.due_date <= next_date] if next_date else upcoming[:10])

    def _safe_to_spend(self, free: Decimal, upcoming: list[Payment], until: str | None, day: date,
                       first: ForecastMonth | None) -> tuple[Decimal, list[tuple[str, Decimal]]]:
        """Free cash less what is already promised before the next income."""
        before = [p for p in upcoming if not p.item.is_income and (until is None or p.due_date < until)]
        bills = sum((p.amount for p in before), ZERO)
        this_month = first.budget_spending if first else ZERO
        goals = first.goal_saving if first else ZERO
        parts = [("Free cash", free), ("Bills and loan payments before next income", -bills),
                 ("Left in plan after bills", -this_month), ("Saving for goals", -goals)]
        return free - bills - this_month - goals, [(label, value) for label, value in parts if value or label == "Free cash"]
