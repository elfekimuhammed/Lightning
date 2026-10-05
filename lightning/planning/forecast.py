"""Cash forecast: free cash today, carried forward month by month.

An estimate. It reads the plan, the budget and reserves and never changes net worth or free cash.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from lightning.core.dates import fmt_date, month_of, parse_date, parse_month, today
from lightning.core.figures import label
from lightning.core.money import ZERO, from_e6

from .domain import CashForecast, ForecastMonth, Payment, PaymentStatus, PlanKind

HORIZON_MONTHS = 3


def _months(start: date, count: int) -> list[str]:
    index = start.year * 12 + start.month - 1
    return [f"{(index + i) // 12}-{(index + i) % 12 + 1:02d}" for i in range(count)]


def _deposit_cash_events(service, as_of: date, end: date):
    """Return projected CD events, replacing maturity projections already posted as transfers."""
    if service is None:
        return []
    events = service.future_events(as_of, end)
    db = getattr(service, "db", None)
    if db is None:
        return events
    replaced: set[tuple[int, int, str]] = set()
    actual = {}
    for event in events:
        if event.kind not in ("PRINCIPAL", "MATURITY"):
            continue
        destination_id = getattr(event, "destination_account_id", getattr(event, "account_id", None))
        key = (event.deposit_account_id, destination_id, event.date)
        if key in actual:
            continue
        rows = db.all(
            "SELECT dst.quantity_e6 FROM transactions t "
            "JOIN ledger_entries src ON src.transaction_id=t.id "
            "JOIN ledger_entries dst ON dst.transaction_id=t.id "
            "WHERE t.status='POSTED' AND t.type='TRF' AND t.date=? "
            "AND src.account_id=? AND src.effect='INTERNAL' "
            "AND dst.account_id=? AND dst.effect='INTERNAL'",
            (event.date, event.deposit_account_id, destination_id),
        )
        actual[key] = sum((abs(int(row["quantity_e6"])) for row in rows), 0)
        if actual[key]:
            replaced.add(key)
    if not replaced:
        return events
    adjusted = [event for event in events if (
        event.deposit_account_id,
        getattr(event, "destination_account_id", getattr(event, "account_id", None)),
        event.date,
    ) not in replaced]
    for deposit_id, destination_id, event_date in replaced:
        amount_e6 = actual[(deposit_id, destination_id, event_date)]
        adjusted.append(type("RecordedDepositEvent", (), {
            "date": event_date, "amount": from_e6(amount_e6),
            "deposit_account_id": deposit_id, "destination_account_id": destination_id,
        })())
    return adjusted


class CashForecaster:
    def __init__(self, planning, reporting, reserves, budgets, categories, position, deposits=None):
        self.planning = planning
        self.position = position
        self.reporting = reporting
        self.reserves = reserves
        self.budgets = budgets
        self.categories = categories
        self.deposits = deposits

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
        """Budget still to spend in the month, and the categories the plan covers.

        It is the Budget screen's own plan (BudgetService.plan_summary): limits plus background
        estimates, so the forecast and the Budget tab show one Left in plan (audit 2026-10-05 #7)."""
        view = self.budgets.month_view(month)
        summary = self.budgets.plan_summary(month)
        covered = {line.category_id for section in view.sections for line in section.lines
                   if line.budget is not None or line.covered}
        covered |= {estimate["category_id"] for estimate in summary["estimates"]}
        room = summary["left"] if current else summary["planned"]
        return max(room, ZERO), covered

    def _goal_need(self, month: str, as_of: date) -> Decimal:
        """What dated reserve goals still need set aside, spread over the months left."""
        return sum((row["amount"] for row in self.goal_needs(month, as_of)), ZERO)

    def goal_needs(self, month: str, as_of: date | None = None) -> list[dict]:
        """Informational monthly saving needs for dated project reserves."""
        day = as_of or today()
        month_start, _ = parse_month(month)
        result = []
        for reserve in self.reserves.list_active():
            if reserve["kind"] == "EMERGENCY" or not reserve.get("due_date"):
                continue
            due = date.fromisoformat(reserve["due_date"])
            if due < month_start:
                continue
            # Everything set aside so far counts, including what the goal has already paid for: a goal
            # funded in full and partly spent needs nothing more (audit 2026-10-05 #8).
            missing = max(reserve["target"] - reserve["allocated"], ZERO)
            months_left = max((due.year - day.year) * 12 + due.month - day.month + 1, 1)
            amount = (missing / months_left).quantize(Decimal("0.01"))
            if amount:
                result.append({"name": reserve["name"], "amount": amount, "due_date": reserve["due_date"]})
        return result

    # -------------------------------------------------------------- forecast
    def forecast(self, as_of: date | None = None, months: int = HORIZON_MONTHS) -> CashForecast:
        day = as_of or today()
        free = self.free_cash(day)
        average, average_months = self.average_income(day)
        month_keys = _months(day, months)
        horizon_end = parse_month(month_keys[-1])[1]
        deposit_events = _deposit_cash_events(self.deposits, day, horizon_end)
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
            # Only this month's unreceived income is still expected now. Older paydays that were never
            # marked received are not added on top (audit 2026-10-05 #3: five months of salary at once).
            income = sum((p.amount for p in in_month + [p for p in due_now if p.due_date[:7] == key]
                          if p.item.is_income), ZERO)
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
            deposit_cash = sum((event.amount for event in deposit_events if event.date[:7] == key), ZERO)
            closing = opening + income + deposit_cash - commitments - budget_spending - goals
            rows.append(ForecastMonth(key, opening, income, estimated, commitments, budget_spending, goals, closing,
                                      deposit_cash))
            opening = closing

        next_income = next((p for p in upcoming if p.item.is_income), None)
        if next_income:
            next_date, next_estimated = next_income.due_date, False
        elif average:
            next_date, next_estimated = fmt_date(parse_month(month_keys[1])[0]) if len(month_keys) > 1 else None, True
        else:
            next_date, next_estimated = None, False
        before = [p for p in upcoming if not p.item.is_income and (next_date is None or p.due_date < next_date)]
        safe, parts = self._safe_to_spend(free, before, next_date, day, rows)
        return CashForecast(fmt_date(day), free, average, average_months, next_date, next_estimated,
                            safe, parts, rows, [p for p in upcoming if p.due_date <= next_date] if next_date else upcoming[:10],
                            before)

    def _safe_to_spend(self, free: Decimal, before: list[Payment], until: str | None, day: date,
                       rows: list[ForecastMonth]) -> tuple[Decimal, list[tuple[str, Decimal]]]:
        """Free cash less what is already promised before the next income.

        Budget and goal needs count for every month until the next income, not just this one: between
        jobs, next month's spending still comes out of today's cash. The month the income lands in
        counts for the days before it."""
        bills = sum((p.amount for p in before), ZERO)
        spending = goals = ZERO
        for index, row in enumerate(rows):
            share = Decimal(1)
            if index:
                if until is None:
                    break
                first_day, last_day = parse_month(row.month)
                pay_day = parse_date(until)
                if pay_day <= first_day:
                    break
                if pay_day <= last_day:
                    share = Decimal((pay_day - first_day).days) / Decimal((last_day - first_day).days + 1)
            spending += row.budget_spending * share
            goals += row.goal_saving * share
        spending, goals = spending.quantize(Decimal("0.01")), goals.quantize(Decimal("0.01"))
        parts = [(label("free_cash"), free), (label("payments_before_next_income"), -bills),
                 (label("left_in_plan_after_bills"), -spending), (label("saving_for_goals"), -goals)]
        return free - bills - spending - goals, [(name, value) for name, value in parts if value or name == label("free_cash")]
