"""Account workflows — actions that span modules, each in ONE database transaction.

- Opening an account also records its opening balance (as an OPN transaction).
- An account can only be deactivated once its balance is zero (no hidden money).
"""

from __future__ import annotations

from decimal import Decimal

from lightning.accounts.domain import Account, INVESTMENT_ACCOUNT_TYPES
from lightning.accounts.service import AccountService
from lightning.core.errors import ConflictError, ValidationError
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.database.connection import Database
from lightning.reporting.service import ReportingService
from lightning.transactions.service import TransactionService


class AccountWorkflows:
    def __init__(self, db: Database, accounts: AccountService, transactions: TransactionService,
                 reporting: ReportingService):
        self.db = db
        self.accounts = accounts
        self.transactions = transactions
        self.reporting = reporting

    @staticmethod
    def parse_opening(entered: object) -> Decimal:
        """What the person typed ('' means 0). Balances you own cannot start below zero."""
        value = to_decimal(entered if str(entered or "").strip() else "0", "opening_balance")
        if value < ZERO:
            raise ValidationError("An opening balance cannot be negative.", "opening_balance")
        return value

    def opening_of(self, account: Account) -> Decimal:
        return self.transactions.opening_balance(account.id)

    def open_account(self, name: str, account_type: str, opening_date: str, opening_balance: object = "0",
                     institution: str = "", currency: str | None = None, code: str | None = None,
                     last4: str | None = None, notes: str = "",
                     opening_balance_date: str | None = None, owner_id: int | None = None) -> Account:
        with self.db.transaction():
            amount = self.parse_opening(opening_balance)
            balance_day = parse_date(opening_balance_date or opening_date, "opening_balance_date")
            if balance_day > today():
                raise ValidationError("The starting balance date cannot be in the future.", "opening_balance_date")
            account = self.accounts.create(name=name, account_type=account_type, opening_date=opening_date,
                                           institution=institution, currency=currency, code=code,
                                           last4=last4, notes=notes)
            self.transactions.set_opening_balance(account.id, amount, fmt_date(balance_day), owner_id)
        return account

    def update_account(self, account_id: int, name: str, account_type: str, opening_date: str,
                       opening_balance: object = "0", institution: str = "", code: str | None = None,
                       last4: str | None = None, notes: str = "", opening_balance_date: str | None = None,
                       owner_id: int | None = None) -> Account:
        balance_day = fmt_date(parse_date(opening_balance_date or opening_date, "opening_balance_date"))
        if parse_date(balance_day) > today():
            raise ValidationError("The starting balance date cannot be in the future.", "opening_balance_date")
        current = self.accounts.get(account_id)
        if current.account_type in INVESTMENT_ACCOUNT_TYPES and account_type not in {t.value for t in INVESTMENT_ACCOUNT_TYPES}:
            holdings = [h for h in self.reporting.holdings("9999-12-31")[0] if h.account.id == account_id]
            if holdings:
                raise ConflictError(
                    "This account still holds investments. Sell or move them before changing its type.",
                    "account_type",
                )
        with self.db.transaction():
            account, _ = self.accounts.update(account_id, name=name, institution=institution,
                                                    account_type=account_type, opening_date=opening_date,
                                                    code=code, last4=last4, notes=notes)
            self.transactions.set_opening_balance(account.id, self.parse_opening(opening_balance),
                                                  balance_day, owner_id)
        return account

    def deactivate(self, account_id: int) -> Account:
        account = self.accounts.get(account_id)
        balance = self.reporting.account_balance(account_id, "9999-12-31")
        if balance != ZERO:
            raise ConflictError(
                f"{account.label} still holds {fmt(balance)} {account.currency}. "
                "Move the balance to another account first, then deactivate it."
            )
        held = [h for h in self.reporting.holdings("9999-12-31")[0] if h.account.id == account_id]
        if held:
            raise ConflictError(f"{account.label} still holds investments ({', '.join(h.asset_code for h in held)}). "
                                "Sell or move them first, then deactivate it.")
        return self.accounts.set_active(account_id, False)

    def reactivate(self, account_id: int) -> Account:
        return self.accounts.set_active(account_id, True)
