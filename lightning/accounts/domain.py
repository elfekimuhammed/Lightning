"""Accounts — WHERE value is held (a wallet, a bank account, a CD, THNDR).

Lightning tracks what you own; it does not track debts (no liabilities — owner decision 2026-09-25).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lightning.core.codes import slug


class AccountType(StrEnum):
    CASH = "CASH"
    BANK = "BANK"  # current or savings — the same thing here
    DEPOSIT = "DEPOSIT"  # bank-specific portfolio of non-cash certificates
    BROKERAGE = "BROKERAGE"
    PHYSICAL_ASSET = "PHYSICAL_ASSET"  # offered from M3 (holdings of gold etc.)
    OTHER_ASSET = "OTHER_ASSET"


TYPE_LABELS: dict[AccountType, str] = {
    AccountType.CASH: "Cash wallet",
    AccountType.BANK: "Bank account (current or savings)",
    AccountType.DEPOSIT: "Certificates of deposit (CD portfolio)",
    AccountType.BROKERAGE: "Brokerage / investment (e.g. THNDR)",
    AccountType.PHYSICAL_ASSET: "Physical asset (e.g. gold at home)",
    AccountType.OTHER_ASSET: "Other",
}

# For lists, where the picker's hints would only repeat (review, 2026-10-06).
TYPE_SHORT: dict[AccountType, str] = {
    AccountType.CASH: "Cash",
    AccountType.BANK: "Bank account",
    AccountType.DEPOSIT: "Certificates",
    AccountType.BROKERAGE: "Brokerage",
    AccountType.PHYSICAL_ASSET: "Physical asset",
    AccountType.OTHER_ASSET: "Other",
}

TYPE_ABBR: dict[AccountType, str] = {
    AccountType.CASH: "CSH",
    AccountType.BANK: "CUR",
    AccountType.DEPOSIT: "CD",
    AccountType.BROKERAGE: "BRK",
    AccountType.PHYSICAL_ASSET: "PHY",
    AccountType.OTHER_ASSET: "OTH",
}

# Cash is one asset (CASH:EGP) wherever it sits; the account type decides where it is reported.
DEFAULT_CASH_CLASS: dict[AccountType, str] = {
    AccountType.CASH: "CASH.PHYSICAL",
    AccountType.BANK: "CASH.BANK",
    AccountType.DEPOSIT: "DEPOSIT.CD",
    AccountType.BROKERAGE: "CASH.BROKERAGE",
    AccountType.PHYSICAL_ASSET: "OTHER",
    AccountType.OTHER_ASSET: "OTHER",
}

# Types a user can pick today
OFFERED_TYPES = [
    AccountType.CASH,
    AccountType.BANK,
    AccountType.DEPOSIT,
    AccountType.BROKERAGE,
    AccountType.PHYSICAL_ASSET,
    AccountType.OTHER_ASSET,
]

# Accounts that can hold investments (stocks, funds, gold)
INVESTMENT_ACCOUNT_TYPES = {AccountType.BROKERAGE, AccountType.PHYSICAL_ASSET, AccountType.OTHER_ASSET}

# How the sidebar groups accounts (the dashboard groups wealth by asset class instead)
SIDEBAR_GROUPS: dict[AccountType, str] = {
    AccountType.CASH: "Cash & bank",
    AccountType.BANK: "Cash & bank",
    AccountType.DEPOSIT: "Deposits",
    AccountType.BROKERAGE: "Investments",
    AccountType.PHYSICAL_ASSET: "Investments",
    AccountType.OTHER_ASSET: "Other",
}


@dataclass
class Account:
    id: int
    code: str
    name: str
    institution: str
    account_type: AccountType
    currency: str
    cash_class_id: int  # always follows account_type (DEFAULT_CASH_CLASS)
    opening_date: str  # yyyy-mm-dd
    is_system: bool
    last4: str | None
    active: bool
    sort_order: int
    notes: str

    @property
    def label(self) -> str:
        """Human-facing account label; the internal code is never shown in the UI."""
        return self.name

    @property
    def type_label(self) -> str:
        return TYPE_LABELS[self.account_type]

    @property
    def type_short(self) -> str:
        return TYPE_SHORT[self.account_type]


def suggest_code(institution: str, name: str, account_type: AccountType, currency: str) -> str:
    """CIB + Bank + EGP -> CIB-CUR-EGP; a wallet with no institution -> WALLET-CSH-EGP."""
    head = slug(institution, 12) or slug(name, 12) or account_type.value.split("_")[0]
    return f"{head}-{TYPE_ABBR[account_type]}-{currency}"
