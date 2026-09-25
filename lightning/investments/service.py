"""Public API of the investments module: buy, sell, dividends, holdings you already own, and positions.

It builds ledger lines and hands them to TransactionService.post(), so every rule of the core applies
(internal lines net to zero, no future dates, no holding below zero units).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from lightning.accounts.domain import INVESTMENT_ACCOUNT_TYPES, Account, AccountType
from lightning.accounts.service import AccountService
from lightning.assets.domain import EXPOSURE_LABELS, FinancialAsset
from lightning.assets.service import AssetService
from lightning.categories.service import CategoryService
from lightning.core.dates import fmt_date, today
from lightning.core.errors import ConflictError, ValidationError
from lightning.core.ledger import Effect, PostingLine
from lightning.core.money import ZERO, check_places, fmt, from_e6, to_decimal
from lightning.core.refs import DocType
from lightning.database.connection import Database
from lightning.reporting.service import ReportingService
from lightning.transactions.domain import Transaction
from lightning.transactions.service import TransactionService

from .domain import Portfolio, Position

DIVIDEND_CATEGORY = "INC.INVEST.DIVIDEND"
CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _num(value: Decimal) -> str:
    """Short number for descriptions: 100, 95.5, 0.125."""
    text = f"{value.normalize():f}"
    return text


class InvestmentService:
    def __init__(self, db: Database, accounts: AccountService, assets: AssetService, categories: CategoryService,
                 transactions: TransactionService, reporting: ReportingService):
        self.db = db
        self.accounts = accounts
        self.assets = assets
        self.categories = categories
        self.transactions = transactions
        self.reporting = reporting

    # ======================================================================
    # Recording
    # ======================================================================
    def buy(self, date: str, account_id: int, asset_id: int, quantity, price, fees="0",
            cash_account_id: int | None = None, notes: str = "") -> Transaction:
        """Buy units: cash leaves the paying account, the holding grows at cost (fees included)."""
        return self._trade(DocType.BUY, date, account_id, asset_id, quantity, price, fees, cash_account_id, notes)

    def buy_total(self, date, account_id, asset_id, quantity, total, cash_account_id=None, notes=""):
        """Buy units for a single all-in total; per-unit cost is derived from total / units."""
        return self._trade(DocType.BUY, date, account_id, asset_id, quantity, None, "0", cash_account_id, notes,
                           total=total)

    def sell_total(self, date, account_id, asset_id, quantity, total, cash_account_id=None, notes=""):
        """Sell units for a single net cash total after fees; per-unit proceeds are derived."""
        return self._trade(DocType.SEL, date, account_id, asset_id, quantity, None, "0", cash_account_id, notes,
                           total=total)

    def sell(self, date: str, account_id: int, asset_id: int, quantity, price, fees="0",
             cash_account_id: int | None = None, notes: str = "") -> Transaction:
        """Sell units: the holding shrinks, what you receive (after fees) arrives as cash."""
        return self._trade(DocType.SEL, date, account_id, asset_id, quantity, price, fees, cash_account_id, notes)

    def dividend(self, date: str, account_id: int, asset_id: int, amount, notes: str = "") -> Transaction:
        """A cash dividend from an investment, received into the account (money in: Investment Income)."""
        lines, counterparty = self._dividend_lines(account_id, asset_id, amount)
        return self.transactions.post(DocType.DIV, date, lines, "", counterparty, notes)

    def add_holding(self, account_id: int, asset_id: int, quantity, total_cost, date: str | None = None,
                    notes: str = "") -> Transaction:
        """Units you already owned when you started tracking, with what you paid for them in total."""
        account = self._holding_account(account_id)
        asset = self._investment(asset_id)
        if self.transactions.opening_txn_id(account.id, asset.id):
            raise ConflictError(f"{account.label} already has a starting amount of {asset.name} — edit that one.")
        lines = self._holding_lines(account, asset, quantity, total_cost)
        return self.transactions.post(DocType.OPN, date or account.opening_date, lines,
                                      f"Starting holding — {asset.name}", asset.name, notes)

    def update(self, txn_id: int, **values) -> Transaction:
        """Edit a buy, sell, dividend or starting holding in place; the ref stays the same."""
        current = self.transactions.get(txn_id)
        kind = current.type
        date = values.get("date", current.date)
        notes = values.get("notes", current.notes)
        if kind in (DocType.BUY, DocType.SEL):
            lines, counterparty = self._trade_lines(kind, values["account_id"], values["asset_id"], values["quantity"],
                                                    values["price"], values.get("fees", "0"),
                                                    values.get("cash_account_id"), total=values.get("total"))
            return self.transactions.repost(txn_id, date, lines, "", counterparty, notes)
        if kind == DocType.DIV:
            lines, counterparty = self._dividend_lines(values["account_id"], values["asset_id"], values["amount"])
            return self.transactions.repost(txn_id, date, lines, "", counterparty, notes)
        if kind == DocType.OPN and self._is_holding_opening(current):
            account = self._holding_account(values["account_id"])
            asset = self._investment(values["asset_id"])
            existing = self.transactions.opening_txn_id(account.id, asset.id, exclude_id=txn_id)
            if existing:
                raise ConflictError(f"{account.label} already has a starting amount of {asset.name}.")
            lines = self._holding_lines(account, asset, values["quantity"], values["total_cost"])
            return self.transactions.repost(txn_id, date, lines, f"Starting holding — {asset.name}", asset.name,
                                            notes)
        raise ValidationError("This is not an investment transaction.")

    def values_of(self, txn_id: int) -> dict:
        """The form values that would recreate a transaction (to prefill the edit form)."""
        t = self.transactions.get(txn_id)
        cash = [ln for ln in t.lines if self.assets.get_asset(ln.asset_id).is_cash]
        units = [ln for ln in t.lines if not self.assets.get_asset(ln.asset_id).is_cash]
        values = {"kind": {DocType.BUY: "buy", DocType.SEL: "sell", DocType.DIV: "dividend",
                           DocType.OPN: "holding"}.get(t.type, ""), "date": t.date, "notes": t.notes}
        if t.type in (DocType.BUY, DocType.SEL) and units and cash:
            u, c = units[0], cash[0]
            gross = _money(abs(u.quantity) * u.unit_price)
            fees = abs(u.amount) - gross if t.type == DocType.BUY else gross - abs(u.amount)
            values.update(account_id=u.account_id, asset_id=u.asset_id, quantity=abs(u.quantity),
                          price=u.unit_price, fees=_money(fees), total=abs(c.quantity), cash_account_id=c.account_id)
        elif t.type == DocType.DIV and cash:
            asset = self.assets.get_asset_by_code(cash[0].memo)
            values.update(account_id=cash[0].account_id, asset_id=asset.id, amount=cash[0].quantity)
        elif t.type == DocType.OPN and units:
            values.update(account_id=units[0].account_id, asset_id=units[0].asset_id, quantity=units[0].quantity,
                          total_cost=units[0].amount)
        return values

    # ======================================================================
    # Positions
    # ======================================================================
    def portfolio(self, as_of=None, account_id: int | None = None) -> Portfolio:
        """Every holding (open and closed) with cost basis, value and gains, as of a date (default today)."""
        day = fmt_date(as_of) if as_of and not isinstance(as_of, str) else (as_of or fmt_date(today()))
        state: dict[tuple[int, int], dict] = {}
        dividends: dict[tuple[int, str], Decimal] = {}
        for line in self.reporting.investment_lines(day, account_id):
            if line["type"] == "DIV":
                key = (line["account_id"], line["memo"])
                dividends[key] = dividends.get(key, ZERO) + from_e6(line["amount_base_e6"])
                continue
            s = state.setdefault((line["account_id"], line["asset_id"]),
                                 {"qty": ZERO, "cost": ZERO, "realized": ZERO})
            qty, amount = from_e6(line["quantity_e6"]), from_e6(line["amount_base_e6"])
            if qty > 0:
                s["cost"] += amount
                s["qty"] += qty
            else:
                average = s["cost"] / s["qty"] if s["qty"] else ZERO
                removed = average * -qty
                if line["type"] == "SEL":
                    s["realized"] += -amount - removed
                s["cost"] -= removed
                s["qty"] += qty
            if s["qty"] == ZERO:
                s["cost"] = ZERO
        positions = []
        for (acc_id, asset_id), s in state.items():
            account, asset = self.accounts.get(acc_id), self.assets.get_asset(asset_id)
            valuation = self.reporting.value_of(asset_id, s["qty"], day) if s["qty"] else None
            positions.append(Position(
                account_id=acc_id, account_label=account.label, asset_id=asset_id, asset_code=asset.code,
                asset_name=asset.name, asset_class=self.assets.display_name(asset.asset_class_id),
                exposure=EXPOSURE_LABELS[asset.exposure], unit=asset.unit, quantity=s["qty"],
                cost_basis=_money(s["cost"]), realized=_money(s["realized"]),
                dividends=dividends.pop((acc_id, asset.code), ZERO),
                price=valuation.price if valuation else None,
                price_date=valuation.price_date if valuation else None,
                price_source=valuation.source if valuation else "",
                value=valuation.value if valuation and valuation.value is not None else (
                    None if s["qty"] else ZERO),  # full precision, like net worth; screens round
            ))
        # dividends from something not (or no longer) held in that account still count
        for (acc_id, code), amount in dividends.items():
            asset = self.assets.get_asset_by_code(code)
            positions.append(Position(acc_id, self.accounts.get(acc_id).label, asset.id, asset.code, asset.name,
                                      self.assets.display_name(asset.asset_class_id), EXPOSURE_LABELS[asset.exposure],
                                      asset.unit, ZERO, ZERO, ZERO, amount, None, None, "", ZERO))
        positions.sort(key=lambda p: (-(p.value or ZERO), p.asset_name))
        return Portfolio(day, positions)

    def holding(self, account_id: int, asset_id: int, as_of=None) -> Decimal:
        for p in self.portfolio(as_of, account_id).positions:
            if p.asset_id == asset_id:
                return p.quantity
        return ZERO

    def investment_accounts(self) -> list[Account]:
        return [a for a in self.accounts.list(active_only=True) if a.account_type in INVESTMENT_ACCOUNT_TYPES]

    # ======================================================================
    # Building lines
    # ======================================================================
    def _trade(self, kind, date, account_id, asset_id, quantity, price, fees, cash_account_id, notes, total=None):
        lines, counterparty = self._trade_lines(kind, account_id, asset_id, quantity, price, fees, cash_account_id, total)
        return self.transactions.post(kind, date, lines, "", counterparty, notes)

    def _trade_lines(self, kind, account_id, asset_id, quantity, price, fees, cash_account_id, total=None):
        account = self._holding_account(account_id)
        asset = self._investment(asset_id)
        cash_account = self._cash_account(account, cash_account_id)
        units = self._units(asset, quantity)
        if total is not None:
            gross = check_places(to_decimal(total, "total"), 2, "total")
            if gross <= ZERO:
                raise ValidationError("Enter the total amount.", "total")
            unit_price = (gross / units).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            fee = ZERO
        else:
            unit_price = check_places(to_decimal(price, "price"), 6, "price")
            if unit_price <= ZERO:
                raise ValidationError("Enter the price per unit.", "price")
            fee = check_places(to_decimal(fees if str(fees or "").strip() else "0", "fees"), 2, "fees")
            if fee < ZERO:
                raise ValidationError("Fees cannot be negative.", "fees")
            gross = _money(units * unit_price)
        cash_asset = self.assets.cash_asset(cash_account.currency)
        fee_text = f" + fee {fmt(fee)}" if kind == DocType.BUY and fee else (f" − fee {fmt(fee)}" if fee else "")
        memo = (f"{'Buy' if kind == DocType.BUY else 'Sell'} {_num(units)} × {asset.code} @ {_num(unit_price)}"
                f"{fee_text}" if total is None else
                f"{'Buy' if kind == DocType.BUY else 'Sell'} {_num(units)} × {asset.code} @ {_num(unit_price)}"
                f" · {'total incl. fees' if kind == DocType.BUY else 'net total'} {fmt(gross)}")
        if kind == DocType.BUY:
            cost = gross if total is not None else gross + fee
            return [PostingLine.cash(cash_account.id, cash_asset.id, -cost, Effect.INTERNAL, memo=memo),
                    PostingLine.units(account.id, asset.id, units, cost, Effect.INTERNAL, unit_price, memo)], asset.name
        proceeds = gross if total is not None else gross - fee
        if proceeds <= ZERO:
            raise ValidationError("After fees nothing would be received — check the price and fees.", "fees")
        return [PostingLine.units(account.id, asset.id, -units, -proceeds, Effect.INTERNAL, unit_price, memo),
                PostingLine.cash(cash_account.id, cash_asset.id, proceeds, Effect.INTERNAL, memo=memo)], asset.name

    def _dividend_lines(self, account_id, asset_id, amount):
        account = self.accounts.require_usable(account_id)
        asset = self._investment(asset_id)
        value = check_places(to_decimal(amount, "amount"), 2, "amount")
        if value <= ZERO:
            raise ValidationError("Enter the dividend you received.", "amount")
        category = self.categories.get_by_code(DIVIDEND_CATEGORY)
        cash_asset = self.assets.cash_asset(account.currency)
        # the memo carries the asset code so dividends are counted per holding
        return [PostingLine.cash(account.id, cash_asset.id, value, Effect.INFLOW, category.id, memo=asset.code)], \
            asset.name

    def _holding_lines(self, account: Account, asset: FinancialAsset, quantity, total_cost):
        units = self._units(asset, quantity)
        cost = check_places(to_decimal(total_cost if str(total_cost or "").strip() else "0", "total_cost"), 2,
                            "total_cost")
        if cost < ZERO:
            raise ValidationError("What you paid cannot be negative.", "total_cost")
        per_unit = (cost / units).quantize(Decimal("0.000001"))
        return [PostingLine.units(account.id, asset.id, units, cost, Effect.OPENING, per_unit,
                                  f"Starting holding {_num(units)} × {asset.label}")]

    def _holding_account(self, account_id) -> Account:
        account = self.accounts.require_usable(account_id)
        if account.account_type not in INVESTMENT_ACCOUNT_TYPES:
            raise ValidationError(
                f"{account.label} is a {account.type_label.lower()}. Investments are held in a brokerage, "
                "physical-asset or other account.", "account")
        return account

    def _cash_account(self, account: Account, cash_account_id) -> Account:
        if cash_account_id in (None, "", 0):
            if account.account_type == AccountType.BROKERAGE:
                return account  # the broker's own cash
            raise ValidationError("Choose which account the money comes from or goes to.", "cash_account")
        return self.accounts.require_usable(int(cash_account_id), "cash_account")

    def _investment(self, asset_id) -> FinancialAsset:
        if asset_id in (None, ""):
            raise ValidationError("Choose the investment.", "asset")
        asset = self.assets.get_asset(int(asset_id))
        if asset.is_cash:
            raise ValidationError("Choose a stock, fund or gold — not a currency.", "asset")
        if not asset.active:
            raise ValidationError(f"{asset.label} is inactive.", "asset")
        return asset

    @staticmethod
    def _units(asset: FinancialAsset, quantity) -> Decimal:
        units = check_places(to_decimal(quantity, "quantity"), asset.quantity_decimals, "quantity")
        if units <= ZERO:
            raise ValidationError(f"Enter how many {asset.unit}s.", "quantity")
        return units

    def _is_holding_opening(self, t: Transaction) -> bool:
        return any(not self.assets.get_asset(ln.asset_id).is_cash for ln in t.lines)
