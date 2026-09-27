from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError
from lightning.core.ledger import Effect, PostingLine
from lightning.core.refs import DocType


def test_brokerage_buy_cannot_spend_another_owners_cash(c):
    broker = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "0")
    owner_id = c.counterparties.create("Dad")
    income = c.categories.get_by_code("EXP.WORK.SALARY")
    cash = c.assets.cash_asset("EGP")
    c.transactions.post(DocType.IN, "2026-09-10", [
        PostingLine.cash(broker.id, cash.id, Decimal("2000"), Effect.INFLOW, income.id,
                         memo="Dad cash", owner_id=owner_id)
    ])
    c.transactions.record_inflow("2026-09-10", broker.id, "5000", income.id, description="My cash")
    shares = c.assets.create_investment("Test share", "STOCK", "MILESTONE")

    with pytest.raises(ValidationError, match="selected owner"):
        c.investments.buy("2026-09-11", broker.id, shares.id, "1", "3000", owner_id=owner_id)

    txn = c.investments.buy("2026-09-11", broker.id, shares.id, "1", "1500", owner_id=owner_id)
    assert {line.owner_id for line in txn.lines} == {owner_id}
    assert c.reporting.account_balance(broker.id, "2026-09-11") == Decimal("5500")


def test_manual_custody_adjustment_is_a_zero_sum_ledger_posting(c):
    bank = c.account_flows.open_account("Bank", "BANK", "2026-09-01", "5000")
    owner_id = c.counterparties.create("Dad")
    c.money_from_others.record("2026-09-10", "Dad", bank.id, Decimal("1200"))

    cash = c.assets.cash_asset("EGP")
    assert c.reporting.account_balance(bank.id, "2026-09-10") == Decimal("5000")
    assert c.db.scalar("SELECT SUM(quantity_e6) FROM ledger_entries WHERE account_id=? AND asset_id=?",
                       (bank.id, cash.id)) == 5000 * 1_000_000
    assert c.db.scalar("""SELECT SUM(quantity_e6) FROM ledger_entries WHERE account_id=? AND asset_id=?
                          AND owner_id=?""", (bank.id, cash.id, owner_id)) == 1200 * 1_000_000


def test_existing_holding_preserves_owner_when_created_and_edited(c):
    broker = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "0")
    owner_id = c.counterparties.create("Dad")
    asset = c.assets.create_investment("Test share", "STOCK", "HOLDING")

    txn = c.investments.add_holding(broker.id, asset.id, "2", "1000", "2026-09-10", owner_id=owner_id)
    assert {line.owner_id for line in txn.lines} == {owner_id}

    updated = c.investments.update(txn.id, account_id=broker.id, asset_id=asset.id,
                                   quantity="3", total_cost="1500", date="2026-09-10",
                                   notes="", owner_id=owner_id)
    assert {line.owner_id for line in updated.lines} == {owner_id}


def test_physical_purchase_uses_selected_owners_cash_and_holding(c):
    physical = c.account_flows.open_account("Gold at home", "PHYSICAL_ASSET", "2026-09-01", "0")
    bank = c.account_flows.open_account("Bank", "BANK", "2026-09-01", "5000")
    dad = c.counterparties.create("Dad")
    cash = c.assets.cash_asset("EGP")
    salary = c.categories.get_by_code("EXP.WORK.SALARY")
    c.transactions.record_inflow("2026-09-10", bank.id, "2000", salary.id, owner_id=dad)
    reference = c.assets.get_asset_by_code("REF:GLD-24K")
    c.assets.set_price(reference.id, "2026-09-10", "10000")
    ring = c.physical_items.create(physical.id, "Ring", "Ring", "4", 18, reference.id)

    with pytest.raises(ValidationError, match="selected owner's"):
        c.investments.buy_total("2026-09-11", physical.id, ring, "1", "3000", bank.id, owner_id=dad)

    bought = c.investments.buy_total("2026-09-11", physical.id, ring, "1", "1500", bank.id, owner_id=dad)
    assert {line.owner_id for line in bought.lines} == {dad}
    with pytest.raises(ValidationError, match="less than zero"):
        c.investments.sell_total("2026-09-12", physical.id, ring, "2", "3000", bank.id, owner_id=dad)
    assert c.reporting.account_balance(bank.id, "2026-09-11") == Decimal("5500")


def test_internal_cash_spend_checks_the_owners_dated_balance(c):
    broker = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "0")
    dad = c.counterparties.create("Dad")
    salary = c.categories.get_by_code("EXP.WORK.SALARY")
    c.transactions.record_inflow("2026-09-10", broker.id, "2000", salary.id, owner_id=dad)
    shares = c.assets.create_investment("Test share", "STOCK", "CASHCHECK")
    with pytest.raises(ValidationError, match="selected owner's"):
        c.investments.buy_total("2026-09-11", broker.id, shares.id, "1", "2500", owner_id=dad)
