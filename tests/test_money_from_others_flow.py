from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError


def test_custody_category_links_cash_transaction_and_excludes_it_from_owned_totals(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "1000")
    category = c.categories.get_by_code("EXP.PERSONAL.CUSTODY")
    dad_id = c.counterparties.create("Dad")
    dad = c.counterparties.get(dad_id)["name"]

    receipt = c.transactions.record_in_account(bank.id, "2026-09-10", "500", category.id)
    c.money_from_others.sync_transaction(receipt.id, receipt.date, dad, bank.id, Decimal("500"))
    assert c.reporting.account_balance(bank.id) == Decimal("1500")
    assert c.reporting.owned_account_value(bank.id, "2026-09-30") == Decimal("1000")
    assert c.reporting.money_from_others_total("2026-09-30") == Decimal("500")
    assert c.reporting.cash_flow("2026-09-01", "2026-09-30").inflows == 0

    returned = c.transactions.record_in_account(bank.id, "2026-09-12", "-125", category.id)
    c.money_from_others.sync_transaction(returned.id, returned.date, dad, bank.id, Decimal("-125"))
    assert c.reporting.money_from_others_total("2026-09-30") == Decimal("375")
    with pytest.raises(ValidationError, match="more than the money currently held"):
        with c.db.transaction():
            excess = c.transactions.record_in_account(bank.id, "2026-09-13", "-500", category.id)
            c.money_from_others.sync_transaction(excess.id, excess.date, dad, bank.id, Decimal("-500"))


def test_investment_units_can_be_attributed_to_another_person(c, setup):
    accounts, _ = setup
    stock = c.assets.create_investment("CIB Shares", "STOCK", "COMI")
    before = c.reporting.net_worth("2026-09-30").total
    buy = c.investments.buy_total("2026-09-10", accounts["thndr"].id, stock.id, "20", "2000",
                                  accounts["cib"].id)
    c.money_from_others.sync_investment(buy.id, buy.date, "Dad", accounts["thndr"].id, stock.id,
                                        Decimal("10"))
    assert c.reporting.money_from_others_total("2026-09-30") == Decimal("1000")
    assert c.reporting.net_worth("2026-09-30").total == before - Decimal("1000")
    with pytest.raises(ValidationError, match="not enough units owned by Dad"):
        with c.db.transaction():
            sale = c.investments.sell_total("2026-09-11", accounts["thndr"].id, stock.id, "11", "1100",
                                            accounts["cib"].id)
            c.money_from_others.sync_investment(sale.id, sale.date, "Dad", accounts["thndr"].id, stock.id,
                                                Decimal("-11"))


def test_csv_import_can_tag_held_for_others_with_whom(c):
    bank = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "1000")
    category = c.categories.get_by_code("EXP.PERSONAL.CUSTODY")
    c.counterparties.create("Dad")
    batch_id, repeated = c.bank_imports.stage(
        bank.id, "statement.csv",
        b"Date,Amount,Counterparty,Category,Notes\n2026-09-10,300,Transfer from Dad,,Family money\n",
    )
    assert not repeated
    _, rows = c.bank_imports.preview(batch_id)
    result = c.bank_imports.confirm(batch_id, {
        rows[0]["_import_row_id"]: {"date": "2026-09-10", "amount": "300", "counterparty": "Dad",
                                   "category_id": category.id, "whom": "Dad"}
    })
    assert result["posted"] == 1
    assert c.reporting.account_balance(bank.id) == Decimal("1300")
    assert c.reporting.owned_account_value(bank.id, "2026-09-30") == Decimal("1000")


def test_internal_transfer_moves_custody_cash_without_double_counting(c, setup):
    accounts, _ = setup
    source, target = accounts["cib"], accounts["thndr"]
    dad_id = c.counterparties.create("Dad")
    dad = c.counterparties.get(dad_id)["name"]
    category = c.categories.get_by_code("EXP.PERSONAL.CUSTODY")
    receipt = c.transactions.record_in_account(source.id, "2026-09-10", "1000", category.id)
    c.money_from_others.sync_transaction(receipt.id, receipt.date, dad, source.id, Decimal("1000"))

    transfer = c.transactions.record_transfer("2026-09-11", source.id, target.id, "1000")
    c.money_from_others.sync_transfer(transfer.id, transfer.date, dad, source.id, target.id, Decimal("1000"))
    assert c.money_from_others.cash_balance(dad, source.id, "2026-09-30") == 0
    assert c.money_from_others.cash_balance(dad, target.id, "2026-09-30") == Decimal("1000")
    assert c.reporting.money_from_others_total("2026-09-30") == Decimal("1000")

    asset = c.assets.create_investment("CIB Shares", "STOCK", "COMI")
    purchase = c.investments.buy_total("2026-09-12", target.id, asset.id, "10", "1000", target.id)
    c.money_from_others.sync_investment(purchase.id, purchase.date, dad, target.id, asset.id, Decimal("10"))
    c.money_from_others.sync_transaction(purchase.id, purchase.date, dad, target.id, Decimal("-1000"))
    assert c.reporting.money_from_others_total("2026-09-30") == Decimal("1000")
