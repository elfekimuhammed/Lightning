"""ReportingService — net worth, the net-worth bridge, cash flow, spending, statements.

Everything is derived from ledger lines; nothing here writes to the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from lightning.accounts.domain import SIDEBAR_GROUPS, Account
from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.categories.domain import IncomeClass, Scope
from lightning.categories.service import CategoryService
from lightning.core.dates import fmt_date, parse_date, parse_month, previous_day
from lightning.core.money import ZERO, from_e6
from lightning.core.refs import DOC_LABELS, DocType
from lightning.database.connection import Database

from .queries import ReportQueries
from .valuation import Valuer


# ---------------------------------------------------------------------------- results
@dataclass
class HoldingValue:
    account: Account
    asset_code: str
    asset_class_code: str
    asset_class_label: str
    quantity: Decimal
    value: Decimal | None
    asset_id: int = 0
    price: Decimal | None = None
    price_date: str | None = None
    price_source: str = ""


@dataclass
class Group:
    code: str
    label: str
    value: Decimal
    children: list["Group"] = field(default_factory=list)
    id: int | None = None  # set for account rows in the sidebar


@dataclass
class NetWorth:
    as_of: str
    total: Decimal
    by_account: list[tuple[Account, Decimal]]
    by_class: list[Group]
    unvalued: list[str]


@dataclass
class Bridge:
    """closing = opening + inflows - outflows + revaluation + new_balances  (difference must be 0)."""

    date_from: str
    date_to: str
    opening: Decimal
    inflows: Decimal
    outflows: Decimal
    revaluation: Decimal
    new_balances: Decimal
    closing: Decimal

    @property
    def change(self) -> Decimal:
        return self.closing - self.opening

    @property
    def expected_closing(self) -> Decimal:
        return self.opening + self.inflows - self.outflows + self.revaluation + self.new_balances

    @property
    def difference(self) -> Decimal:
        return self.closing - self.expected_closing


@dataclass
class CashFlow:
    date_from: str
    date_to: str
    inflows: Decimal
    household_inflows: Decimal
    investment_inflows: Decimal
    outflows: Decimal
    personal_outflows: Decimal
    work_outflows: Decimal

    @property
    def net(self) -> Decimal:
        return self.inflows - self.outflows


@dataclass
class StatementRow:
    date: str
    txn_id: int
    ref: str
    type: str
    type_label: str
    counterparty: str
    description: str
    notes: str
    category_label: str  # plain names, or "Transfer ↔ <account>"
    amount: Decimal  # + deposit / - payment
    balance: Decimal | None  # running balance (single-account view only)
    account_id: int = 0
    account_label: str = ""
    category_id: int | None = None
    other_account_id: int | None = None
    other_account_label: str = ""

    @property
    def payment(self) -> Decimal | None:
        return -self.amount if self.amount < 0 else None

    @property
    def deposit(self) -> Decimal | None:
        return self.amount if self.amount > 0 else None


@dataclass
class Statement:
    account: Account
    date_from: str
    date_to: str
    opening: Decimal
    rows: list[StatementRow]
    closing: Decimal


# ---------------------------------------------------------------------------- service
class ReportingService:
    def __init__(self, db: Database, accounts: AccountService, assets: AssetService,
                 categories: CategoryService, base_currency: str):
        self.q = ReportQueries(db)
        self.accounts = accounts
        self.assets = assets
        self.categories = categories
        self.base_currency = base_currency
        self.valuer = Valuer(self.q, base_currency)

    # -- holdings & net worth ---------------------------------------------
    def holdings(self, as_of: date | str) -> tuple[list[HoldingValue], list[str]]:
        day = self._day(as_of)
        result, unvalued = [], []
        for row in self.q.holdings(day):
            quantity = from_e6(row["quantity_e6"])
            if quantity == ZERO:
                continue
            account = self.accounts.get(row["account_id"])
            asset = self.assets.get_asset(row["asset_id"])
            class_id = account.cash_class_id if asset.is_cash else asset.asset_class_id
            asset_class = self.assets.get_class(class_id)
            valuation = self.valuer.value(asset, quantity, day)
            if valuation.value is None:
                unvalued.append(f"{account.label} — {valuation.reason}")
            result.append(HoldingValue(account, asset.code, asset_class.code, asset_class.name, quantity,
                                       valuation.value, asset.id, valuation.price, valuation.price_date,
                                       valuation.source))
        return result, unvalued

    def net_worth(self, as_of: date | str) -> NetWorth:
        day = self._day(as_of)
        holdings, unvalued = self.holdings(day)
        by_account: dict[int, tuple[Account, Decimal]] = {}
        roots: dict[str, Group] = {}
        for h in holdings:
            value = h.value or ZERO
            acc, total = by_account.get(h.account.id, (h.account, ZERO))
            by_account[h.account.id] = (acc, total + value)
            root = self.assets.get_class_by_code(h.asset_class_code.split(".")[0])
            group = roots.setdefault(root.code, Group(root.code, root.name, ZERO))
            group.value += value
            if h.asset_class_code != root.code:
                child = next((c for c in group.children if c.code == h.asset_class_code), None)
                if child is None:
                    child = Group(h.asset_class_code, h.asset_class_label, ZERO)
                    group.children.append(child)
                child.value += value
        # include active accounts with zero balance so the dashboard lists every account
        for account in self.accounts.list(active_only=True):
            by_account.setdefault(account.id, (account, ZERO))
        order = {c.code: i for i, c in enumerate(self.assets.list_classes())}
        by_class = sorted(roots.values(), key=lambda g: order.get(g.code, 999))
        for g in by_class:
            g.children.sort(key=lambda c: order.get(c.code, 999))
        accounts_sorted = sorted(by_account.values(), key=lambda item: (item[0].sort_order, item[0].code))
        total = sum((v for _, v in accounts_sorted), ZERO)
        return NetWorth(day, total, accounts_sorted, by_class, unvalued)

    def account_balance(self, account_id: int, as_of: date | str | None = None) -> Decimal:
        return from_e6(self.q.account_quantity(account_id, as_of=self._day(as_of) if as_of else None))

    # -- the net-worth equation --------------------------------------------
    def bridge(self, date_from: date | str, date_to: date | str) -> Bridge:
        start, end = parse_date(date_from), parse_date(date_to)
        before = fmt_date(previous_day(start))
        opening = self.net_worth(before).total
        closing = self.net_worth(end).total
        totals = self.q.effect_totals(fmt_date(start), fmt_date(end))
        inflows = from_e6(totals.get("INFLOW", 0))
        outflows = -from_e6(totals.get("OUTFLOW", 0))
        new_balances = from_e6(totals.get("OPENING", 0))
        revaluation = self._revaluation(before, fmt_date(start), fmt_date(end))
        return Bridge(fmt_date(start), fmt_date(end), opening, inflows, outflows, revaluation, new_balances, closing)

    def bridge_for_month(self, month: str) -> Bridge:
        first, last = parse_month(month)
        return self.bridge(first, last)

    def _revaluation(self, before: str, start: str, end: str) -> Decimal:
        """Per holding: value change not explained by money moving in or out of it.

        Base-currency cash is always exactly zero. From M3/M4 this captures price and FX moves.
        """
        start_values = {(h.account.id, h.asset_code): h.value or ZERO for h in self.holdings(before)[0]}
        end_values = {(h.account.id, h.asset_code): h.value or ZERO for h in self.holdings(end)[0]}
        flows: dict[tuple[int, str], Decimal] = {}
        for row in self.q.flows_by_holding(start, end):
            key = (row["account_id"], self.assets.get_asset(row["asset_id"]).code)
            flows[key] = from_e6(row["amount_base_e6"])
        total = ZERO
        for key in set(start_values) | set(end_values) | set(flows):
            total += end_values.get(key, ZERO) - start_values.get(key, ZERO) - flows.get(key, ZERO)
        return total

    # -- cash flow & spending ----------------------------------------------
    def cash_flow(self, date_from: date | str, date_to: date | str) -> CashFlow:
        start, end = self._day(date_from), self._day(date_to)
        inflow = household = investment = outflow = personal = work = ZERO
        for row in self.q.category_totals(start, end):
            amount = from_e6(row["total"])
            cat = self.categories.get(row["category_id"])
            if row["effect"] == "INFLOW":
                inflow += amount
                if cat.income_class == IncomeClass.INVESTMENT:
                    investment += amount
                else:
                    household += amount
            else:
                outflow -= amount
                if cat.scope == Scope.WORK:
                    work -= amount
                else:
                    personal -= amount
        return CashFlow(start, end, inflow, household, investment, outflow, personal, work)

    def money_out_by_category(self, date_from: date | str, date_to: date | str) -> dict[int, Decimal]:
        """Money out per category (positive; refunds reduce it), for the category itself only."""
        start, end = self._day(date_from), self._day(date_to)
        return {row["category_id"]: -from_e6(row["total"])
                for row in self.q.category_totals(start, end) if row["effect"] == "OUTFLOW"}

    def spending_by_category(self, date_from: date | str, date_to: date | str, depth: int = 2) -> list[Group]:
        """Outflows rolled up to a tree depth (1 = Personal/Work, 2 = Food, Transport, ...)."""
        start, end = self._day(date_from), self._day(date_to)
        groups: dict[str, Group] = {}
        for row in self.q.category_totals(start, end):
            if row["effect"] != "OUTFLOW":
                continue
            cat = self.categories.get(row["category_id"])
            parts = cat.code.split(".")
            code = ".".join(parts[: depth + 1])
            label_cat = self.categories.get_by_code(code)
            group = groups.setdefault(code, Group(code, self.categories.display_name(label_cat.id), ZERO))
            group.value -= from_e6(row["total"])
        return sorted((g for g in groups.values() if g.value != ZERO), key=lambda g: g.value, reverse=True)

    def monthly_trend(self, end_month: str, months: int = 6) -> list[dict]:
        _, last = parse_month(end_month)
        first = last.replace(day=1)
        for _ in range(months - 1):
            first = (first - timedelta(days=1)).replace(day=1)
        data: dict[str, dict] = {}
        cursor = first
        while cursor <= last:
            key = cursor.strftime("%Y-%m")
            data[key] = {"month": key, "inflows": ZERO, "outflows": ZERO}
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        for row in self.q.monthly_effects(fmt_date(first), fmt_date(last)):
            if row["month"] not in data:
                continue
            if row["effect"] == "INFLOW":
                data[row["month"]]["inflows"] += from_e6(row["total"])
            elif row["effect"] == "OUTFLOW":
                data[row["month"]]["outflows"] -= from_e6(row["total"])
        for item in data.values():
            item["net"] = item["inflows"] - item["outflows"]
        return list(data.values())

    # -- account statement & register ------------------------------------
    def statement(self, account_id: int, date_from: date | str, date_to: date | str) -> Statement:
        """One account, oldest first, with a running balance."""
        account = self.accounts.get(account_id)
        start, end = self._day(date_from), self._day(date_to)
        opening = from_e6(self.q.account_quantity(account_id, before=start))
        rows = self._rows(self.q.statement_lines(account_id, start, end), opening)
        closing = rows[-1].balance if rows else opening
        return Statement(account, start, end, opening, rows, closing)

    def register(self, account_id: int | None, date_from: date | str, date_to: date | str,
                 txn_ids: set[int] | None = None) -> list[StatementRow]:
        """Rows for the register view, newest first.

        One account: running balance included. All accounts (account_id None): one row per account touched.
        ``txn_ids`` limits rows to a search result; running balances are then left out (they would mislead).
        """
        start, end = self._day(date_from), self._day(date_to)
        opening = from_e6(self.q.account_quantity(account_id, before=start)) if account_id else None
        rows = self._rows(self.q.statement_lines(account_id, start, end),
                          opening if txn_ids is None else None)
        if txn_ids is not None:
            rows = [r for r in rows if r.txn_id in txn_ids]
        return list(reversed(rows))

    def _rows(self, lines: list[dict], opening: Decimal | None) -> list[StatementRow]:
        running = opening
        rows = []
        for r in lines:
            amount = from_e6(r["quantity_e6"])
            if running is not None:
                running += amount
            other_label = self.accounts.get(r["other_account_id"]).label if r["other_account_id"] else ""
            if r["type"] in ("BUY", "SEL") and r["memo"]:
                category = r["memo"]
            elif r["category_id"]:
                category = self.categories.display_name(r["category_id"])
            elif r["type"] == "TRF":
                category = "Transfer"
            else:
                category = DOC_LABELS[DocType(r["type"])]
            rows.append(StatementRow(
                r["date"], r["txn_id"], r["ref"], r["type"], DOC_LABELS[DocType(r["type"])], r["counterparty"],
                r["description"], r["notes"], category, amount, running, r["account_id"],
                self.accounts.get(r["account_id"]).label, r["category_id"], r["other_account_id"], other_label))
        return rows

    def sidebar(self, as_of: date | str) -> tuple[Decimal, list[Group]]:
        """All-accounts total and active accounts grouped by kind (Cash & bank, Deposits, Investments, Other).
        An account's value includes its holdings at market value."""
        nw = self.net_worth(as_of)
        groups: dict[str, Group] = {}
        for account, value in nw.by_account:
            if not account.active:
                continue
            name = SIDEBAR_GROUPS[account.account_type]
            group = groups.setdefault(name, Group(name, name, ZERO))
            group.value += value
            group.children.append(Group(account.code, account.name, value, id=account.id))
        order = list(dict.fromkeys(SIDEBAR_GROUPS.values()))
        return nw.total, sorted(groups.values(), key=lambda g: order.index(g.code))

    def investment_lines(self, as_of: date | str, account_id: int | None = None) -> list[dict]:
        """Posted lines of investments (and dividends), oldest first — the input for positions."""
        return self.q.investment_lines(self._day(as_of), account_id)

    def value_of(self, asset_id: int, quantity: Decimal, as_of: date | str):
        """Market value of units of an asset on a date (see Valuer for where the price comes from)."""
        return self.valuer.value(self.assets.get_asset(asset_id), quantity, self._day(as_of))

    def account_value(self, account_id: int, as_of: date | str) -> Decimal:
        """Cash plus holdings at market value."""
        holdings, _ = self.holdings(as_of)
        return sum((h.value or ZERO for h in holdings if h.account.id == account_id), ZERO)

    def first_date(self) -> str | None:
        return self.q.first_entry_date()

    @staticmethod
    def _day(value: date | str) -> str:
        return fmt_date(parse_date(value))
