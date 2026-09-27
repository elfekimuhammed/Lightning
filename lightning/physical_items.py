"""Named physical gold items backed by piece-count ledger assets."""

from __future__ import annotations

from decimal import Decimal

from lightning.accounts.domain import AccountType
from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.core.dates import now_iso, parse_date, today
from lightning.core.errors import ValidationError
from lightning.core.money import check_places, to_decimal, to_e6
from lightning.database.audit import AuditLog
from lightning.database.connection import Database


class PhysicalItemService:
    def __init__(self, db: Database, accounts: AccountService, assets: AssetService, audit: AuditLog):
        self.db, self.accounts, self.assets, self.audit = db, accounts, assets, audit

    def create(self, account_id: int, name: str, kind: str, grams_per_piece, karat: int,
               reference_asset_id: int, details: str = "") -> int:
        account = self.accounts.require_usable(account_id)
        if account.account_type != AccountType.PHYSICAL_ASSET:
            raise ValidationError("Choose a physical-asset account.", "account_id")
        name = (name or "").strip()
        kind = (kind or "").strip()
        if not name:
            raise ValidationError("Enter an item name.", "name")
        if not kind:
            raise ValidationError("Choose an item kind.", "kind")
        if karat not in (18, 21, 22, 24):
            raise ValidationError("Choose 18K, 21K, 22K, or 24K.", "karat")
        weight = check_places(to_decimal(grams_per_piece, "weight"), 6, "weight")
        if weight <= 0:
            raise ValidationError("Net gold weight per piece must be greater than zero.", "weight")
        ref = self.assets.get_asset(int(reference_asset_id))
        if ref.exposure.value != "GOLD" or ref.purity not in (Decimal(1), Decimal(karat) / Decimal(24)):
            raise ValidationError(f"Choose a 24K or {karat}K gold price reference.", "reference_asset_id")
        if ref.currency != account.currency:
            raise ValidationError("The price reference must use this account's currency.", "reference_asset_id")
        now = now_iso()
        with self.db.transaction():
            item_asset = self.assets.create_physical_item_asset(name)
            self.db.execute(
                "INSERT INTO physical_items(asset_id,account_id,item_kind,net_gold_grams_e6,karat,"
                "reference_asset_id,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (item_asset.id, account.id, kind, to_e6(weight), karat, ref.id, (details or "").strip(), now, now),
            )
            self.audit.record("physical_item", item_asset.id, "create", f"Created {name}", None,
                              self._snapshot(item_asset.id))
        return item_asset.id

    def get(self, asset_id: int) -> dict:
        row = self.db.one("SELECT * FROM physical_items WHERE asset_id=?", (asset_id,))
        if not row:
            raise ValidationError("Physical item not found.")
        return dict(row)

    def for_account(self, account_id: int) -> list[dict]:
        return [dict(row) for row in self.db.all(
            "SELECT p.*,a.name FROM physical_items p JOIN financial_assets a ON a.id=p.asset_id "
            "WHERE p.account_id=? ORDER BY a.name COLLATE NOCASE", (account_id,))]

    def update(self, asset_id: int, name: str, kind: str, grams_per_piece, karat: int,
               reference_asset_id: int, details: str = "") -> None:
        old = self.get(asset_id)
        name, kind = (name or "").strip(), (kind or "").strip()
        weight = check_places(to_decimal(grams_per_piece, "weight"), 6, "weight")
        if not name or not kind or weight <= 0:
            raise ValidationError("Enter an item name, kind, and positive net gold weight.")
        if karat not in (18, 21, 22, 24):
            raise ValidationError("Choose 18K, 21K, 22K, or 24K.", "karat")
        ref = self.assets.get_asset(int(reference_asset_id))
        account = self.accounts.require_usable(old["account_id"])
        if ref.exposure.value != "GOLD" or ref.purity not in (Decimal(1), Decimal(karat) / Decimal(24)) or ref.currency != account.currency:
            raise ValidationError(f"Choose a 24K or {karat}K gold price reference in {account.currency}.",
                                  "reference_asset_id")
        before = self._snapshot(asset_id)
        after = {"name": name, "kind": kind, "grams_per_piece": str(weight), "karat": karat,
                 "reference_asset_id": ref.id, "details": (details or "").strip()}
        with self.db.transaction():
            self.db.execute("UPDATE physical_items SET item_kind=?,net_gold_grams_e6=?,karat=?,reference_asset_id=?,"
                            "details=?,updated_at=? WHERE asset_id=?",
                            (kind, to_e6(weight), karat, ref.id, after["details"], now_iso(), asset_id))
            self.db.execute("UPDATE financial_assets SET name=?,updated_at=? WHERE id=?",
                            (name, now_iso(), asset_id))
            self.audit.record("physical_item", asset_id, "edit", f"Updated {name}", before, after)

    def record_valuation(self, asset_id: int, day: str, total_value, notes: str = "") -> None:
        day = parse_date(day).isoformat()
        if parse_date(day) > today():
            raise ValidationError("A valuation cannot be dated in the future.", "date")
        value = check_places(to_decimal(total_value, "value"), 2, "value")
        if value < 0:
            raise ValidationError("Valuation cannot be negative.", "value")
        quantity = self.db.scalar("SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le "
                                  "JOIN transactions t ON t.id=le.transaction_id WHERE le.asset_id=? "
                                  "AND le.date<=? AND t.status='POSTED'", (asset_id, day)) or 0
        if int(quantity) <= 0:
            raise ValidationError("Add the item to this account before valuing it.")
        with self.db.transaction():
            self.db.execute("INSERT INTO physical_item_valuations(asset_id,date,quantity_e6,total_value_e6,notes,created_at) "
                            "VALUES(?,?,?,?,?,?)", (asset_id, day, int(quantity), to_e6(value),
                                                       (notes or "").strip(), now_iso()))

    def valuations(self, asset_id: int) -> list[dict]:
        return [dict(row) for row in self.db.all("SELECT date,quantity_e6,total_value_e6,notes "
                                                  "FROM physical_item_valuations WHERE asset_id=? "
                                                  "ORDER BY date DESC,id DESC", (asset_id,))]

    def record_trade_details(self, transaction_id: int, asset_id: int, action: str,
                             workmanship_cost, notes: str = "") -> None:
        cost = check_places(to_decimal(workmanship_cost or "0", "workmanship"), 2, "workmanship")
        if cost < 0:
            raise ValidationError("Workmanship cost cannot be negative.", "workmanship")
        if action not in {"BUY", "SEL", "OPN"}:
            raise ValidationError("Unknown item activity.")
        self.db.execute("INSERT INTO physical_item_trade_details(transaction_id,asset_id,action,workmanship_cost_e6,notes) "
                        "VALUES(?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET asset_id=excluded.asset_id,"
                        "action=excluded.action,workmanship_cost_e6=excluded.workmanship_cost_e6,notes=excluded.notes",
                        (transaction_id, asset_id, action, to_e6(cost), (notes or "").strip()))

    def trade_details_for_account(self, account_id: int) -> list[dict]:
        return [dict(row) for row in self.db.all(
            "SELECT d.* FROM physical_item_trade_details d JOIN physical_items p ON p.asset_id=d.asset_id "
            "WHERE p.account_id=?", (account_id,))]

    def _snapshot(self, asset_id: int) -> dict:
        item = self.get(asset_id)
        return {"name": self.assets.get_asset(asset_id).name, "kind": item["item_kind"],
                "grams_per_piece": str(Decimal(item["net_gold_grams_e6"]) / Decimal(1_000_000)),
                "karat": item["karat"], "reference_asset_id": item["reference_asset_id"],
                "details": item["details"]}
