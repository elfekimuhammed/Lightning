from datetime import date
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


def test_cash_ownership_can_be_reassigned_without_changing_account_balance(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "20000")
    dad = c.counterparties.create("Dad")

    txn = c.transactions.change_cash_ownership("2026-09-10", bank.id, "5000", None, dad)

    assert txn.type == DocType.ADJ
    assert c.reporting.account_balance(bank.id, "2026-09-10") == Decimal("20000")
    assert c.reporting.money_from_others_total("2026-09-10") == Decimal("5000")
    assert c.transactions.summarize(txn).type_label == "Ownership change"
    with pytest.raises(ValidationError, match="user's balance"):
        c.transactions.change_cash_ownership("2026-09-11", bank.id, "16000", None, dad)


def test_external_expense_reduces_owned_cash_and_counts_as_spending(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "20000")
    dad = c.counterparties.create("Dad")
    category = c.categories.get_by_code("EXP.PERSONAL.FOOD")
    item_id = c.planning.create(kind="BILL", name="Groceries", amount="2500", frequency="MONTHLY",
                                start_date="2026-09-10", account_id=str(bank.id),
                                category_id=str(category.id), counterparty_id=str(dad))

    txn = c.transactions.record_expense_paid_by_person(
        "2026-09-10", bank.id, "2500", dad, category.id, "Dad paid groceries")

    assert c.reporting.account_balance(bank.id, "2026-09-10") == Decimal("20000")
    assert c.reporting.money_from_others_total("2026-09-10") == Decimal("2500")
    assert c.reporting.cash_flow("2026-09-01", "2026-09-30").outflows == Decimal("2500")
    assert c.transactions.summarize(txn).type_label == "Expense paid for you"
    assert c.transactions.summarize(txn).category_label == c.categories.display_name(category.id)
    assert c.planning.match_payments(date.fromisoformat("2026-09-30")) == 1
    payment = c.planning.payments(c.planning.get(item_id), "2026-09-30", date.fromisoformat("2026-09-30"))[0]
    assert payment.transaction_id == txn.id


def test_external_expense_can_settle_a_planned_payment_and_reserve(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "20000")
    dad = c.counterparties.create("Dad")
    category = c.categories.get_by_code("EXP.PERSONAL.FOOD")
    reserve = c.reserves.create("Groceries", "3000", category_id=category.id)
    c.reserves.allocate(reserve["id"], "3000")
    txn = c.transactions.record_expense_paid_by_person(
        "2026-09-10", bank.id, "2500", dad, category.id, "Dad paid groceries")

    c.reserves.set_expense_link(reserve["id"], txn.id, "2500")
    linked = c.reserves.links_for_transaction(txn.id)
    assert linked[0]["amount"] == Decimal("2500")


def test_voiding_owned_cash_cannot_make_the_owner_balance_negative(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "0")
    dad = c.counterparties.create("Dad")
    salary = c.categories.get_by_code("EXP.WORK.SALARY")
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD")
    deposit = c.transactions.record_inflow("2026-09-10", bank.id, "2000", salary.id, owner_id=dad)
    c.transactions.record_outflow("2026-09-11", bank.id, "1500", food.id, owner_id=dad)

    with pytest.raises(ValidationError, match="selected owner's balance"):
        c.transactions.void(deposit.id)
    assert not c.transactions.get(deposit.id).is_void
