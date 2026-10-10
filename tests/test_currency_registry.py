from __future__ import annotations

import pytest

from lightning.database.connection import Database
from lightning.database.currencies import CurrencyRegistry
from lightning.database.migrator import migrate
from lightning.database.seed import seed
from lightning.database.settings import SettingsStore


def _registry():
    db = Database(":memory:")
    migrate(db)
    seed(db)
    return db, CurrencyRegistry(db)


def test_iso_suggestions_and_custom_registration_are_separate():
    db, currencies = _registry()
    try:
        assert {r["code"] for r in currencies.suggestions("Egypt")} == {"EGP"}
        assert currencies.list() == [{"code": "EGP", "name": "Egyptian Pound", "is_custom": 0}]
        registered = currencies.register("xyz", "Example Credits")
        assert registered == {"code": "XYZ", "name": "Example Credits", "is_custom": 1}
        assert not any(row["code"] == "XYZ" for row in currencies.suggestions())
        assert db.scalar("SELECT currency FROM financial_assets WHERE code='CASH:XYZ'") == "XYZ"
        assert currencies.register("USD") == {"code": "USD", "name": "US Dollar", "is_custom": 0}
    finally:
        db.close()


def test_base_currency_can_change_before_activity_but_not_after():
    db, currencies = _registry()
    try:
        currencies.register("USD")
        currencies.set_base_currency("USD")
        assert SettingsStore(db).base_currency == "USD"
        assert {row[0] for row in db.all(
            "SELECT currency FROM financial_assets WHERE code IN "
            "('GLD:18K','REF:GLD-21K','REF:GLD-24K')"
        )} == {"USD"}
        db.execute("INSERT INTO fx_rates(date,base,quote,rate_e6,source,created_at) "
                   "VALUES('2026-01-01','USD','EGP',1,'TEST','2026-01-01')")
        with pytest.raises(ValueError, match="cannot change"):
            currencies.set_base_currency("EGP")
    finally:
        db.close()


def test_base_currency_change_updates_unpriced_noncash_assets_in_old_base():
    db, currencies = _registry()
    try:
        currencies.register("USD")
        cash_class = db.scalar("SELECT id FROM asset_classes WHERE code='OTHER'")
        db.execute(
            "INSERT INTO financial_assets(code,name,asset_class_id,currency,unit,quantity_decimals,"
            "is_cash,exposure,liquidity,price_source,created_at,updated_at) "
            "VALUES('OTHER:TEST','Test holding',?,'EGP','unit',2,0,'OTHER','DAYS','MANUAL','now','now')",
            (cash_class,),
        )
        currencies.set_base_currency("USD")
        assert db.scalar("SELECT currency FROM financial_assets WHERE code='OTHER:TEST'") == "USD"
    finally:
        db.close()


def test_base_currency_change_is_blocked_after_gold_reference_prices():
    db, currencies = _registry()
    try:
        currencies.register("USD")
        asset_id = db.scalar("SELECT id FROM financial_assets WHERE code='GLD:18K'")
        db.execute(
            "INSERT INTO price_history(asset_id,date,price_e6,currency,source,created_at) "
            "VALUES(?, '2026-01-01', 100, 'EGP', 'TEST', '2026-01-01')", (asset_id,)
        )
        with pytest.raises(ValueError, match="gold reference prices"):
            currencies.set_base_currency("USD")
        assert SettingsStore(db).base_currency == "EGP"
        assert db.scalar("SELECT currency FROM financial_assets WHERE code='GLD:18K'") == "EGP"
    finally:
        db.close()


def test_existing_base_currency_is_registered_by_migration(tmp_path, monkeypatch):
    from lightning.database import migrator
    import shutil

    db = Database(":memory:")
    try:
        older = tmp_path / "migrations"
        shutil.copytree(migrator._BUNDLED_MIGRATIONS_DIR, older)
        (older / "0049_currency_registry.sql").unlink()
        (older / "0050_cash_at_hand.sql").unlink()
        monkeypatch.setattr(migrator, "MIGRATIONS_DIR", older)
        migrate(db)
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES('base_currency','EGP','old')")
        monkeypatch.setattr(migrator, "MIGRATIONS_DIR", migrator._BUNDLED_MIGRATIONS_DIR)
        migrate(db)
        assert db.scalar("SELECT count(*) FROM registered_currencies WHERE code='EGP'") == 1
    finally:
        db.close()


@pytest.mark.parametrize("code", ["EURO", "1GP", "éGP", "A B"])
def test_custom_code_must_be_three_ascii_letters(code):
    db, currencies = _registry()
    try:
        with pytest.raises(ValueError, match="three letters"):
            currencies.register(code, "Custom")
    finally:
        db.close()
