"""Public API of the accounts module.

Opening balances are NOT stored here — the workflow layer records them as an
opening transaction, so every balance comes from the ledger.
"""

from __future__ import annotations

from dataclasses import replace

from lightning.assets.service import AssetService
from lightning.core.codes import validate_account_code
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.database.connection import Database

from .domain import DEFAULT_CASH_CLASS, OFFERED_TYPES, TYPE_LABELS, Account, AccountType, suggest_code
from .repository import AccountRepository


class AccountService:
    def __init__(self, db: Database, assets: AssetService, base_currency: str, allow_foreign: bool = False):
        self.db = db
        self.repo = AccountRepository(db)
        self.assets = assets
        self.base_currency = base_currency
        self.allow_foreign = allow_foreign  # other currencies need FX rates (M4)

    # -- reading -----------------------------------------------------------
    def list(self, active_only: bool = False) -> list[Account]:
        return self.repo.list(active_only)

    def get(self, account_id: int) -> Account:
        found = self.repo.get(account_id)
        if not found:
            raise NotFoundError("Account not found.")
        return found

    def get_by_code(self, code: str) -> Account:
        found = self.repo.get_by_code(code)
        if not found:
            raise NotFoundError(f"Account {code} not found.")
        return found

    def find_by_text(self, text: str) -> Account | None:
        """An active account matching what was typed: its label ('CIB-CUR-EGP · CIB Current'), code or name."""
        wanted = " ".join((text or "").split()).casefold()
        if not wanted:
            return None
        for account in self.repo.list(active_only=True):
            if wanted in (account.label.casefold(), account.code.casefold(), account.name.casefold(),
                          f"{account.code} · {account.name}".casefold()):
                return account
        return None

    def require_usable(self, account_id: int | None, field: str = "account") -> Account:
        if account_id is None:
            raise ValidationError("Choose an account.", field)
        account = self.get(account_id)
        if not account.active:
            raise ValidationError(f"{account.label} is inactive.", field)
        return account

    def unique_code(self, institution: str, name: str, account_type: AccountType, currency: str) -> str:
        base = suggest_code(institution, name, account_type, currency)
        code, n = base, 1
        while self.repo.code_exists(code):
            n += 1
            code = f"{base}-{n}"
        return code

    # -- writing -----------------------------------------------------------
    def create(
        self,
        name: str,
        account_type: AccountType | str,
        opening_date: str,
        institution: str = "",
        currency: str | None = None,
        code: str | None = None,
        last4: str | None = None,
        notes: str = "",
    ) -> Account:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter an account name.", "name")
        account_type = self._type(account_type)
        currency = (currency or self.base_currency).strip().upper()
        self.assets.cash_asset(currency)  # currency must exist
        if currency != self.base_currency and not self.allow_foreign:
            raise ValidationError(
                f"For now accounts must be in {self.base_currency}. Other currencies arrive with FX rates (M4).",
                "currency",
            )
        institution = (institution or "").strip()
        code = validate_account_code(code) if code and code.strip() else self.unique_code(
            institution, name, account_type, currency
        )
        if self.repo.code_exists(code):
            raise ConflictError(f"The code {code} is already used by another account.", "code")
        account = Account(
            id=0,
            code=code,
            name=name,
            institution=institution,
            account_type=account_type,
            currency=currency,
            cash_class_id=self._cash_class_id(account_type),
            opening_date=self._start(opening_date),
            is_system=False,
            last4=self._last4(last4),
            active=True,
            sort_order=self.repo.next_sort_order(),
            notes=(notes or "").strip(),
        )
        with self.db.transaction():
            new_id = self.repo.insert(account)
        return self.get(new_id)

    def update(
        self,
        account_id: int,
        name: str,
        institution: str,
        account_type: AccountType | str,
        opening_date: str,
        code: str | None = None,
        last4: str | None = None,
        notes: str = "",
    ) -> tuple[Account, bool]:
        """Returns (updated account, whether code or name changed)."""
        current = self.get(account_id)
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter an account name.", "name")
        account_type = self._type(account_type)
        new_code = validate_account_code(code) if code and code.strip() else current.code
        if self.repo.code_exists(new_code, exclude_id=current.id):
            raise ConflictError(f"The code {new_code} is already used by another account.", "code")
        updated = replace(
            current,
            code=new_code,
            name=name,
            institution=(institution or "").strip(),
            account_type=account_type,
            cash_class_id=self._cash_class_id(account_type),
            opening_date=self._start(opening_date),
            last4=self._last4(last4),
            notes=(notes or "").strip(),
        )
        with self.db.transaction():
            self.repo.update(updated)
        return self.get(account_id), (new_code != current.code or name != current.name)

    def set_active(self, account_id: int, active: bool) -> Account:
        account = self.get(account_id)
        with self.db.transaction():
            self.repo.update(replace(account, active=active))
        return self.get(account_id)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _start(value: str) -> str:
        day = parse_date(value, "opening_date")
        if day > today():
            raise ValidationError("An account cannot start in the future.", "opening_date")
        return fmt_date(day)

    @staticmethod
    def _type(value: AccountType | str) -> AccountType:
        try:
            account_type = AccountType(value)
        except ValueError:
            raise ValidationError("Choose an account type.", "account_type") from None
        if account_type not in OFFERED_TYPES:
            raise ValidationError(f"{TYPE_LABELS[account_type]} accounts are not available yet.", "account_type")
        return account_type

    def _cash_class_id(self, account_type: AccountType) -> int:
        """Where this account's cash appears in reports — always decided by the type."""
        return self.assets.get_class_by_code(DEFAULT_CASH_CLASS[account_type]).id

    def reporting_group(self, account: Account) -> str:
        """Plain-language place in 'What your wealth is made of', e.g. 'Liquid Cash › Bank Balance'."""
        return self.assets.display_name(account.cash_class_id)

    @staticmethod
    def _last4(value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if len(value) != 4 or not value.isdigit():
            raise ValidationError("Enter only the last 4 digits (never the full number).", "last4")
        return value
