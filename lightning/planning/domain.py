from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from lightning.core.money import ZERO


class PlanKind(StrEnum):
    BILL = "BILL"
    SUBSCRIPTION = "SUBSCRIPTION"
    INCOME = "INCOME"
    LOAN = "LOAN"


KIND_LABELS = {PlanKind.BILL: "Bill", PlanKind.SUBSCRIPTION: "Subscription",
               PlanKind.INCOME: "Income", PlanKind.LOAN: "Loan"}
RECURRING_KINDS = (PlanKind.BILL, PlanKind.SUBSCRIPTION, PlanKind.INCOME)


class Frequency(StrEnum):
    ONCE = "ONCE"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


FREQUENCY_LABELS = {Frequency.ONCE: "Once", Frequency.WEEKLY: "Weekly", Frequency.MONTHLY: "Monthly",
                    Frequency.QUARTERLY: "Every 3 months", Frequency.YEARLY: "Yearly"}


class PaymentStatus(StrEnum):
    PAID = "PAID"          # settled by a posted transaction
    SKIPPED = "SKIPPED"    # the user says this one will not happen
    DUE = "DUE"            # date is today or earlier and nothing settled it
    UPCOMING = "UPCOMING"  # date is after today


@dataclass(frozen=True)
class PlannedItem:
    id: int
    kind: PlanKind
    name: str
    amount: Decimal                 # per payment, always positive
    frequency: Frequency
    interval_count: int
    start_date: str
    end_date: str | None
    payment_count: int | None
    account_id: int | None
    category_id: int | None
    counterparty_id: int | None
    principal: Decimal | None
    active: bool
    notes: str

    @property
    def is_income(self) -> bool:
        return self.kind == PlanKind.INCOME

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind]


@dataclass(frozen=True)
class Payment:
    """One scheduled payment of a planned item and its status on the as-of date."""
    item: PlannedItem
    due_date: str
    number: int                     # 1-based position in the schedule
    status: PaymentStatus
    transaction_id: int | None = None
    paid_amount: Decimal | None = None  # what was actually paid, when it was recorded or linked

    @property
    def amount(self) -> Decimal:
        return self.item.amount

    @property
    def outstanding(self) -> bool:
        return self.status in (PaymentStatus.DUE, PaymentStatus.UPCOMING)


@dataclass(frozen=True)
class WhatYouOwe:
    bills_due: Decimal              # unpaid bills, subscriptions and loan payments dated on or before as-of
    loans_still_to_pay: Decimal     # every unpaid loan payment, due or upcoming
    bills_due_items: list[Payment] = field(default_factory=list)

    @property
    def other_bills_due(self) -> Decimal:
        """Bills due that are not loan payments (those are already in loans still to pay)."""
        return self.bills_due - sum((p.amount for p in self.bills_due_items if p.item.kind == PlanKind.LOAN), ZERO)

    @property
    def total(self) -> Decimal:
        """What you owe: bills due plus loans still to pay, each payment counted once."""
        return self.other_bills_due + self.loans_still_to_pay


@dataclass(frozen=True)
class ForecastMonth:
    month: str
    opening: Decimal
    income: Decimal
    income_estimated: bool          # True when Average monthly income stands in for scheduled income
    commitments: Decimal            # bills, subscriptions and loan payments scheduled in the month
    budget_spending: Decimal        # remaining budget plan not already covered by scheduled bills
    goal_saving: Decimal            # what reserves with due dates still need this month
    closing: Decimal
    deposit_cash: Decimal = ZERO

    @property
    def money_in(self) -> Decimal:
        return self.income + self.deposit_cash

    @property
    def money_out(self) -> Decimal:
        return self.commitments + self.budget_spending + self.goal_saving

    @property
    def net(self) -> Decimal:
        return self.money_in - self.money_out


@dataclass(frozen=True)
class CashForecast:
    as_of: str
    free_cash: Decimal
    average_income: Decimal | None
    average_income_months: int
    next_income_date: str | None
    next_income_estimated: bool
    safe_to_spend: Decimal
    safe_to_spend_parts: list[tuple[str, Decimal]]
    months: list[ForecastMonth]
    upcoming: list[Payment]
    # The payments Safe to spend takes off: scheduled, not yet due, before the next income.
    payments_before_income: list[Payment] = field(default_factory=list)

    @property
    def lowest(self) -> ForecastMonth | None:
        return min(self.months, key=lambda m: m.closing) if self.months else None
