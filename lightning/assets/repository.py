"""SQL for asset_classes and financial_assets. Only this module touches those tables."""

from __future__ import annotations

import sqlite3

from lightning.core.money import from_e6
from lightning.database.connection import Database

from .domain import AssetClass, Exposure, FinancialAsset, Liquidity, PriceSource


def _class(row: sqlite3.Row) -> AssetClass:
    return AssetClass(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        parent_id=row["parent_id"],
        sort_order=row["sort_order"],
        active=bool(row["active"]),
    )


def _asset(row: sqlite3.Row) -> FinancialAsset:
    return FinancialAsset(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        asset_class_id=row["asset_class_id"],
        currency=row["currency"],
        unit=row["unit"],
        quantity_decimals=row["quantity_decimals"],
        is_cash=bool(row["is_cash"]),
        exposure=Exposure(row["exposure"]),
        liquidity=Liquidity(row["liquidity"]),
        purity=None if row["purity_e6"] is None else from_e6(row["purity_e6"]),
        isin=row["isin"],
        price_source=PriceSource(row["price_source"]),
        external_symbol=row["external_symbol"],
        active=bool(row["active"]),
        notes=row["notes"],
    )


class AssetRepository:
    def __init__(self, db: Database):
        self.db = db

    # asset classes
    def list_classes(self) -> list[AssetClass]:
        return [_class(r) for r in self.db.all("SELECT * FROM asset_classes ORDER BY sort_order, code")]

    def get_class(self, class_id: int) -> AssetClass | None:
        row = self.db.one("SELECT * FROM asset_classes WHERE id = ?", (class_id,))
        return _class(row) if row else None

    def get_class_by_code(self, code: str) -> AssetClass | None:
        row = self.db.one("SELECT * FROM asset_classes WHERE code = ?", (code,))
        return _class(row) if row else None

    # financial assets
    def list_assets(self) -> list[FinancialAsset]:
        return [_asset(r) for r in self.db.all("SELECT * FROM financial_assets ORDER BY code")]

    def get_asset(self, asset_id: int) -> FinancialAsset | None:
        row = self.db.one("SELECT * FROM financial_assets WHERE id = ?", (asset_id,))
        return _asset(row) if row else None

    def get_asset_by_code(self, code: str) -> FinancialAsset | None:
        row = self.db.one("SELECT * FROM financial_assets WHERE code = ?", (code,))
        return _asset(row) if row else None

    def get_cash_asset(self, currency: str) -> FinancialAsset | None:
        row = self.db.one(
            "SELECT * FROM financial_assets WHERE is_cash = 1 AND currency = ?", (currency,)
        )
        return _asset(row) if row else None
