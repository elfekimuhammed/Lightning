"""Named financial-health figures and profile-owned comparison limits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from lightning.core.dates import fmt_date, month_of, parse_month, today
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, check_places, to_decimal
from lightning.database.settings import SettingsStore

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


@dataclass(frozen=True)
class HealthMonth:
    month: str
    savings_rate: Decimal | None
    net_worth: Decimal | None


@dataclass(frozen=True)
class HealthFigure:
    key: str
    value: Decimal | None
    unit: str
    period: str
    limit: Decimal | None
    direction: str
    status: str | None
    support: tuple[tuple[str, Decimal | None], ...]
    href: str


LIMIT_DEFAULTS: dict[str, Decimal | None] = {
    "savings_rate": Decimal("20"),
    "fixed_costs_to_income": Decimal("50"),
    "loan_payments_to_income": Decimal("20"),
    "debt_to_cash": None,
    "debt_to_net_worth": None,
}
LIMIT_DIRECTIONS = {
    "savings_rate": "minimum",
    "fixed_costs_to_income": "maximum",
    "loan_payments_to_income": "maximum",
    "debt_to_cash": "maximum",
    "debt_to_net_worth": "maximum",
}
LIMIT_LABELS = {
    "savings_rate": "Savings rate",
    "fixed_costs_to_income": "Fixed costs to income",
    "loan_payments_to_income": "Loan payments to income",
    "debt_to_cash": "Debt to cash",
    "debt_to_net_worth": "Debt to net worth",
}
LIMIT_PREFIX = "financial_health_limit_"
EMERGENCY_FUND_MONTHS = Decimal("6")
NO_LIMIT_SUPPORTED = frozenset({"debt_to_cash", "debt_to_net_worth"})


def compare_to_limit(value: Decimal | None, limit: Decimal | None, direction: str) -> str | None:
    """Compare an available figure to a set limit; equality is within the limit."""
    if value is None or limit is None:
        return None
    within = value >= limit if direction == "minimum" else value <= limit
    return "within your limit" if within else "outside your limit"


class HealthService:
    def __init__(self, planning, position, budgets, settings: SettingsStore | None = None):
        self.planning = planning
        self.position = position
        self.budgets = budgets
        self.reporting = position.reporting
        self.reserves = position.reserves
        self.settings = settings or SettingsStore(budgets.db)

    def loans_a_month(self, day: date) -> Decimal:
        """Loan payments a month, counting only loans with payments still to make."""
        return sum((per_year(item) / 12 for item in self.planning.items((PlanKind.LOAN,))
                    if self.planning.loan_progress(item, day)["still_to_pay"] > 0), ZERO)

    def bills_a_month(self) -> Decimal:
        """Bills and subscriptions a month: what Cash planning › Recurring totals."""
        return sum((per_year(item) / 12 for item in self.planning.items((PlanKind.BILL, PlanKind.SUBSCRIPTION))), ZERO)

    def at(self, day: date) -> Health:
        position = self.position.at(day, match_payments=False)
        owe = position.what_you_owe
        income = self.budgets.income_average(day.strftime("%Y-%m")).amount
        loans, bills = self.loans_a_month(day), self.bills_a_month()
        return Health(
            debt_to_net_worth=Ratio("debt_to_net_worth", owe, position.net_worth),
            debt_to_cash=Ratio("debt_to_cash", owe, position.cash_you_own),
            loan_payments_to_income=Ratio("loan_payments_to_income", loans, income),
            fixed_costs_to_income=Ratio("fixed_costs_to_income", bills + loans, income),
            bills_a_month=bills, loans_a_month=loans)

    def limit_values(self) -> dict[str, Decimal | None]:
        """Current profile limits; absent settings use defaults, and `none` means no limit."""
        values = {}
        for key, default in LIMIT_DEFAULTS.items():
            saved = self.settings.get(LIMIT_PREFIX + key)
            if not saved:
                values[key] = default
            elif saved.casefold() == "none":
                values[key] = None
            else:
                try:
                    values[key] = to_decimal(saved, "limit")
                except ValidationError:
                    values[key] = default
        return values

    def limit_settings(self) -> list[dict]:
        values = self.limit_values()
        return [{"key": key, "label": LIMIT_LABELS[key], "direction": LIMIT_DIRECTIONS[key],
                 "value": values[key], "default": LIMIT_DEFAULTS[key], "no_limit": values[key] is None,
                 "supports_no_limit": key in NO_LIMIT_SUPPORTED, "unit": "%"} for key in LIMIT_DEFAULTS]

    def set_limit(self, key: str, raw: str, no_limit: bool = False) -> Decimal | None:
        if key not in LIMIT_DEFAULTS:
            raise ValidationError("Choose a financial-health limit.", "limit")
        if no_limit:
            if key not in NO_LIMIT_SUPPORTED:
                raise ValidationError("This figure needs a personal limit.", "limit")
            value = None
        else:
            value = check_places(to_decimal(raw, "limit"), 1, "limit")
            if value < ZERO:
                raise ValidationError("A financial-health limit cannot be negative.", "limit")
        self.settings.set(LIMIT_PREFIX + key, "none" if value is None else format(value, "f"))
        return value

    def restore_limit(self, key: str) -> Decimal | None:
        if key not in LIMIT_DEFAULTS:
            raise ValidationError("Choose a financial-health limit.", "limit")
        value = LIMIT_DEFAULTS[key]
        self.settings.set(LIMIT_PREFIX + key, "none" if value is None else format(value, "f"))
        return value

    def emergency_fund(self, day: date):
        """Use the Reserves page's single target and selected income-or-spending basis."""
        position = self.position.at(day, match_payments=False)
        reserve = next((row for row in (position.reserve_rows or ()) if row["kind"] == "EMERGENCY"), None)
        return self.budgets.emergency_fund(month_of(day), reserve["effective_allocated"] if reserve else None)

    def overview(self, as_of: date | None = None) -> dict:
        """Assemble the read-only figures and six completed-month trends for the Health page."""
        day = as_of or today()
        position = self.position.at(day, match_payments=False)
        health = self.at(day)
        fund = self.emergency_fund(day)
        current_month_start, _ = parse_month(month_of(day))
        savings_end = current_month_start - timedelta(days=1)
        savings_month = month_of(savings_end)
        savings_start, _ = parse_month(savings_month)
        savings = self.reporting.cash_flow(savings_start, savings_end)
        income_average = self.budgets.income_average(month_of(day))
        limits = self.limit_values()

        def figure(key, value, unit, period, limit, direction, support, href):
            return HealthFigure(key, value, unit, period, limit, direction,
                                compare_to_limit(value, limit, direction), tuple(support), href)

        avg_label = "Average monthly income" if fund.basis == "income" else "Average monthly spending"
        emergency_status = compare_to_limit(fund.months, EMERGENCY_FUND_MONTHS, "minimum")
        figures = (
            figure("net_worth", position.net_worth, "money", f"As of {fmt_date(day)}", None, "maximum",
                   (("What you own", position.what_you_own), ("What you owe", position.what_you_owe)), "/"),
            HealthFigure("emergency_fund", fund.months, "months", f"As of {fmt_date(day)} · months of {avg_label.lower()}",
                         EMERGENCY_FUND_MONTHS, "minimum", emergency_status,
                         (("Reserves for emergencies", fund.set_aside), (avg_label, fund.monthly)), "/plan/reserves"),
            figure("savings_rate", savings.savings_rate, "%", savings_month, limits["savings_rate"], "minimum",
                   (("Net flow", savings.net), ("Money in", savings.inflows)), "/"),
            figure("debt_to_cash", health.debt_to_cash.percent, "%", fmt_date(day), limits["debt_to_cash"], "maximum",
                   (("What you owe", health.debt_to_cash.part), ("Cash you own", health.debt_to_cash.whole)), "/plan/loans"),
            figure("debt_to_net_worth", health.debt_to_net_worth.percent, "%", fmt_date(day), limits["debt_to_net_worth"], "maximum",
                   (("What you owe", health.debt_to_net_worth.part), ("Net worth", health.debt_to_net_worth.whole)), "/plan/loans"),
            figure("fixed_costs_to_income", health.fixed_costs_to_income.percent, "%", f"Monthly · {income_average.window}", limits["fixed_costs_to_income"], "maximum",
                   (("Bills and subscriptions a month", health.bills_a_month),
                    ("Loan payments a month", health.loans_a_month),
                    ("Average monthly income", health.fixed_costs_to_income.whole)), "/plan/recurring"),
            figure("loan_payments_to_income", health.loan_payments_to_income.percent, "%", f"Monthly · {income_average.window}", limits["loan_payments_to_income"], "maximum",
                   (("Loan payments a month", health.loan_payments_to_income.part),
                    ("Average monthly income", health.loan_payments_to_income.whole)), "/plan/loans"),
        )

        first_activity = self.reporting.first_activity_date()
        first_date = date.fromisoformat(first_activity) if first_activity else None
        month_cursor = savings_start
        for _ in range(5):
            month_cursor = month_cursor.replace(day=1) - timedelta(days=1)
            month_cursor = month_cursor.replace(day=1)
        trends = []
        cursor = month_cursor
        for _ in range(6):
            key = month_of(cursor)
            _, month_end = parse_month(key)
            flow = self.reporting.cash_flow(cursor, month_end)
            worth = (self.position.at(month_end, match_payments=False).net_worth
                     if first_date and month_end >= first_date else None)
            trends.append(HealthMonth(key, flow.savings_rate, worth))
            next_month = month_end + timedelta(days=1)
            cursor = next_month
        return {"as_of": fmt_date(day), "savings_month": savings_month, "fund": fund,
                "figures": figures, "trends": tuple(trends), "emergency_months": EMERGENCY_FUND_MONTHS,
                "income_average": income_average}
