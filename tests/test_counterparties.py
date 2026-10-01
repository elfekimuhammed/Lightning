from __future__ import annotations

import pytest

from lightning.core.errors import ConflictError, ValidationError


def test_alias_resolves_to_one_canonical_counterparty(c):
    cid = c.counterparties.create("Talabat", alias="Talabaat")
    assert c.counterparties.resolve("TALABAT")["id"] == cid
    assert c.counterparties.resolve("talabaat")["id"] == cid
    assert c.counterparties.suggestions("Talabaat") == []


def test_approximate_matches_are_suggestions_not_automatic_merges(c):
    cid = c.counterparties.create("Talabat")
    guesses = c.counterparties.suggestions("Talabaat")
    assert guesses and guesses[0][0] == "Talabat"
    assert c.counterparties.resolve("Talabaat") is None
    c.counterparties.add_alias(cid, "Talabaat")
    assert c.counterparties.resolve("Talabaat")["id"] == cid


def test_same_counterparty_cannot_be_created_twice(c):
    c.counterparties.create("Talabat")
    with pytest.raises(ConflictError):
        c.counterparties.create(" talabat ")


def test_transactions_link_confirmed_alias_to_canonical_record(c, setup):
    accounts, cats = setup
    cid = c.counterparties.create("Talabat", alias="Talabaat")
    txn = c.transactions.record_outflow(
        "2026-09-25", accounts["cib"].id, "125", cats["EXP.PERSONAL.FOOD"].id,
        counterparty="Talabaat",
    )
    row = c.db.one("SELECT counterparty_id FROM transactions WHERE id=?", (txn.id,))
    assert row["counterparty_id"] == cid


def test_rename_updates_linked_transaction_display_and_keeps_aliases(c, setup):
    accounts, cats = setup
    cid = c.counterparties.create("NBE", alias="National Bank")
    txn = c.transactions.record_outflow("2026-09-25", accounts["cib"].id, "10",
                                         cats["EXP.PERSONAL.FOOD"].id, counterparty="NBE")
    c.db.execute("UPDATE transactions SET counterparty_id=? WHERE id=?", (cid, txn.id))
    c.counterparties.rename(cid, "National Bank of Egypt")
    assert c.counterparties.resolve("NBE")["id"] == cid
    assert c.db.scalar("SELECT counterparty FROM transactions WHERE id=?", (txn.id,)) == "National Bank of Egypt"


def test_delete_unused_counterparty_removes_aliases_but_used_one_archives(c, setup):
    accounts, cats = setup
    unused = c.counterparties.create("Temporary", alias="Temp")
    assert c.counterparties.delete_or_archive(unused) is False
    assert c.counterparties.get(unused) is None
    assert c.counterparties.resolve("Temp") is None

    used = c.counterparties.create("Employer", alias="My Employer")
    txn = c.transactions.record_inflow("2026-09-25", accounts["cib"].id, "10",
                                       cats["EXP.WORK.SALARY"].id, counterparty="Employer")
    c.db.execute("UPDATE transactions SET counterparty_id=? WHERE id=?", (used, txn.id))
    assert c.counterparties.delete_or_archive(used) is True
    assert c.counterparties.get(used)["active"] == 0
    assert all(party["id"] != used for party in c.counterparties.list_active())
    assert any(party["id"] == used for party in c.counterparties.list_all())
    c.counterparties.set_active(used, True)
    assert c.counterparties.get(used)["active"] == 1


def test_usual_category_is_the_most_picked_in_the_last_20(c, setup):
    accounts, cats = setup
    food, soft = cats["EXP.PERSONAL.FOOD"].id, cats["EXP.WORK.SOFTWARE"].id
    c.counterparties.create("Talabat", alias="Talabaat")
    for day, cat, name in [("2026-09-01", food, "Talabat"), ("2026-09-02", food, "Talabaat"),
                           ("2026-09-03", soft, "Talabat")]:
        c.transactions.record_outflow(day, accounts["cib"].id, "10", cat, counterparty=name)
    usual = c.transactions.usual_categories()["Talabat"]
    assert usual == {"category_id": food, "count": 2, "total": 3}  # the alias counts with its counterparty
    # A tie goes to the most recent pick.
    c.transactions.record_outflow("2026-09-04", accounts["cib"].id, "10", soft, counterparty="Talabat")
    assert c.transactions.usual_categories()["Talabat"]["category_id"] == soft
    # Only the last 20 count: 20 newer software payments outweigh the older food ones.
    for day in range(5, 25):
        c.transactions.record_outflow(f"2026-09-{day:02d}", accounts["cib"].id, "10", soft, counterparty="Talabat")
    assert c.transactions.usual_categories()["Talabat"] == {"category_id": soft, "count": 20, "total": 20}


def test_a_counterparty_holds_up_to_20_aliases(c):
    cid = c.counterparties.create("Vodafone")
    for i in range(20):
        c.counterparties.add_alias(cid, f"Vodafone branch {i}")
    with pytest.raises(ValidationError, match="at most 20"):
        c.counterparties.add_alias(cid, "Vodafone branch 99")
