"""Financial assets say where they trade (ISO 10383 MIC, ISO 3166 country, ISIN) and can all be edited."""

import shutil

import pytest
from fastapi.testclient import TestClient

from lightning.core.errors import ConflictError, ValidationError
from lightning.database import migrator
from lightning.database.connection import Database
from lightning.ui.web import create_app


def test_migration_0041_marks_existing_stocks_as_egx_listings(monkeypatch, tmp_path):
    before = tmp_path / "migrations"
    before.mkdir()
    for path in sorted(migrator._BUNDLED_MIGRATIONS_DIR.glob("*.sql")):
        if int(path.name[:4]) <= 40:
            shutil.copy(path, before / path.name)
    db = Database(":memory:")
    monkeypatch.setattr(migrator, "MIGRATIONS_DIR", before)
    migrator.migrate(db)
    for code in ("STOCK", "FUND.EQUITY"):  # classes come from the seed, not from migrations
        db.execute("INSERT INTO asset_classes(code,name,created_at,updated_at) VALUES (?,?,'2026-10-01','2026-10-01')",
                   (code, code))
    stock_class = db.scalar("SELECT id FROM asset_classes WHERE code='STOCK'")
    fund_class = db.scalar("SELECT id FROM asset_classes WHERE code='FUND.EQUITY'")
    for code, class_id in (("STK:COMI", stock_class), ("FND:AZS", fund_class)):
        db.execute("INSERT INTO financial_assets(code,name,asset_class_id,currency,unit,quantity_decimals,is_cash,exposure,"
                   "liquidity,price_source,active,notes,created_at,updated_at) VALUES (?,?,?,'EGP','unit',4,0,'EQUITY',"
                   "'DAYS','MANUAL',1,'','2026-10-01','2026-10-01')", (code, code, class_id))
    monkeypatch.setattr(migrator, "MIGRATIONS_DIR", migrator._BUNDLED_MIGRATIONS_DIR)
    assert migrator.migrate(db)[0] == "0041_asset_venue (APPLIED)"  # later migrations follow
    rows = {r["code"]: (r["mic"], r["country"], r["market_key"]) for r in db.all("SELECT * FROM financial_assets")}
    assert rows == {"STK:COMI": ("XCAI", "EG", "EG:COMI"), "FND:AZS": (None, "EG", None)}


def test_a_new_asset_takes_its_exchange_country_and_market_key(c):
    comi = c.assets.create_investment("Commercial International Bank", "STOCK", "COMI", isin="egs60121c018")
    assert (comi.mic, comi.country, comi.market_key, comi.exchange, comi.isin) == ("XCAI", "EG", "EG:COMI", "EGX", "EGS60121C018")
    apple = c.assets.create_investment("Apple", "STOCK", "AAPL", isin="US0378331005", mic="XNAS")
    assert (apple.country, apple.market_key, apple.exchange) == ("US", "US:AAPL", "Nasdaq")
    fund = c.assets.create_investment("AZ Savings Fund", "FUND.FIXED_INCOME", "AZS")
    assert (fund.mic, fund.country, fund.market_key) == (None, "EG", None)
    with pytest.raises(ValidationError, match="check digit"):
        c.assets.create_investment("Typo", "STOCK", "TYPO", isin="EGS60121C019")
    with pytest.raises(ValidationError, match="four letters"):
        c.assets.create_investment("Bad venue", "STOCK", "BADV", mic="EGX!")


def test_editing_renames_the_ticker_keeps_the_history_and_refuses_a_taken_one(c, setup):
    accounts, _ = setup
    comi = c.assets.create_investment("Commercial International Bank", "STOCK", "COMI")
    c.assets.create_investment("Telecom Egypt", "STOCK", "ETEL")
    c.assets.set_price(comi.id, "2026-09-30", "85.25")
    renamed = c.assets.update_investment(comi.id, "CIB", "STOCK", "EGS60121C018", "", True, ticker="CIB", mic="XCAI")
    assert (renamed.id, renamed.code, renamed.market_key) == (comi.id, "STK:CIB", "EG:CIB")
    assert c.assets.price_history(comi.id)[0].price == 85.25  # history stays with the asset
    with pytest.raises(ConflictError, match="already exists"):
        c.assets.update_investment(comi.id, "CIB", "STOCK", "", "", True, ticker="ETEL")
    hidden = c.assets.update_investment(comi.id, "CIB", "STOCK", "", "", False)
    assert hidden.active is False and hidden.code == "STK:CIB"


def test_the_financial_assets_page_lists_and_edits_everything(c, setup):
    accounts, _ = setup
    comi = c.assets.create_investment("Commercial International Bank", "STOCK", "COMI", isin="EGS60121C018")
    c.transactions.record_transfer("2026-09-01", accounts["cib"].id, accounts["thndr"].id, "5000")
    c.investments.buy("2026-09-02", accounts["thndr"].id, comi.id, "10", "80")
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    page = client.get("/investments/assets").text
    assert "Commercial International Bank" in page and ">EGX</span>" in page and "EGS60121C018" in page
    assert "REF:GLD" not in page and "CASH:" not in page  # price references and currencies are not listed
    form = client.get(f"/investments/assets/{comi.id}/edit").text
    assert 'value="COMI"' in form and '<option value="XCAI" selected>EGX · XCAI</option>' in form
    saved = client.post(f"/investments/assets/{comi.id}/edit", data={
        "name": "CIB", "class_code": "STOCK", "symbol": "COMI", "isin": "EGS60121C018", "mic": "XCAI", "active": "1"})
    assert saved.status_code == 200 and "Saved CIB." in saved.text
    refused = client.post(f"/investments/assets/{comi.id}/edit", data={
        "name": "CIB", "class_code": "STOCK", "symbol": "COMI", "isin": "EGS60121C019", "mic": "XCAI", "active": "1"})
    assert refused.status_code == 400 and "check digit" in refused.text
    assert "/investments/assets?return_to=/investments" in client.get("/investments").text
    # Financial assets are the Holdings tab's settings: its gear opens them (two levels, 2026-10-06).
    assert 'href="/investments" aria-current="page">' in page
    assert 'href="/investments/assets" data-popup-open aria-label="Financial assets"' in client.get("/investments").text
