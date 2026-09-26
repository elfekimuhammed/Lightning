from __future__ import annotations

import pytest

from lightning.core.errors import ConflictError


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
