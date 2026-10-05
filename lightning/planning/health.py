"""How safe the money is: debt and fixed-cost ratios (Project Overview › Upcoming projects #3).

Each ratio divides two figures other services already compute and keeps both, so a screen can show
what was divided by what. A ratio with nothing sensible to divide by (no income measured, a net worth
of zero or less) is None, never a made-up number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from lightning.core.money import ZERO

from .domain import PlanKind, per_year


@dataclass(frozen=True)
class Ratio:
    key: str                 # its figure registry key
    part: Decimal            # what is divided: What you owe, payments a month
    whole: Decimal | None    # what it is divided by: Net worth, Cash you own, Average monthly income

    @property
    def percent(self) -> Decimal | None:
        return self.part / self.whole * 100 if self.whole is not None and self.whole > 0 else None


@dataclass(frozen=True)
class Health:
    debt_to_net_worth: Ratio
    debt_to_cash: Ratio
    loan_payments_to_income: Ratio
    fixed_costs_to_income: Ratio
    bills_a_month: Decimal       # bills and subscriptions, a month
    loans_a_month: Decimal       # loan payments still to make, a month


class HealthService:
    def __init__(self, planning, position, budgets):
        self.planning = planning
        self.position = position
        self.budgets = budgets

    def loans_a_month(self, day: date) -> Decimal:
        """Loan payments a month, counting only loans with payments still to make."""
        return sum((per_year(item) / 12 for item in self.planning.items((PlanKind.LOAN,))
                    if self.planning.loan_progress(item, day)["still_to_pay"] > 0), ZERO)

    def bills_a_month(self) -> Decimal:
        """Bills and subscriptions a month: what Cash planning › Recurring totals."""
        return sum((per_year(item) / 12 for item in self.planning.items((PlanKind.BILL, PlanKind.SUBSCRIPTION))), ZERO)

    def at(self, day: date) -> Health:
        position = self.position.at(day)
        owe = position.what_you_owe
        income = self.budgets.income_average(day.strftime("%Y-%m")).amount
        loans, bills = self.loans_a_month(day), self.bills_a_month()
        return Health(
            debt_to_net_worth=Ratio("debt_to_net_worth", owe, position.net_worth),
            debt_to_cash=Ratio("debt_to_cash", owe, position.cash_you_own),
            loan_payments_to_income=Ratio("loan_payments_to_income", loans, income),
            fixed_costs_to_income=Ratio("fixed_costs_to_income", bills + loans, income),
            bills_a_month=bills, loans_a_month=loans)
