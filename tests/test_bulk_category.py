"""Bulk edit: one category for several selected rows (user feedback, batch 001, ticket 20)."""
from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError


def test_selected_rows_take_one_category_and_keep_everything_else(c, setup):
    accounts, cats = setup
    cib = accounts["cib"].id
    food, software = cats["EXP.PERSONAL.FOOD"], cats["EXP.WORK.SOFTWARE"]
    a = c.transactions.record_outflow("2026-09-05", cib, "120", software.id, counterparty="Talabat", notes="lunch")
    b = c.transactions.record_outflow("2026-09-06", cib, "80", software.id, counterparty="Talabat")
    pay = c.transactions.record_inflow("2026-09-01", cib, "30000", cats["EXP.WORK.SALARY"].id, counterparty="ACME")
    move = c.transactions.record_transfer("2026-09-07", cib, accounts["wallet"].id, "500")
    changed, skipped = c.transactions.set_category([a.id, b.id, pay.id, move.id], food.id)
    assert changed == [a.id, b.id] and skipped == [pay.id, move.id]   # pay is money in; a transfer has no category
    after = c.transactions.get(a.id)
    assert [line.category_id for line in after.lines if line.category_id] == [food.id]
    assert after.counterparty == "Talabat" and after.notes == "lunch" and after.date == "2026-09-05"
    assert c.reporting.account_balance(cib) == Decimal("50000") - 120 - 80 + 30000 - 500


def test_a_system_category_is_refused(c, setup):
    accounts, cats = setup
    row = c.transactions.record_outflow("2026-09-05", accounts["cib"].id, "120", cats["EXP.PERSONAL.FOOD"].id)
    for code in ("EXP.SYSTEM.CUSTODY", "EXP.UNACCOUNTED"):
        with pytest.raises(ValidationError):
            c.transactions.set_category([row.id], c.categories.get_by_code(code).id)
