"""Financial assets — WHAT wealth consists of — and the asset-class tree."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Exposure(StrEnum):
    CASH = "CASH"
    EQUITY = "EQUITY"
    GOLD = "GOLD"
    FIXED_INCOME = "FIXED_INCOME"
    REAL_ESTATE = "REAL_ESTATE"
    OTHER = "OTHER"


class Liquidity(StrEnum):
    IMMEDIATE = "IMMEDIATE"
    DAYS = "DAYS"
    LOCKED = "LOCKED"


class PriceSource(StrEnum):
    YAHOO = "YAHOO"
    GOLD_CALC = "GOLD_CALC"
    GOLD_LOCAL = "GOLD_LOCAL"
    MANUAL = "MANUAL"
    NONE = "NONE"


@dataclass
class AssetClass:
    id: int
    code: str  # dotted path, e.g. FUND.GOLD
    name: str
    parent_id: int | None
    sort_order: int
    active: bool

    @property
    def root_code(self) -> str:
        return self.code.split(".", 1)[0]

    @property
    def depth(self) -> int:
        return self.code.count(".")

    @property
    def label(self) -> str:
        return f"{self.code} · {self.name}"


@dataclass
class FinancialAsset:
    id: int
    code: str  # CLASS:SYMBOL, e.g. STK:COMI, CASH:EGP
    name: str
    asset_class_id: int
    currency: str
    unit: str
    quantity_decimals: int
    is_cash: bool
    exposure: Exposure
    liquidity: Liquidity
    purity: Decimal | None
    isin: str | None
    price_source: PriceSource
    external_symbol: str | None
    active: bool
    notes: str

    @property
    def label(self) -> str:
        return f"{self.code} · {self.name}"
