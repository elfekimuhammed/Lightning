from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class InterestMethod(StrEnum):
    SIMPLE = "SIMPLE"
    COMPOUND = "COMPOUND"


class PayoutFrequency(StrEnum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    AT_MATURITY = "AT_MATURITY"


class CompoundingFrequency(StrEnum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"


@dataclass(frozen=True)
class DepositTerms:
    account_id: int
    start_date: str
    lockup_end_date: str
    maturity_date: str
    principal: Decimal
    annual_rate: Decimal  # percentage points: Decimal("18") means 18% per year
    interest_method: InterestMethod
    payout_frequency: PayoutFrequency
    compounding_frequency: CompoundingFrequency
    destination_account_id: int


@dataclass(frozen=True)
class DepositEvent:
    date: str
    account_id: int
    amount: Decimal
    kind: str
    deposit_account_id: int
