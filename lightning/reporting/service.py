"""ReportingService — net worth, the net-worth bridge, cash flow, spending, statements.

Everything is derived from ledger lines; nothing here writes to the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from lightning.accounts.domain import SIDEBAR_GROUPS, Account, AccountType
from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.categories.domain import CategoryFamily, IncomeClass, Scope
from lightning.categories.service import CategoryService
from lightning.core.dates import fmt_date, parse_date, parse_month, previous_day
from lightning.core.memo import request_cached
from lightning.core.money import ZERO, from_e6
from lightning.money_from_others import MoneyFromOthersService
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
    custody_change: Decimal = ZERO

    @property
    def change(self) -> Decimal:
        return self.closing - self.opening

    @property
    def expected_closing(self) -> Decimal:
        return self.opening + self.inflows - self.outflows + self.revaluation + self.new_balances + self.custody_change

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
    investment_outflows: Decimal

    @property
    def net(self) -> Decimal:
        """Net flow = Money in − Money out."""
        return self.inflows - self.outflows

    @property
    def savings_rate(self) -> Decimal | None:
        """Savings rate = Net flow ÷ Money in, as a percentage; None without money in."""
        return self.net / self.inflows * 100 if self.inflows > ZERO else None


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
def flow_of(effect: str, amount: Decimal, category) -> tuple[Decimal, Decimal]:
    """The one rule for Money in and Money out (every report, chart and budget uses it).

    ``amount`` is a ledger line's signed base amount. A line with the income effect in a category with
    an income class is Money in. Every other categorised line is spending: a payment (negative amount)
    adds to Money out, and a refund (positive amount, whichever effect it was recorded with) takes
    from it. Returns (money_in, money_out); one of them is zero."""
    if effect == "INFLOW" and category.income_class is not None:
        return amount, ZERO
    return ZERO, -amount


class ReportingService:
    def __init__(self, db: Database, accounts: AccountService, assets: AssetService,
                 categories: CategoryService, base_currency: str, money_from_others: MoneyFromOthersService):
        self.q = ReportQueries(db)
        self.accounts = accounts
        self.assets = assets
        self.categories = categories
        self.base_currency = base_currency
        self.money_from_others = money_from_others
        self.valuer = Valuer(self.q, base_currency)

    # -- holdings & net worth ---------------------------------------------
    def holdings(self, as_of: date | str) -> tuple[list[HoldingValue], list[str]]:
        return self._holdings(self._day(as_of))

    @request_cached
    def _holdings(self, day: str) -> tuple[list[HoldingValue], list[str]]:
        result, unvalued = [], []
        # Resolve ledger metadata in batches. The previous loop performed three
        # point reads for every account/asset pair even when many rows shared
        # the same account, asset, or class.
        accounts = {item.id: item for item in self.accounts.list()}
        assets = {item.id: item for item in self.assets.list_assets()}
        classes = {item.id: item for item in self.assets.list_classes()}
        for row in self.q.holdings(day):
            quantity = from_e6(row["quantity_e6"])
            if quantity == ZERO:
                continue
            account = accounts[row["account_id"]]
            asset = assets[row["asset_id"]]
            class_id = account.cash_class_id if asset.is_cash else asset.asset_class_id
            asset_class = classes[class_id]
            valuation = self.valuer.value(asset, quantity, day)
            if valuation.value is None:
                unvalued.append(f"{account.label} — {valuation.reason}")
            result.append(HoldingValue(account, asset.code, asset_class.code, asset_class.name, quantity,
                                       valuation.value, asset.id, valuation.price, valuation.price_date,
                                       valuation.source))
        return result, unvalued

    def stale_prices(self, as_of: date | str, days: int = 62) -> list[dict]:
        """Holdings valued from a price older than ``days`` (about two months): honest numbers need a
        recent price. Cash, holdings valued at what you paid and certificates (valued at principal)
        are left out: there is no market price to update. One entry per asset, oldest first."""
        day = self._day(as_of)
        cutoff = fmt_date(parse_date(day) - timedelta(days=days))
        stale: dict[int, dict] = {}
        for holding in self.holdings(day)[0]:
            if (holding.price_date is None or holding.price_source in ("CASH", "COST")
                    or holding.asset_class_code.startswith("DEPOSIT") or holding.price_date >= cutoff):
                continue
            asset = self.assets.get_asset(holding.asset_id)
            stale.setdefault(holding.asset_id, {"asset_id": holding.asset_id, "name": asset.name,
                                                "price_date": holding.price_date})
        return sorted(stale.values(), key=lambda row: (row["price_date"], row["name"]))

    def net_worth(self, as_of: date | str) -> NetWorth:
        return self._net_worth(self._day(as_of))

    @request_cached
    def _net_worth(self, day: str) -> NetWorth:
        holdings, unvalued = self.holdings(day)
        by_account: dict[int, tuple[Account, Decimal]] = {}
        roots: dict[str, Group] = {}
        classes_by_code = {item.code: item for item in self.assets.list_classes()}
        for h in holdings:
            value = h.value or ZERO
            acc, total = by_account.get(h.account.id, (h.account, ZERO))
            by_account[h.account.id] = (acc, total + value)
            root = classes_by_code[h.asset_class_code.split(".")[0]]
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
        custody, custody_unvalued = self._money_from_others_value(day)
        total -= custody
        unvalued.extend(custody_unvalued)
        if custody:
            by_class.append(Group("CUSTODY", "Less: money from others", -custody))
        return NetWorth(day, total, accounts_sorted, by_class, unvalued)

    def owned_liquid_cash(self, as_of: date | str) -> Decimal:
        """Owned wallet, bank, and brokerage cash; excludes custody balances and locked assets."""
        return (sum((self.owned_account_value(account.id, as_of) for account in self.accounts.list()
                     if account.account_type in {AccountType.CASH, AccountType.BANK}), ZERO)
                + self.owned_brokerage_cash(as_of))

    def owned_brokerage_cash(self, as_of: date | str) -> Decimal:
        """Cash inside brokerage accounts, valued at face value and excluded from spendable cash."""
        return sum((row["value"] or ZERO for row in self.owned_brokerage_cash_by_account(as_of)), ZERO)

    def owned_brokerage_cash_by_account(self, as_of: date | str) -> list[dict]:
        """Owned brokerage cash at an account boundary, for reconciled detail views."""
        return [dict(row) for row in self._owned_brokerage_cash_by_account(self._day(as_of))]

    @request_cached
    def _owned_brokerage_cash_by_account(self, day: str) -> list[dict]:
        rows = []
        for account in self.accounts.list(active_only=True):
            if account.account_type != AccountType.BROKERAGE:
                continue
            amount = max(ZERO, self.account_balance(account.id, day)
                         - self.money_from_others.cash_total_for_account(account.id, day))
            valuation = self.valuer.value(self.assets.cash_asset(account.currency), amount, day)
            rows.append({"id": account.id, "label": account.label, "value": valuation.value})
        return rows

    @request_cached
    def opening_balances_between(self, start: date | str, end: date | str) -> Decimal:
        """What you recorded as already owned (opening balances and existing holdings, at their recorded
        value) between two dates. Recording something you had is not a change in what you own."""
        return from_e6(self.q.opening_total(self._day(start), self._day(end)))

    @request_cached
    def first_activity_date(self) -> str | None:
        return self.q.first_entry_date()

    def money_from_others_total(self, as_of: date | str) -> Decimal:
        return self._money_from_others_value(as_of)[0]

    def money_from_others_by_owner(self, as_of: date | str) -> list[dict]:
        day = self._day(as_of)
        grouped: dict[tuple[str, str, int], dict] = {}
        for row in self.money_from_others.by_owner(day):
            key = (row["owner"], row["currency"], row["account_id"])
            grouped[key] = dict(row)
        for pos in self.money_from_others.investment_positions(day):
            asset = self.assets.get_asset(pos["asset_id"])
            valuation = self.valuer.value(asset, pos["units"], day)
            if valuation.value is None:
                continue
            account = self.accounts.get(pos["account_id"])
            key = (pos["owner"], self.base_currency, pos["account_id"])
            row = grouped.setdefault(key, {"owner": pos["owner"], "currency": self.base_currency,
                                           "account_id": pos["account_id"], "account_name": account.name,
                                           "amount": ZERO})
            row["amount"] += valuation.value
        return sorted(grouped.values(), key=lambda row: (row["owner"].casefold(), row["account_name"].casefold()))

    def money_from_others_history(self, limit: int = 100) -> list[dict]:
        return self.money_from_others.history(limit)

    def money_from_others_investments(self, as_of: date | str) -> list[dict]:
        day = self._day(as_of)
        rows = []
        for pos in self.money_from_others.investment_positions(day):
            asset = self.assets.get_asset(pos["asset_id"])
            account = self.accounts.get(pos["account_id"])
            valuation = self.valuer.value(asset, pos["units"], day)
            rows.append({"owner": pos["owner"], "account_name": account.name, "asset_name": asset.name,
                         "units": pos["units"], "unit": asset.unit, "value": valuation.value,
                         "currency": self.base_currency})
        return sorted(rows, key=lambda row: (row["owner"].casefold(), row["asset_name"].casefold()))

    def _money_from_others_value(self, as_of: date | str) -> tuple[Decimal, list[str]]:
        return self._money_from_others_value_on(self._day(as_of))

    @request_cached
    def _money_from_others_value_on(self, day: str) -> tuple[Decimal, list[str]]:
        totals = self.money_from_others.totals_by_account(day)
        total, unvalued = ZERO, []
        for row in totals:
            account = self.accounts.get(row["account_id"])
            local_amount = from_e6(row["amount_e6"])
            valuation = self.valuer.value(self.assets.cash_asset(account.currency), local_amount, day)
            if valuation.value is None:
                unvalued.append(f"Money from others — {account.label}: {valuation.reason}")
            else:
                total += valuation.value
        for position in self.money_from_others.investment_positions(day):
            asset = self.assets.get_asset(position["asset_id"])
            account = self.accounts.get(position["account_id"])
            valuation = self.valuer.value(asset, position["units"], day)
            if valuation.value is None:
                unvalued.append(f"Money from others — {position['owner']} / {asset.name}: {valuation.reason}")
            else:
                total += valuation.value
        return total, unvalued

    def custody_value_by_account(self, as_of: date | str) -> dict[int, Decimal]:
        """Market value held for others, partitioned by account for gross/owned comparisons."""
        return self._custody_value_by_account(self._day(as_of))

    @request_cached
    def _custody_value_by_account(self, day: str) -> dict[int, Decimal]:
        values: dict[int, Decimal] = {}
        for row in self.money_from_others.totals_by_account(day):
            account = self.accounts.get(row["account_id"])
            valuation = self.valuer.value(self.assets.cash_asset(account.currency), from_e6(row["amount_e6"]), day)
            if valuation.value is not None:
                values[account.id] = values.get(account.id, ZERO) + valuation.value
        for position in self.money_from_others.investment_positions(day):
            valuation = self.valuer.value(self.assets.get_asset(position["asset_id"]), position["units"], day)
            if valuation.value is not None:
                account_id = position["account_id"]
                values[account_id] = values.get(account_id, ZERO) + valuation.value
        return values

    def owned_account_value(self, account_id: int, as_of: date | str) -> Decimal:
        return self.account_value(account_id, as_of) - self.custody_value_by_account(as_of).get(account_id, ZERO)

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
        custody_change = -(self.money_from_others_total(end) - self.money_from_others_total(before))
        return Bridge(fmt_date(start), fmt_date(end), opening, inflows, outflows, revaluation, new_balances, closing,
                      custody_change)

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
        inflow = household = investment = outflow = personal = work = investment_out = ZERO
        for row in self.q.category_totals(start, end):
            cat = self.categories.get(row["category_id"])
            money_in, signed_outflow = flow_of(row["effect"], from_e6(row["total"]), cat)
            if money_in:
                inflow += money_in
                if cat.family == CategoryFamily.INVESTMENT or cat.income_class == IncomeClass.INVESTMENT:
                    investment += money_in
                else:
                    household += money_in
            else:
                outflow += signed_outflow
                if cat.family == CategoryFamily.INVESTMENT:
                    investment_out += signed_outflow
                elif cat.family == CategoryFamily.WORK or cat.scope == Scope.WORK:
                    work += signed_outflow
                else:
                    personal += signed_outflow
        return CashFlow(start, end, inflow, household, investment, outflow, personal, work, investment_out)

    def flows_by_date(self, date_from: date | str, date_to: date | str, by: str = "day",
                      code_prefix: str = "") -> dict[str, dict]:
        """Money in, money out and net flow per day (``by="day"``) or month (``"month"``), counted the
        way cash_flow counts them; days with nothing are left out. ``spending`` is money out limited to
        categories under ``code_prefix`` (all of it when empty)."""
        start, end = self._day(date_from), self._day(date_to)
        out: dict[str, dict] = {}
        for row in self.q.category_totals_by_date(start, end, 10 if by == "day" else 7):
            cat = self.categories.get(row["category_id"])
            item = out.setdefault(row["key"], {"inflows": ZERO, "outflows": ZERO, "spending": ZERO})
            money_in, signed_outflow = flow_of(row["effect"], from_e6(row["total"]), cat)
            if money_in:
                item["inflows"] += money_in
                continue
            item["outflows"] += signed_outflow
            if not code_prefix or cat.code.startswith(code_prefix):
                item["spending"] += signed_outflow
        for item in out.values():
            item["net"] = item["inflows"] - item["outflows"]
        return out

    def money_out_by_category(self, date_from: date | str, date_to: date | str) -> dict[int, Decimal]:
        """Money out per category (positive; refunds reduce it), for the category itself only."""
        return self._money_out_by_category(self._day(date_from), self._day(date_to))

    @request_cached
    def _money_out_by_category(self, start: str, end: str) -> dict[int, Decimal]:
        totals: dict[int, Decimal] = {}
        for row in self.q.category_totals(start, end):
            money_in, money_out = flow_of(row["effect"], from_e6(row["total"]), self.categories.get(row["category_id"]))
            if not money_in:
                totals[row["category_id"]] = totals.get(row["category_id"], ZERO) + money_out
        return totals

    def money_in_by_category(self, date_from: date | str, date_to: date | str) -> list[Group]:
        """Income by category, excluding custody and expense refunds."""
        start, end = self._day(date_from), self._day(date_to)
        totals: dict[int, Decimal] = {}
        for row in self.q.category_totals(start, end):
            category = self.categories.get(row["category_id"])
            money_in, _ = flow_of(row["effect"], from_e6(row["total"]), category)
            if money_in:
                totals[category.id] = totals.get(category.id, ZERO) + money_in
        groups = []
        for category_id, value in sorted(totals.items(), key=lambda item: -item[1]):
            category = self.categories.get(category_id)
            groups.append(Group(category.code, self.categories.display_name(category_id), value))
        return groups

    def monthly_flow_between(self, date_from: date | str, date_to: date | str) -> list[dict]:
        """Income and net expenses grouped by month for an exact date range."""
        first, last = parse_date(date_from), parse_date(date_to)
        cursor = first.replace(day=1)
        data: dict[str, dict] = {}
        while cursor <= last:
            key = cursor.strftime("%Y-%m")
            month_end = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            data[key] = {"month": key, "inflows": ZERO, "outflows": ZERO,
                         "date_from": fmt_date(max(first, cursor)), "date_to": fmt_date(min(last, month_end))}
            if cursor.year == 9999 and cursor.month == 12:
                break
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        # The same rows and rule as cash_flow, so a chart's month always equals the card for that month.
        for key, flow in self.flows_by_date(first, last, "month").items():
            if key in data:
                data[key]["inflows"], data[key]["outflows"] = flow["inflows"], flow["outflows"]
        for item in data.values():
            item["net"] = item["inflows"] - item["outflows"]
        return list(data.values())

    def spending_by_category(self, date_from: date | str, date_to: date | str, depth: int = 2) -> list[Group]:
        """Outflows rolled up to a tree depth (1 = Personal/Work, 2 = Food, Transport, ...)."""
        start, end = self._day(date_from), self._day(date_to)
        groups: dict[str, Group] = {}
        for row in self.q.category_totals(start, end):
            cat = self.categories.get(row["category_id"])
            money_in, money_out = flow_of(row["effect"], from_e6(row["total"]), cat)
            if money_in:
                continue
            parts = cat.code.split(".")
            code = ".".join(parts[: depth + 1])
            label_cat = self.categories.get_by_code(code)
            group = groups.setdefault(code, Group(code, self.categories.display_name(label_cat.id), ZERO))
            group.value += money_out
        return sorted((g for g in groups.values() if g.value != ZERO), key=lambda g: g.value, reverse=True)

    def _spending(self, date_from, date_to) -> list[dict]:
        """Spending lines (positive = spent; a refund in an expense category is negative), the same
        lines that make up spending_by_category."""
        start, end = self._day(date_from), self._day(date_to)
        out = []
        for row in self.q.spending_lines(start, end):
            money_in, money_out = flow_of(row["effect"], from_e6(row["amount"]), self.categories.get(row["category_id"]))
            if not money_in:
                out.append(row | {"value": money_out})
        return out

    def spending_by_counterparty(self, date_from, date_to) -> list[tuple[str, Decimal]]:
        """Money out per counterparty (who you paid), largest first."""
        totals: dict[str, Decimal] = {}
        for row in self._spending(date_from, date_to):
            name = (row["counterparty"] or row["description"] or "No counterparty").strip()
            totals[name] = totals.get(name, ZERO) + row["value"]
        return sorted(((k, v) for k, v in totals.items() if v > ZERO), key=lambda kv: -kv[1])

    def spending_by_account(self, date_from, date_to) -> list[tuple[int, Decimal]]:
        """Money out per account it was paid from, largest first."""
        totals: dict[int, Decimal] = {}
        for row in self._spending(date_from, date_to):
            totals[row["account_id"]] = totals.get(row["account_id"], ZERO) + row["value"]
        return sorted(((k, v) for k, v in totals.items() if v > ZERO), key=lambda kv: -kv[1])

    def largest_payments(self, date_from, date_to, limit: int = 5) -> list[dict]:
        """The biggest single payments in the period."""
        by_txn: dict[int, dict] = {}
        for row in self._spending(date_from, date_to):
            entry = by_txn.setdefault(row["transaction_id"], {"id": row["transaction_id"], "date": row["date"],
                                                              "ref": row["ref"], "counterparty": row["counterparty"] or row["description"] or "",
                                                              "category_id": row["category_id"], "value": ZERO})
            entry["value"] += row["value"]
        return sorted((e for e in by_txn.values() if e["value"] > ZERO), key=lambda e: -e["value"])[:limit]

    def spending_vs_usual(self, date_from, date_to, months: int = 3, history: int = 6, depth: int = 2) -> list[dict]:
        """Each category's spending in the period against its usual month: the average of the
        ``months`` whole months before the period (only months after the first record count). Also
        the last ``history`` months for a mini trend. Largest first."""
        start, end = parse_date(self._day(date_from)), parse_date(self._day(date_to))
        first_record = self.first_activity_date()
        floor = parse_date(first_record).replace(day=1) if first_record else start

        def month_range(back_from: date, back: int) -> tuple[date, date]:
            index = back_from.year * 12 + back_from.month - 1 - back
            first = date(index // 12, index % 12 + 1, 1)
            last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            return first, last

        def by_code(first: date, last: date) -> dict[str, Decimal]:
            return {g.code: g.value for g in self.spending_by_category(first, last, depth)}

        prior = [month_range(start, k) for k in range(1, months + 1)]
        prior = [(a, b) for a, b in prior if a >= floor]
        prior_values = [by_code(a, b) for a, b in prior]
        trend_months = [month_range(end, k) for k in range(history - 1, -1, -1)]
        trend_months = [(a, min(b, end)) for a, b in trend_months if a >= floor]
        trend_values = [by_code(a, b) for a, b in trend_months]
        rows = []
        for group in self.spending_by_category(start, end, depth):
            usual = (sum((v.get(group.code, ZERO) for v in prior_values), ZERO) / len(prior_values)) if prior_values else None
            rows.append({"code": group.code, "label": group.label, "value": group.value, "usual": usual,
                         "change": None if usual is None else group.value - usual,
                         "history": [v.get(group.code, ZERO) for v in trend_values],
                         "history_months": [a.strftime("%Y-%m") for a, _ in trend_months]})
        return rows

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
            if cursor.year == 9999 and cursor.month == 12:
                break
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        for key, flow in self.flows_by_date(first, last, "month").items():
            if key in data:
                data[key]["inflows"], data[key]["outflows"] = flow["inflows"], flow["outflows"]
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

    def category_transaction_ids(self, category_ids: set[int]) -> set[int]:
        return self.q.category_transaction_ids(category_ids)

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

    def register_page(self, account_id: int | None, date_from: date | str, date_to: date | str,
                      page: int, page_size: int = 50) -> tuple[list[StatementRow], int, int]:
        """One page of ``register`` (newest first) without reading the rest: (rows, total rows, page).

        The page is clamped to the pages there are. A single account's running balance starts from
        the opening balance plus the movement of every older row, summed in SQL."""
        start, end = self._day(date_from), self._day(date_to)
        total = self.q.statement_count(account_id, start, end)
        pages = max(1, -(-total // page_size))
        page = min(max(page, 1), pages)
        newest = total - (page - 1) * page_size          # rows are read oldest first
        first = max(0, newest - page_size)
        opening = None
        if account_id:
            opening = from_e6(self.q.account_quantity(account_id, before=start)
                              + self.q.statement_movement(account_id, start, end, first))
        lines = self.q.statement_lines(account_id, start, end, limit=newest - first, offset=first)
        return list(reversed(self._rows(lines, opening))), total, page

    def _rows(self, lines: list[dict], opening: Decimal | None) -> list[StatementRow]:
        running = opening
        rows = []
        for r in lines:
            movement = from_e6(r["quantity_e6"])
            amount = from_e6(r["amount_e6"]) if r["effect"] == "REVALUATION" else movement
            if running is not None:
                running += movement
            other_label = self.accounts.get(r["other_account_id"]).label if r["other_account_id"] else ""
            if r["memo"].startswith("Split · "):
                category = r["memo"]
            elif r["type"] in ("BUY", "SEL") and r["memo"]:
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

    def sidebar(self, as_of: date | str) -> tuple[Decimal, Decimal, list[Group]]:
        """Gross active-account balances, owned net worth, and accounts grouped by kind."""
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
        gross_total = sum((value for account, value in nw.by_account if account.active), ZERO)
        return gross_total, nw.total, sorted(groups.values(), key=lambda g: order.index(g.code))

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

    def account_asset_class_breakdown(self, account_id: int, as_of: date | str) -> list[dict]:
        """Brokerage value, ownership and weight grouped by level-2 asset class."""
        account = self.accounts.get(account_id)
        day = self._day(as_of)
        groups: dict[int, dict] = {}

        def level_two(class_id: int):
            asset_class = self.assets.get_class(class_id)
            while asset_class.parent_id is not None:
                parent = self.assets.get_class(asset_class.parent_id)
                if parent.parent_id is None:
                    break
                asset_class = parent
            return asset_class

        def add(class_id: int, value: Decimal, held: Decimal = ZERO):
            asset_class = level_two(class_id)
            group = groups.setdefault(asset_class.id, {"code": asset_class.code, "name": asset_class.name,
                                                        "total": ZERO, "held": ZERO})
            group["total"] += value
            group["held"] += held

        holdings, _ = self.holdings(day)
        for holding in holdings:
            if holding.account.id == account_id:
                add(self.assets.get_class_by_code(holding.asset_class_code).id, holding.value or ZERO)

        cash_amount = self.money_from_others.cash_total_for_account(account_id, day)
        if cash_amount:
            cash_value = self.valuer.value(self.assets.cash_asset(account.currency), cash_amount, day).value
            if cash_value is not None:
                add(account.cash_class_id, ZERO, cash_value)
        for position in self.money_from_others.investment_positions(day):
            if position["account_id"] != account_id:
                continue
            asset = self.assets.get_asset(position["asset_id"])
            held_value = self.valuer.value(asset, position["units"], day).value
            if held_value is not None:
                add(asset.asset_class_id, ZERO, held_value)

        total = self.account_value(account_id, day)
        held_total = sum((group["held"] for group in groups.values()), ZERO)
        yours_total = total - held_total
        result = []
        for group in groups.values():
            yours = group["total"] - group["held"]
            result.append({"code": group["code"], "name": group["name"], "total": group["total"],
                           "held": group["held"], "yours": yours,
                           "weight_total": group["total"] / total * 100 if total else ZERO,
                           "weight_yours": yours / yours_total * 100 if yours_total else ZERO,
                           "weight_held": group["held"] / held_total * 100 if held_total else ZERO})
        return sorted(result, key=lambda group: (-group["total"], group["name"].casefold()))

    def first_date(self) -> str | None:
        return self.q.first_entry_date()

    @staticmethod
    def _day(value: date | str) -> str:
        return fmt_date(parse_date(value))
