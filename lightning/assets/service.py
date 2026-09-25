"""Public API of the assets module: asset classes, financial assets (cash and investments) and their prices."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from lightning.core.codes import slug, validate_asset_code
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.core.money import ZERO, check_places, to_decimal
from lightning.database.connection import Database

from .domain import INVESTMENT_KINDS, AssetClass, Exposure, FinancialAsset, Liquidity, Price, PriceSource
from .repository import AssetRepository


class AssetService:
    def __init__(self, db: Database, base_currency: str = "EGP"):
        self.db = db
        self.repo = AssetRepository(db)
        self.base_currency = base_currency

    # -- asset classes -----------------------------------------------------
    def list_classes(self) -> list[AssetClass]:
        """Tree order: each parent followed by its children."""
        classes = self.repo.list_classes()
        by_parent: dict[int | None, list[AssetClass]] = {}
        for c in classes:
            by_parent.setdefault(c.parent_id, []).append(c)
        ordered: list[AssetClass] = []

        def walk(parent_id: int | None) -> None:
            for child in by_parent.get(parent_id, []):
                ordered.append(child)
                walk(child.id)

        walk(None)
        return ordered

    def get_class(self, class_id: int) -> AssetClass:
        found = self.repo.get_class(class_id)
        if not found:
            raise NotFoundError("Asset class not found.")
        return found

    def get_class_by_code(self, code: str) -> AssetClass:
        found = self.repo.get_class_by_code(code)
        if not found:
            raise NotFoundError(f"Asset class {code} not found.")
        return found

    def display_name(self, class_id: int) -> str:
        """Names only, for screens: 'Liquid Cash › Bank Balance'."""
        names, current = [], self.get_class(class_id)
        while True:
            names.append(current.name)
            if current.parent_id is None:
                break
            current = self.get_class(current.parent_id)
        return " › ".join(reversed(names))

    def root_of(self, class_id: int) -> AssetClass:
        current = self.get_class(class_id)
        while current.parent_id is not None:
            current = self.get_class(current.parent_id)
        return current

    # -- financial assets --------------------------------------------------
    def list_assets(self) -> list[FinancialAsset]:
        return self.repo.list_assets()

    def get_asset(self, asset_id: int) -> FinancialAsset:
        found = self.repo.get_asset(asset_id)
        if not found:
            raise NotFoundError("Financial asset not found.")
        return found

    def get_asset_by_code(self, code: str) -> FinancialAsset:
        found = self.repo.get_asset_by_code(code)
        if not found:
            raise NotFoundError(f"Financial asset {code} not found.")
        return found

    def cash_asset(self, currency: str) -> FinancialAsset:
        found = self.repo.get_cash_asset(currency)
        if not found:
            raise ValidationError(f"Currency {currency} is not set up.", "currency")
        return found

    def cash_currencies(self) -> list[str]:
        return [a.currency for a in self.repo.list_assets() if a.is_cash and a.active]

    def investments(self, active_only: bool = False) -> list[FinancialAsset]:
        return [a for a in self.repo.list_assets() if not a.is_cash and (a.active or not active_only)]

    def investment_classes(self) -> list[AssetClass]:
        """Asset classes you can create an investment in (Stocks, Funds…, Gold, Other)."""
        return [c for c in self.list_classes() if c.code in INVESTMENT_KINDS]

    # -- creating investments (M3) ----------------------------------------
    def create_investment(self, name: str, class_code: str, symbol: str = "", karat: object = None,
                          isin: str = "", notes: str = "") -> FinancialAsset:
        """A stock, fund, gold or other investment you can hold in an account.

        Code = <prefix>:<symbol>, e.g. STK:COMI, FND:AZ-GOLD, GLD:21K. Units and decimals follow the class.
        """
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter a name, e.g. Commercial International Bank.", "name")
        kind = INVESTMENT_KINDS.get((class_code or "").strip())
        if kind is None:
            raise ValidationError("Choose what kind of investment this is.", "class_code")
        purity = None
        if class_code == "GOLD":
            carat = to_decimal(karat or "24", "karat")
            if carat not in (Decimal(24), Decimal(22), Decimal(21), Decimal(18)):
                raise ValidationError("Gold karat must be 24, 22, 21 or 18.", "karat")
            purity = (carat / Decimal(24)).quantize(Decimal("0.000001"))
            symbol = symbol or f"{int(carat)}K"
        symbol = slug(symbol or name, 20) or ""
        if not symbol:
            raise ValidationError("Enter a short symbol in Latin letters, e.g. COMI.", "symbol")
        code = validate_asset_code(f"{kind.prefix}:{symbol}")
        if self.repo.get_asset_by_code(code):
            raise ConflictError(f"{code} already exists.", "symbol")
        asset = FinancialAsset(
            id=0, code=code, name=name, asset_class_id=self.get_class_by_code(class_code).id,
            currency=self.base_currency, unit=kind.unit, quantity_decimals=kind.quantity_decimals, is_cash=False,
            exposure=kind.exposure, liquidity=kind.liquidity, purity=purity, isin=(isin or "").strip() or None,
            price_source=PriceSource.MANUAL, external_symbol=None, active=True, notes=(notes or "").strip(),
        )
        with self.db.transaction():
            new_id = self.repo.insert_asset(asset)
        return self.get_asset(new_id)

    def update_investment(self, asset_id: int, name: str, class_code: str | None = None, isin: str = "",
                          notes: str = "", active: bool = True) -> FinancialAsset:
        asset = self.get_asset(asset_id)
        if asset.is_cash:
            raise ValidationError("Currencies cannot be edited here.")
        name = (name or "").strip()
        if not name:
            raise ValidationError("Enter a name.", "name")
        class_id = asset.asset_class_id
        exposure = asset.exposure
        if class_code:
            kind = INVESTMENT_KINDS.get(class_code)
            if kind is None:
                raise ValidationError("Choose what kind of investment this is.", "class_code")
            class_id, exposure = self.get_class_by_code(class_code).id, kind.exposure
        updated = replace(asset, name=name, asset_class_id=class_id, exposure=exposure,
                          isin=(isin or "").strip() or None, notes=(notes or "").strip(), active=active)
        with self.db.transaction():
            self.repo.update_asset(updated)
        return self.get_asset(asset_id)

    # -- prices -------------------------------------------------------------
    def set_price(self, asset_id: int, date: str, price: object, source: str = "MANUAL") -> Price:
        """Record the price of one unit on a date (a manual price wins over automatic ones)."""
        asset = self.get_asset(asset_id)
        if asset.is_cash:
            raise ValidationError("Currencies do not need a price.")
        day = parse_date(date)
        if day > today():
            raise ValidationError("Prices cannot be dated in the future.", "date")
        value = check_places(to_decimal(price, "price"), 6, "price")
        if value <= ZERO:
            raise ValidationError(f"The price of {asset.name} must be greater than zero.", "price")
        with self.db.transaction():
            self.repo.upsert_price(asset.id, fmt_date(day), value, asset.currency, source)
        return Price(asset.id, fmt_date(day), value, asset.currency, source)

    def set_prices(self, date: str, prices: dict[int, object]) -> int:
        """Several prices for one date (the 'Update prices' page). Empty values are skipped."""
        count = 0
        with self.db.transaction():
            for asset_id, raw in prices.items():
                if str(raw or "").strip():
                    self.set_price(asset_id, date, raw)
                    count += 1
        return count

    def remove_price(self, asset_id: int, date: str, source: str = "MANUAL") -> None:
        with self.db.transaction():
            self.repo.delete_price(asset_id, fmt_date(parse_date(date)), source)

    def price_history(self, asset_id: int, limit: int = 50) -> list[Price]:
        return self.repo.prices(asset_id, limit)
