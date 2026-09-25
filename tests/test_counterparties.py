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
