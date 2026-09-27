from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError
from lightning.ui.routes.physical_items import _references


def setup_ring(c):
    physical = c.account_flows.open_account("Gold at home", "PHYSICAL_ASSET", "2026-01-01", "0")
    cash = c.account_flows.open_account("Bank", "BANK", "2026-01-01", "10000")
    reference = c.assets.get_asset_by_code("GLD:18K")
    c.assets.set_price(reference.id, "2026-09-01", "1000")
    item_id = c.physical_items.create(physical.id, "Gold ring", "Ring", "4.2", 18,
                                      reference.id, "One small stone")
    return physical, cash, reference, item_id


def test_item_value_uses_matching_karat_price_once_and_cost_stays_separate(c):
    physical, cash, reference, item_id = setup_ring(c)
    c.investments.buy_total("2026-09-01", physical.id, item_id, "1", "4200", cash.id)

    position = c.investments.portfolio("2026-09-01", physical.id).open[0]
    assert position.quantity == Decimal("1")
    assert position.value == Decimal("4200")  # 4.2g × 1,000; no extra 18/24 multiplier
    assert position.cost_basis == Decimal("4200")
    assert position.price_date == "2026-09-01"
    assert c.reporting.account_value(physical.id, "2026-09-01") == Decimal("4200")
    assert c.reporting.net_worth("2026-09-01").total == Decimal("10000")

    c.assets.set_price(reference.id, "2026-09-02", "1200")
    position = c.investments.portfolio("2026-09-02", physical.id).open[0]
    assert position.value == Decimal("5040")
    assert position.cost_basis == Decimal("4200")


def test_manual_item_valuation_and_metadata_edit_are_audited(c):
    physical, cash, reference, item_id = setup_ring(c)
    c.investments.add_holding(physical.id, item_id, "1", "3500", "2026-09-01")
    c.physical_items.record_valuation(item_id, "2026-09-02", "3300", "Local jeweller estimate")
    assert c.reporting.account_value(physical.id, "2026-09-02") == Decimal("3300")

    c.physical_items.update(item_id, "Gold ring", "Ring", "5", 18, reference.id, "Description corrected")
    position = c.investments.portfolio("2026-09-02", physical.id).open[0]
    assert position.value == Decimal("3300")  # the dated manual total remains a recorded fact
    assert position.cost_basis == Decimal("3500")
    assert c.audit.history("physical_item", item_id)[0]["action"] == "edit"


def test_missing_reference_price_is_explicitly_valued_at_cost(c):
    physical = c.account_flows.open_account("Gold at home", "PHYSICAL_ASSET", "2026-01-01", "0")
    reference = c.assets.get_asset_by_code("GLD:18K")
    item_id = c.physical_items.create(physical.id, "Gold ring", "Ring", "4.2", 18,
                                      reference.id, "")
    c.investments.add_holding(physical.id, item_id, "1", "3500", "2026-09-01")
    position = c.investments.portfolio("2026-09-02", physical.id).open[0]
    assert position.value == Decimal("3500")
    assert position.price_source == "COST"


def test_purchase_and_sale_post_cash_and_piece_quantity_with_oversell_guard(c):
    physical, cash, _reference, item_id = setup_ring(c)
    before = c.reporting.net_worth("2026-09-01").total
    c.investments.buy_total("2026-09-01", physical.id, item_id, "1", "4200", cash.id)
    assert c.investments.holding(physical.id, item_id, "2026-09-01") == Decimal("1")
    assert c.reporting.net_worth("2026-09-01").total == before

    with pytest.raises(ValidationError):
        c.investments.sell_total("2026-09-02", physical.id, item_id, "2", "9000", cash.id)

    c.investments.sell_total("2026-09-02", physical.id, item_id, "1", "4200", cash.id)
    assert c.investments.holding(physical.id, item_id, "2026-09-02") == Decimal("0")


def test_item_custody_ownership_and_existing_gram_gold_remain_separate(c):
    physical, cash, reference, item_id = setup_ring(c)
    c.counterparties.create("Dad")
    owner = c.counterparties.resolve("Dad")
    txn = c.investments.buy_total("2026-09-01", physical.id, item_id, "1", "4200", cash.id)
    c.money_from_others.sync_investment(txn.id, txn.date, owner["name"], physical.id, item_id, Decimal("1"))
    assert c.reporting.account_value(physical.id, "2026-09-01") == Decimal("4200")
    assert c.reporting.owned_account_value(physical.id, "2026-09-01") == Decimal("0")

    grams = c.assets.create_investment("Existing 18K grams", "GOLD", "EXISTING18", 18)
    c.assets.set_price(grams.id, "2026-09-01", "1000")
    c.investments.add_holding(physical.id, grams.id, "10", "8000", "2026-09-01")
    positions = {position.asset_id: position for position in c.investments.portfolio("2026-09-01", physical.id).open}
    assert positions[grams.id].quantity == Decimal("10")
    assert positions[grams.id].value == Decimal("10000")
    assert positions[item_id].value == Decimal("4200")


def test_invalid_karat_does_not_crash_reference_filter(c):
    physical, _cash, _reference, _item_id = setup_ring(c)
    assert _references(c, c.accounts.get(physical.id), "not-a-karat") == []
