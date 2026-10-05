"""#tags in a transaction's notes: written as text, shown as links, and a filter with its own money in and out."""

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from lightning.transactions.tags import normalize, split, tags_in
from lightning.ui.web import create_app


@pytest.mark.parametrize("note, tags", [
    ("Eid gifts #Eid #eid #sahel-trip", ["eid", "sahel-trip"]),   # one tag whatever the case
    ("#عيد للأولاد", ["عيد"]),                                     # Arabic letters
    ("tea #eid, then #Eid.", ["eid"]),                              # punctuation ends a tag
    ("#2026eid", ["2026eid"]),
    ("invoice #4521", []), ("C# course", []), ("x#tag", []), ("#__", []), ("", []), (None, []),
])
def test_a_tag_is_a_hash_word_with_a_letter(note, tags):
    assert tags_in(note) == tags


def test_a_note_splits_into_text_and_tags():
    assert split("Gifts #Eid, sweets") == [("Gifts ", ""), ("#Eid", "eid"), (", sweets", "")]
    assert normalize("#Eid") == "eid" and normalize("4521") == "" and normalize("#") == ""


@pytest.fixture
def eid(c, setup):
    accounts, cats = setup
    cib, wallet, food = accounts["cib"].id, accounts["wallet"].id, cats["EXP.PERSONAL.FOOD"]
    salary = cats["EXP.WORK.SALARY"]
    c.transactions.record_outflow("2026-09-10", cib, "1,500", food.id, notes="Kahk and biscuits #Eid")
    c.transactions.record_outflow("2026-09-11", wallet, "600", food.id, notes="#eid gifts for the kids")
    c.transactions.record_inflow("2026-09-12", cib, "1,000", salary.id, notes="Eid bonus #eid")
    c.transactions.record_outflow("2026-09-13", cib, "250", food.id, notes="#eid2026 is another tag")
    c.transactions.record_outflow("2026-09-14", cib, "90", food.id, notes="no tag here: eid")
    return c


def test_a_tag_finds_its_transactions_exactly_with_their_money(eid):
    ids = eid.transactions.tag_transaction_ids("#EID")
    assert len(ids) == 3  # never #eid2026, never the word without #
    assert eid.reporting.money_in_out(ids) == (D("1000"), D("2100"))
    assert eid.transactions.tags() == [("eid", 3), ("eid2026", 1)]


def test_notes_link_their_tags_and_the_link_opens_every_tagged_transaction(eid, setup):
    accounts, _ = setup
    client = TestClient(create_app(eid))
    account = client.get(f"/accounts/{accounts['cib'].id}").text
    assert 'Kahk and biscuits <a class="note-tag" href="/transactions?tag=eid">#Eid</a>' in account

    tagged = client.get("/transactions?tag=eid").text
    assert "Tagged #eid · 3 transactions · Money in 1,000.00 · Money out 2,100.00" in tagged
    assert "Kahk and biscuits" in tagged and "gifts for the kids" in tagged and "another tag" not in tagged
    assert ">Clear</a>" in tagged

    # typing the tag in a register's search is the same exact filter, for that account only
    searched = client.get(f"/accounts/{accounts['cib'].id}?q=%23eid").text
    assert "Tagged #eid · 2 transactions · Money in 1,000.00 · Money out 1,500.00" in searched
    assert "another tag" not in searched


def test_a_tag_nobody_used_shows_nothing(eid):
    page = TestClient(create_app(eid)).get("/transactions?tag=ramadan").text
    assert "Tagged #ramadan · 0 transactions · Money in 0.00 · Money out 0.00" in page
