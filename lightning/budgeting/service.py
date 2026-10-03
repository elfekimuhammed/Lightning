"""Public API of the budgeting module: the month view (budget vs actual) and saving budgets."""

from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
import json

from lightning.categories.domain import Category, CategoryFamily, Movement, Scope
from lightning.categories.service import CategoryService
from lightning.core.dates import month_of, parse_month
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, check_places, fmt, from_e6, to_decimal
from lightning.database.connection import Database
from lightning.reporting.service import ReportingService

from .domain import BudgetLine, BudgetMonth, BudgetSection, IncomeAverage
from .repository import BudgetRepository

SECTION_NAMES = {Scope.PERSONAL: "Personal", Scope.WORK: "Work"}


class BudgetService:
    def __init__(self, db: Database, categories: CategoryService, reporting: ReportingService):
        self.db = db
        self.repo = BudgetRepository(db)
        self.categories = categories
        self.reporting = reporting
        # Set by the composition root: month -> {category_id: loan payments scheduled that month}.
        # A category with no budget rule is planned at exactly that amount.
        self.scheduled_loans = lambda month: {}

    def first_owned_spending_date(self) -> str | None:
        """Earliest posted, personally owned entry in a spending category."""
        return self.db.scalar(
            "SELECT MIN(le.date) FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
            "WHERE t.status='POSTED' AND le.category_id IS NOT NULL AND le.owner_id IS NULL"
        )

    def snapshot_rows(self, category_ids: list[int]) -> list[dict]:
        """Capture all stored rules for an undoable bulk edit."""
        if not category_ids:
            return []
        marks = ",".join("?" for _ in category_ids)
        return [dict(row) for row in self.db.all(
            f"SELECT * FROM budgets WHERE category_id IN ({marks})", tuple(category_ids)
        )]

    def restore_rows(self, category_ids: list[int], rows: list[dict]) -> None:
        """Restore the exact rules captured before a bulk edit."""
        if not category_ids:
            return
        columns = ("id", "category_id", "month", "one_off", "amount_e6", "created_at", "updated_at",
                   "average_months", "income_percent_e6")
        marks = ",".join("?" for _ in category_ids)
        names = ",".join(columns)
        values = ",".join("?" for _ in columns)
        with self.db.transaction():
            self.db.execute(f"DELETE FROM budgets WHERE category_id IN ({marks})", tuple(category_ids))
            for row in rows:
                self.db.execute(f"INSERT INTO budgets({names}) VALUES ({values})",
                                tuple(row.get(key) for key in columns))

    # ------------------------------------------------------------------ reading
    def loan_lines(self, month: str) -> dict[int, Decimal]:
        """Categories planned from scheduled loan payments because no budget rule is set for them."""
        explicit = self.amounts_for(month, loans=False)
        return {cid: amount for cid, amount in self.scheduled_loans(month).items()
                if amount and cid not in explicit}

    def amounts_for(self, month: str, loans: bool = True) -> dict[int, tuple[Decimal | None, bool, int | None, Decimal | None]]:
        """Effective amount, one-off flag, average window, and income percentage.

        With ``loans``, a category that has scheduled loan payments and no rule of its own is
        planned at the payments due that month (Planned = scheduled loan payments)."""
        parse_month(month)
        repeating: dict[int, tuple[Decimal | None, int | None, Decimal | None]] = {}
        one_off: dict[int, tuple[Decimal | None, int | None, Decimal | None]] = {}
        for e in self.repo.entries_up_to(month):  # ordered by category, month
            if e.one_off:
                one_off[e.category_id] = (e.amount, e.average_months, e.income_percent)
            else:
                repeating[e.category_id] = (e.amount, e.average_months, e.income_percent)
        result = {cid: (amount, False, period, percent) for cid, (amount, period, percent) in repeating.items()}
        result.update({cid: (amount, True, period, percent) for cid, (amount, period, percent) in one_off.items()})
        result = {cid: v for cid, v in result.items() if v[0] is not None or v[2] is not None or v[3] is not None}
        for cid, (amount, oneoff, period, percent) in list(result.items()):
            if percent is not None:
                income = self.budgeting_income(month)
                amount = None if income is None else (income * percent / Decimal(100)).quantize(Decimal("0.01"))
            elif period:
                cats = [c for c in self.categories.tree(Movement.OUTFLOW) if not c.is_root]
                children = {}
                for cat in cats:
                    if cat.parent_id:
                        children.setdefault(cat.parent_id, []).append(cat.id)
                amount = self._rolling_average(cid, month, period, children, {})
            result[cid] = (amount, oneoff, period, percent)
        if loans:
            for cid, amount in self.scheduled_loans(month).items():
                if amount and cid not in result:
                    result[cid] = (amount, False, None, None)
        return result

    # -- category flags kept with the budget settings (one list each, edited from Categories or Budget)
    def _id_list(self, key: str) -> set[int] | None:
        raw = self.db.scalar("SELECT value FROM settings WHERE key=?", (key,))
        if raw is None:
            return None
        try:
            return {int(value) for value in json.loads(raw)}
        except (ValueError, TypeError):
            return set()

    def _save_id_list(self, key: str, ids: set[int]) -> None:
        from lightning.database.settings import SettingsStore
        SettingsStore(self.db).set(key, json.dumps(sorted(ids)))

    def recurring_income_ids(self) -> set[int]:
        """Income categories you can count on (salary, rent received): the income average and the
        forecast use these. Bonuses and other irregular income are left out."""
        chosen = self._id_list("budget_income_categories")
        if chosen is None:
            chosen = {category.id for category in self.categories.tree() if category.income_class is not None
                      and category.code != "EXP.WORK.BONUS" and (category.family == CategoryFamily.WORK or any(
                          word in category.name.casefold() for word in ("salary", "wage", "pay")))}
        return chosen

    def set_recurring_income(self, category_id: int, recurring: bool) -> None:
        ids = self.recurring_income_ids()
        ids = ids | {category_id} if recurring else ids - {category_id}
        self._save_id_list("budget_income_categories", ids)

    def one_off_ids(self, with_children: bool = True) -> set[int]:
        """Expense categories marked one-off: their spending stays in cash flow and analysis but is
        left out of the budget's totals and of every estimate."""
        ids = self._id_list("budget_one_off_exclusions") or set()
        if with_children:
            for category_id in list(ids):
                try:
                    ids |= {child.id for child in self.categories.descendants(category_id)}
                except Exception:
                    continue
        return ids

    def set_one_off(self, category_id: int, one_off: bool) -> None:
        ids = self.one_off_ids(with_children=False)
        ids = ids | {category_id} if one_off else ids - {category_id}
        self._save_id_list("budget_one_off_exclusions", ids)

    def budgeting_income(self, month: str) -> Decimal | None:
        """Average monthly income for a month's budget (see income_average)."""
        return self.income_average(month).amount

    def income_average(self, month: str) -> IncomeAverage:
        """Average monthly income: owned income in the chosen income categories, averaged over
        the last 3 (or 6) completed months before `month` that had any. A manual amount in
        Settings replaces the average. The budget, reserves and the cash forecast all use this."""
        chosen = self.recurring_income_ids()
        categories = self.categories.tree()
        by_id = {category.id: category for category in categories}
        raw_months = self.db.scalar("SELECT value FROM settings WHERE key='budget_income_months'") or "3"
        lookback = 6 if str(raw_months) == "6" else 3
        manual = self.db.scalar("SELECT value FROM settings WHERE key='budget_manual_monthly_income'")
        if manual:
            return IncomeAverage(to_decimal(manual, "manual_income"), 0, lookback, "", "", True)
        end = parse_month(month)[0] - timedelta(days=1)
        last_month = month_of(end)
        observed = []
        for _ in range(lookback):
            start, _ = parse_month(month_of(end))
            if chosen:
                marks = ",".join("?" for _ in chosen)
                rows = self.db.all(
                    "SELECT le.category_id,SUM(le.amount_base_e6) AS total_e6 "
                    "FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
                    "LEFT JOIN planned_payments pp ON pp.transaction_id=t.id AND pp.status='PAID' "
                    "LEFT JOIN planned_items pi ON pi.id=pp.planned_item_id AND pi.kind='INCOME' "
                    "WHERE t.status='POSTED' AND le.effect='INFLOW' AND le.owner_id IS NULL "
                    "AND le.category_id NOT IN (SELECT id FROM categories WHERE code='EXP.SYSTEM.CUSTODY') "
                    f"AND le.category_id IN ({marks}) "
                    "AND CASE WHEN pi.id IS NOT NULL THEN substr(pp.due_date,1,7) "
                    "ELSE substr(le.date,1,7) END=? GROUP BY le.category_id",
                    (*chosen, month_of(end)),
                )
            else:
                rows = []
            included = [row for row in rows if by_id.get(row["category_id"]) and
                        by_id[row["category_id"]].income_class is not None and
                        by_id[row["category_id"]].code != "EXP.INVEST" and
                        not any(word in by_id[row["category_id"]].code.casefold()
                                for word in ("sale", "opening", "valuation"))]
            if included:
                observed.append(sum((from_e6(row["total_e6"]) for row in included), ZERO))
            end = start - timedelta(days=1)
        amount = (sum(observed, ZERO) / len(observed)).quantize(Decimal("0.01")) if observed else None
        return IncomeAverage(amount, len(observed), lookback, month_of(end + timedelta(days=1)), last_month, False)

    def has_plan(self, month: str) -> bool:
        return bool(self.amounts_for(month, loans=False))

    def month_view(self, month: str) -> BudgetMonth:
        first, last = parse_month(month)
        direct = self.amounts_for(month)
        from_loans = self.loan_lines(month)
        spent = self._owned_spending(first, last)
        cats = [c for c in self.categories.tree(Movement.OUTFLOW) if not c.is_root
                and c.family != CategoryFamily.INVESTMENT]  # investments are never budget spending
        by_id = {c.id: c for c in cats}
        children: dict[int, list[int]] = {}
        for c in cats:
            if c.parent_id in by_id:
                children.setdefault(c.parent_id, []).append(c.id)

        one_offs = self.one_off_ids()
        actual: dict[int, Decimal] = {}
        planned_actual: dict[int, Decimal] = {}
        budget: dict[int, Decimal | None] = {}
        average_cache: dict[tuple[int, int], Decimal | None] = {}
        for c in reversed(cats):  # children before parents
            kids = children.get(c.id, [])
            # A one-off child keeps its own actual but does not add to its parent's (unless it has a plan).
            actual[c.id] = spent.get(c.id, ZERO) + sum((actual[k] for k in kids
                                                        if k not in one_offs or k in direct), ZERO)
            if c.id in direct:
                amount, _, period, percent = direct[c.id]
                budget[c.id] = amount
            else:
                kid_budgets = [budget[k] for k in kids if budget[k] is not None]
                budget[c.id] = sum(kid_budgets, ZERO) if kid_budgets else None
            if budget[c.id] is not None and c.id in direct:
                planned_actual[c.id] = actual[c.id]
            else:
                planned_actual[c.id] = sum((planned_actual[k] for k in kids), ZERO)

        def ancestor_has_direct(c: Category) -> bool:
            parent = by_id.get(c.parent_id)
            while parent is not None:
                if parent.id in direct:
                    return True
                parent = by_id.get(parent.parent_id)
            return False

        sections = {scope: BudgetSection(name) for scope, name in SECTION_NAMES.items()}
        sections["INVESTMENT"] = BudgetSection("Investment")
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
            section = sections["INVESTMENT"] if c.family == CategoryFamily.INVESTMENT else sections[c.scope or Scope.PERSONAL]
            covered = ancestor_has_direct(c)
            if c.id in one_offs and c.id not in direct:
                if c.parent_id not in one_offs:
                    section.one_off += actual[c.id]
            elif c.id not in direct and not covered:
                section.unbudgeted += spent.get(c.id, ZERO)
            shows = c.active or actual[c.id] != ZERO or c.id in direct
            if c.is_system and actual[c.id] == ZERO and c.id not in direct:
                shows = False
            if not shows:
                continue
            amount, one_off, average_months, income_percent = direct.get(c.id, (None, False, None, None))
            section.lines.append(BudgetLine(
                category_id=c.id, code=c.code, name=c.name, depth=c.depth, direct=amount, one_off=one_off,
                average_months=average_months, budget=budget[c.id], actual=actual[c.id],
                planned_actual=planned_actual[c.id], covered=covered,
                opening_carryover=opening_carryovers.get(c.id, ZERO),
                carryover_enabled=carryover_settings.get(c.id, False),
                income_percent=income_percent, from_loans=c.id in from_loans,
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
        cache: dict[tuple[int, int], Decimal | None] = {}
        result = {}
        for category in cats:
            if children.get(category.id):
                continue
            avg = self._rolling_average(category.id, month, 3, children, cache)
            if avg is not None and avg > ZERO:
                result[category.id] = avg
        return result

    def _owned_spending(self, start, end) -> dict[int, Decimal]:
        # Report queries already filter to posted, user-owned categorized ledger
        # effects; investment buys, transfers, and revaluations have no outflow
        # expense effect and therefore do not appear as spending here.
        # Investment fees and moves into investments are not household spending, so the budget never
        # counts them (cash flow and the Overview still do).
        investment = self._investment_ids()
        return {cid: v for cid, v in self.reporting.money_out_by_category(start, end).items() if cid not in investment}

    def _investment_ids(self) -> set[int]:
        return {c.id for c in self.categories.tree() if c.family == CategoryFamily.INVESTMENT}

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
        reset_month = self.repo.reset_month(category_id, month)
        if reset_month == month:
            return ZERO
        enabling_now = bool(settings and settings[-1] == (month, True))
        preceding_month = month_of(first - timedelta(days=1))
        descendants = {category_id}
        pending = [category_id]
        while pending:
            kids = children.get(pending.pop(), [])
            descendants.update(kids)
            pending.extend(kids)
        while cursor < first:
            current_month = month_of(cursor)
            if reset_month == current_month:
                balance = ZERO
            while setting_index < len(settings) and settings[setting_index][0] <= current_month:
                active = settings[setting_index][1]
                setting_index += 1
            next_month = month_of(parse_month(current_month)[1] + timedelta(days=1))
            # An opt-in effective in the next month immediately carries this
            # month's final result, even if carryover was previously off.
            if setting_index < len(settings) and settings[setting_index] == (next_month, True):
                active = True
            if enabling_now and current_month == preceding_month:
                active = True
            next_cursor = (parse_month(current_month)[1] + timedelta(days=1))
            if active:
                direct = self.amounts_for(current_month).get(category_id)
                if direct:
                    amount, _, period, percent = direct
                    if period:
                        amount = self._rolling_average(category_id, current_month, period, children, {})
                    elif percent is not None:
                        amount = self.budgeting_income(current_month)
                        if amount is not None:
                            amount = amount * percent / Decimal(100)
                    start, end = parse_month(current_month)
                    spent = self._owned_spending(start, end)
                    actual = sum((spent.get(cid, ZERO) for cid in descendants), ZERO)
                    balance = (amount or ZERO) + balance - actual
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
                old = current.get(category_id, (None, False, None, None))
                if old[0] == value and old[2] == period and old[3] is None:
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
                         children: dict[int, list[int]], cache: dict[tuple[int, int], Decimal | None]) -> Decimal | None:
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
            actual = self._owned_spending(start, end)
            total += sum((actual.get(cid, ZERO) for cid in descendants), ZERO)
            cursor = start
        observed = 0
        cursor = parse_month(month)[0]
        for _ in range(months):
            start, end = parse_month((cursor - timedelta(days=1)).strftime("%Y-%m"))
            amounts = self._owned_spending(start, end)
            if any(cid in amounts for cid in descendants):
                observed += 1
            cursor = start
        cache[key] = (total / observed).quantize(Decimal("0.01")) if observed else None
        return cache[key]

    def background_estimates(self, month: str) -> list[dict]:
        """Monthly expectations for untracked spending categories: the average of the last three
        completed months that had spending. They count in the month's plan (owner decision
        2026-10-03); an estimate from one observed month is low confidence and the screens say so.
        Categories that are tracked, one-off, have children, or sit under a parent's own limit
        (covered) are left out, so nothing is counted twice."""
        view = self.month_view(month)
        tracked = {line.category_id for section in view.sections for line in section.lines
                   if line.direct is not None or line.average_months or line.income_percent is not None}
        tracked |= self._id_list("budget_tracked_categories") or set()
        exclusions = self.one_off_ids(with_children=False)
        categories = self.categories.tree(Movement.OUTFLOW)
        by_id = {category.id: category for category in categories}
        children: dict[int, list[int]] = {}
        for category in categories:
            if category.parent_id:
                children.setdefault(category.parent_id, []).append(category.id)
        groups = {group.category_id for section in view.sections for group in section.groups}
        months, cursor = [], parse_month(month)[0]
        for _ in range(3):  # the three completed months before this one, newest first
            start, end = parse_month((cursor - timedelta(days=1)).strftime("%Y-%m"))
            months.append(self._owned_spending(start, end))
            cursor = start
        estimates, cache = [], {}
        for section in view.sections:
            for line in section.lines:
                if (line.depth <= 1 or line.category_id in tracked or line.covered
                        or children.get(line.category_id) or line.category_id in exclusions):
                    continue
                estimate = self._rolling_average(line.category_id, month, 3, children, cache)
                if estimate is None:
                    continue
                parent = by_id.get(line.category_id)
                while parent and parent.depth > 1 and parent.parent_id:
                    parent = by_id.get(parent.parent_id)
                if not parent or parent.id not in groups:
                    continue
                tree, pending = {line.category_id}, [line.category_id]
                while pending:
                    kids = children.get(pending.pop(), [])
                    tree.update(kids)
                    pending.extend(kids)
                observed = sum(1 for amounts in months if any(cid in amounts for cid in tree))
                estimates.append({"category_id": line.category_id, "name": line.name, "group_id": parent.id,
                                  "estimate": estimate, "observed": observed, "low_confidence": observed <= 1})
        return estimates

    def plan_summary(self, month: str) -> dict:
        """The month's plan as every screen shows it: Planned (limits plus background estimates),
        Spent (owned spending, one-off categories left out) and Left in plan."""
        view = self.month_view(month)
        estimates = self.background_estimates(month)
        planned = view.available + sum((e["estimate"] for e in estimates), ZERO)
        first, last = parse_month(month)
        one_offs = self.one_off_ids()
        spent = sum((v for cid, v in self._owned_spending(first, last).items() if cid not in one_offs), ZERO)
        return {"planned": planned, "spent": spent, "left": planned - spent, "estimates": estimates,
                "low_confidence": [e for e in estimates if e["low_confidence"]]}

    def set_income_percentage(self, category_id: int, month: str, percent: object,
                              only_this_month: bool = False) -> bool:
        parse_month(month); category = self._budgetable(category_id)
        value = check_places(to_decimal(percent, "percentage"), 2, "percentage")
        if value < ZERO or value > 10000:
            raise ValidationError("Enter an income percentage from 0 to 10,000.", "percentage")
        rows = self.repo.entries_up_to(month)
        prior = next((row for row in reversed(rows) if row.category_id == category_id and not row.one_off
                      and row.month < month), None)
        previous = ((prior.amount, prior.average_months, prior.income_percent) if prior else (None, None, None))
        desired = (None, None, value)
        with self.db.transaction():
            if only_this_month:
                if previous == desired:
                    self.repo.delete(category_id, month, True)
                else:
                    self.repo.upsert(category_id, month, True, None, None, value)
            else:
                self.repo.delete(category_id, month, True)
                if previous == desired:
                    self.repo.delete(category_id, month, False)
                else:
                    self.repo.upsert(category_id, month, False, None, None, value)
        return True

    def reset_carryover(self, category_id: int, month: str) -> None:
        """Set a dated boundary clearing carryover from this month onward."""
        parse_month(month)
        self._budgetable(category_id)
        if category_id not in self.amounts_for(month):
            raise ValidationError("Reset carryover is available for tracked categories only.")
        self.repo.reset(category_id, month)

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
