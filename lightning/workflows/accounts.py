"""Account workflows — actions that span modules, each in ONE database transaction.

- Opening an account also records its opening balance (as an OPN transaction).
- An account can only be deactivated once its balance is zero (no hidden money).
"""

from __future__ import annotations

from decimal import Decimal

from lightning.accounts.domain import Account
from lightning.accounts.service import AccountService
from lightning.core.errors import ConflictError, ValidationError
from lightning.core.dates import fmt_date, parse_date
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
                     last4: str | None = None, notes: str = "") -> Account:
        with self.db.transaction():
            amount = self.parse_opening(opening_balance)
            account = self.accounts.create(name=name, account_type=account_type, opening_date=opening_date,
                                           institution=institution, currency=currency, code=code,
                                           last4=last4, notes=notes)
            self.transactions.set_opening_balance(account.id, amount, account.opening_date)
        return account

    def update_account(self, account_id: int, name: str, account_type: str, opening_date: str,
                       opening_balance: object = "0", institution: str = "", code: str | None = None,
                       last4: str | None = None, notes: str = "") -> Account:
        first = self.transactions.earliest_activity(account_id)
        new_start = fmt_date(parse_date(opening_date, "opening_date"))
        if first and new_start > first:
            raise ValidationError(
                f"This account already has transactions from {first}. The start date must be on or before that.",
                "opening_date",
            )
        with self.db.transaction():
            account, _ = self.accounts.update(account_id, name=name, institution=institution,
                                                    account_type=account_type, opening_date=opening_date,
                                                    code=code, last4=last4, notes=notes)
            self.transactions.set_opening_balance(account.id, self.parse_opening(opening_balance),
                                                  account.opening_date)
        return account

    def deactivate(self, account_id: int) -> Account:
        account = self.accounts.get(account_id)
        balance = self.reporting.account_balance(account_id)
        if balance != ZERO:
            raise ConflictError(
                f"{account.label} still holds {fmt(balance)} {account.currency}. "
                "Move the balance to another account first, then deactivate it."
            )
        return self.accounts.set_active(account_id, False)

    def reactivate(self, account_id: int) -> Account:
        return self.accounts.set_active(account_id, True)
