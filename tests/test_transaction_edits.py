"""Edits to recorded transactions: category splits, owners, refunds, reserve unlinks and counterparty
aliases, each changing only what it should."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.ui.web import create_app


def client(c):
    return TestClient(create_app(c), base_url="http://127.0.0.1")


def food_and_transport(c):
    return c.categories.get_by_code("EXP.PERSONAL.FOOD"), c.categories.get_by_code("EXP.PERSONAL.TRANSPORT")


# -- category split ------------------------------------------------------------

def test_a_split_keeps_the_balance_and_moves_the_category_totals(c, setup):
    accounts, _ = setup
    food, transport = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)

    split = c.transactions.update_expense_split(txn.id, [(food.id, "600"), (transport.id, "400")])

    assert split.ref == txn.ref
    assert sorted(line.quantity for line in split.lines) == [Decimal("-600"), Decimal("-400")]
    assert c.reporting.account_balance(accounts["cib"].id) == Decimal("49000")
    totals = c.reporting.money_out_by_category("2026-09-01", "2026-09-30")
    assert totals[food.id] == Decimal("600") and totals[transport.id] == Decimal("400")


def test_split_amounts_must_add_up_to_the_total(c, setup):
    accounts, _ = setup
    food, transport = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)
    with pytest.raises(ValidationError, match="add up to the transaction total"):
        c.transactions.update_expense_split(txn.id, [(food.id, "600"), (transport.id, "300")])
    assert [line.quantity for line in c.transactions.get(txn.id).lines] == [Decimal("-1000")]


@pytest.mark.parametrize("amount", ["0", "-100"])
def test_a_split_amount_of_zero_or_less_is_refused(c, setup, amount):
    accounts, _ = setup
    food, transport = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)
    with pytest.raises(ValidationError, match="greater than zero"):
        c.transactions.update_expense_split(txn.id, [(food.id, "1000"), (transport.id, amount)])


def test_a_split_into_an_income_category_is_refused(c, setup):
    accounts, cats = setup
    food, _ = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)
    with pytest.raises(ValidationError, match="expense category"):
        c.transactions.update_expense_split(txn.id, [(food.id, "500"), (cats["EXP.WORK.SALARY"].id, "500")])


def test_a_split_into_the_custody_category_is_refused(c, setup):
    accounts, _ = setup
    food, _ = food_and_transport(c)
    custody = c.categories.get_by_code("EXP.SYSTEM.CUSTODY")
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)
    # Custody is an INFLOW category, so the expense-category check refuses it before the custody check.
    with pytest.raises(ValidationError, match="expense category for each split row"):
        c.transactions.update_expense_split(txn.id, [(food.id, "500"), (custody.id, "500")])


def test_an_expense_already_in_the_custody_category_cannot_be_split(c, setup):
    accounts, _ = setup
    food, _ = food_and_transport(c)
    custody = c.categories.get_by_code("EXP.SYSTEM.CUSTODY")
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", custody.id,
                                        allow_system_category=True)
    with pytest.raises(ValidationError, match="Money held for others cannot be split"):
        c.transactions.update_expense_split(txn.id, [(food.id, "1000")])


def test_the_split_form_saves_a_valid_split_and_redirects_back(c, setup):
    accounts, _ = setup
    food, transport = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)

    response = client(c).post(f"/transactions/{txn.id}/split", follow_redirects=False, data={
        "split_category_id": [str(food.id), str(transport.id), ""], "split_amount": ["700", "300", ""]})

    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/transactions/{txn.id}?msg=Updated%20{txn.ref}")
    assert c.reporting.money_out_by_category("2026-09-01", "2026-09-30")[transport.id] == Decimal("300")
    assert c.reporting.account_balance(accounts["cib"].id) == Decimal("49000")


def test_the_split_form_shows_the_error_and_changes_nothing_when_amounts_do_not_add_up(c, setup):
    accounts, _ = setup
    food, transport = food_and_transport(c)
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "1000", food.id)

    response = client(c).post(f"/transactions/{txn.id}/split", follow_redirects=False, data={
        "split_category_id": [str(food.id), str(transport.id)], "split_amount": ["700", "200"]})

    assert response.status_code == 303
    assert "add%20up" in response.headers["location"]
    assert [line.category_id for line in c.transactions.get(txn.id).lines] == [food.id]


# -- owner ---------------------------------------------------------------------

def test_giving_a_payment_to_an_owner_with_no_cash_is_refused(c, setup):
    accounts, _ = setup
    food, _ = food_and_transport(c)
    dad = c.counterparties.create("Dad")
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "300", food.id)
    with pytest.raises(ValidationError, match="selected owner's balance"):
        c.transactions.set_transaction_owner(txn.id, dad)
    assert {line.owner_id for line in c.transactions.get(txn.id).lines} == {None}


def test_changing_the_owner_sets_it_on_every_ledger_line(c, setup):
    accounts, cats = setup
    food, _ = food_and_transport(c)
    dad = c.counterparties.create("Dad")
    received = c.transactions.record_inflow("2026-09-10", accounts["cib"].id, "500", cats["EXP.WORK.SALARY"].id)
    spent = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "300", food.id)

    c.transactions.set_transaction_owner(received.id, dad)
    updated = c.transactions.set_transaction_owner(spent.id, dad)

    assert {line.owner_id for line in updated.lines} == {dad}
    assert c.db.scalar("SELECT COUNT(*) FROM ledger_entries WHERE transaction_id IN (?,?) AND owner_id IS NOT ?",
                       (received.id, spent.id, dad)) == 0
    assert c.reporting.account_balance(accounts["cib"].id) == Decimal("50200")
    assert c.transactions.history(spent.id)[0]["summary"] == f"Changed owner on {spent.ref}"


# -- refund --------------------------------------------------------------------

def test_editing_a_refund_keeps_its_ref_logs_history_and_moves_money_out_by_the_difference(c, setup):
    accounts, _ = setup
    food, _ = food_and_transport(c)
    c.transactions.record_outflow("2026-09-10", accounts["cib"].id, "1000", food.id)
    refund = c.transactions.record_refund("2026-09-12", accounts["cib"].id, "200", food.id)
    before = c.reporting.cash_flow("2026-09-01", "2026-09-30").outflows
    assert c.reporting.money_out_by_category("2026-09-01", "2026-09-30")[food.id] == Decimal("800")

    edited = c.transactions.update_refund(refund.id, "2026-09-12", accounts["cib"].id, "350", food.id)

    assert edited.ref == refund.ref
    assert c.transactions.history(refund.id)[0]["action"] == "edit"
    assert c.reporting.cash_flow("2026-09-01", "2026-09-30").outflows == before - Decimal("150")
    assert c.reporting.money_out_by_category("2026-09-01", "2026-09-30")[food.id] == Decimal("650")
    assert c.reporting.account_balance(accounts["cib"].id) == Decimal("49350")


# -- reserve unlink ------------------------------------------------------------

def test_unlinking_a_payment_gives_the_reserve_back_its_amount(c):
    account = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "10000")
    _, transport = food_and_transport(c)
    reserve = c.reserves.create("Car insurance", "9000")
    c.reserves.allocate(reserve["id"], "9000")
    paid = c.transactions.record_outflow("2026-09-10", account.id, "6000", transport.id)
    c.reserves.set_expense_link(reserve["id"], paid.id, "6000")

    def active():
        return next(r for r in c.reserves.list_active() if r["id"] == reserve["id"])

    assert (active()["spent"], active()["effective_allocated"]) == (Decimal("6000"), Decimal("3000"))
    allocated_before = c.reserves.cash_summary(Decimal("0"))["allocated"]

    response = client(c).post(f"/transactions/{paid.id}/reserve", follow_redirects=False,
                              data={"action": "unlink", "reserve_id": str(reserve["id"])})

    assert response.status_code == 303
    assert c.reserves.links_for_transaction(paid.id) == []
    assert (active()["spent"], active()["effective_allocated"]) == (Decimal("0"), Decimal("9000"))
    assert c.reserves.cash_summary(Decimal("0"))["allocated"] == allocated_before + Decimal("6000")


# -- counterparty aliases ------------------------------------------------------

def test_renaming_an_alias_to_another_counterpartys_spelling_is_a_conflict(c):
    talabat = c.counterparties.create("Talabat", alias="Talabaat")
    c.counterparties.create("Breadfast", alias="Bread Fast")
    alias_id = c.counterparties.aliases_for(talabat)[0]["id"]
    for taken in ("Breadfast", "bread fast"):
        with pytest.raises(ConflictError, match="already linked to Breadfast"):
            c.counterparties.rename_alias(talabat, alias_id, taken)
    assert c.counterparties.aliases_for(talabat)[0]["alias"] == "Talabaat"


def test_renaming_an_alias_links_past_transactions_with_no_counterparty(c, setup):
    accounts, cats = setup
    talabat = c.counterparties.create("Talabat", alias="Talabaat")
    alias_id = c.counterparties.aliases_for(talabat)[0]["id"]
    txn = c.transactions.record_outflow("2026-09-20", accounts["cib"].id, "125", cats["EXP.PERSONAL.FOOD"].id,
                                        counterparty="Talabaat")
    other = c.transactions.record_outflow("2026-09-21", accounts["cib"].id, "50", cats["EXP.PERSONAL.FOOD"].id,
                                          counterparty="Talabaat")
    # Rows imported before the counterparty existed: the old spelling, no link yet.
    c.db.execute("UPDATE transactions SET counterparty_id=NULL, counterparty='Tlbt' WHERE id=?", (txn.id,))
    c.db.execute("UPDATE transactions SET counterparty_id=NULL, counterparty='Someone else' WHERE id=?",
                 (other.id,))

    c.counterparties.rename_alias(talabat, alias_id, "  TLBT ")

    assert c.counterparties.resolve("tlbt")["id"] == talabat
    assert c.counterparties.resolve("Talabaat") is None
    linked = c.db.one("SELECT counterparty_id, counterparty FROM transactions WHERE id=?", (txn.id,))
    assert (linked["counterparty_id"], linked["counterparty"]) == (talabat, "Talabat")
    assert c.db.scalar("SELECT counterparty_id FROM transactions WHERE id=?", (other.id,)) is None


def test_removing_an_unknown_alias_is_not_found(c):
    talabat = c.counterparties.create("Talabat", alias="Talabaat")
    breadfast = c.counterparties.create("Breadfast", alias="Bread Fast")
    breadfast_alias = c.counterparties.aliases_for(breadfast)[0]["id"]
    with pytest.raises(NotFoundError):
        c.counterparties.remove_alias(talabat, 999_999)
    with pytest.raises(NotFoundError):
        c.counterparties.remove_alias(talabat, breadfast_alias)
    c.counterparties.remove_alias(breadfast, breadfast_alias)
    assert c.counterparties.aliases_for(breadfast) == []
