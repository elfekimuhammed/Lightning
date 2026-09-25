"""Public API of the assets module (read-only in M1; creating investments arrives in M3)."""

from __future__ import annotations

from lightning.core.errors import NotFoundError, ValidationError
from lightning.database.connection import Database

from .domain import AssetClass, FinancialAsset
from .repository import AssetRepository


class AssetService:
    def __init__(self, db: Database):
        self.repo = AssetRepository(db)

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
