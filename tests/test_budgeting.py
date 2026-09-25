from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lightning.core.errors import ValidationError
from lightning.ui.web import create_app


@pytest.fixture
def b(c, setup):
    accounts, cats = setup
    g = c.categories.get_by_code
    ids = {k: g(k).id for k in ("EXP.PERSONAL", "EXP.PERSONAL.FOOD", "EXP.PERSONAL.TRANSPORT",
                                 "EXP.WORK", "EXP.WORK.SOFTWARE", "INC.SALARY")}
    return c, accounts, ids


def line(view, code):
    return next(l for s in view.sections for l in s.lines if l.code == code)


def section(view, name):
    return next(s for s in view.sections if s.name == name)


def test_repeat_until_changed(b):
    c, _, ids = b
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-07", "6,000")
    assert line(c.budgets.month_view("2026-06"), "EXP.PERSONAL.FOOD").budget is None
    for m in ("2026-07", "2026-08", "2027-01"):
        assert line(c.budgets.month_view(m), "EXP.PERSONAL.FOOD").budget == Decimal("6000")
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "7000")
    assert line(c.budgets.month_view("2026-08"), "EXP.PERSONAL.FOOD").budget == Decimal("6000")
    assert line(c.budgets.month_view("2026-12"), "EXP.PERSONAL.FOOD").budget == Decimal("7000")
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-11", "")  # no budget from November
    assert line(c.budgets.month_view("2026-12"), "EXP.PERSONAL.FOOD").budget is None
    assert line(c.budgets.month_view("2026-10"), "EXP.PERSONAL.FOOD").budget == Decimal("7000")


def test_this_month_only(b):
    c, _, ids = b
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-07", "6000")
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "9000", only_this_month=True)
    sep = line(c.budgets.month_view("2026-09"), "EXP.PERSONAL.FOOD")
    assert sep.budget == Decimal("9000") and sep.one_off
    assert line(c.budgets.month_view("2026-10"), "EXP.PERSONAL.FOOD").budget == Decimal("6000")
    # setting it back to the repeating amount removes the override
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "6000", only_this_month=True)
    assert not line(c.budgets.month_view("2026-09"), "EXP.PERSONAL.FOOD").one_off
    # a one-off "no budget"
    c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "", only_this_month=True)
    assert line(c.budgets.month_view("2026-09"), "EXP.PERSONAL.FOOD").budget is None
    assert line(c.budgets.month_view("2026-10"), "EXP.PERSONAL.FOOD").budget == Decimal("6000")


def test_group_is_sum_of_categories_or_its_own_ceiling(b):
    c, _, ids = b
    c.budgets.save_month("2026-09", {ids["EXP.PERSONAL.FOOD"]: "6000", ids["EXP.PERSONAL.TRANSPORT"]: "2000"})
    view = c.budgets.month_view("2026-09")
    assert line(view, "EXP.PERSONAL").budget == Decimal("8000") and line(view, "EXP.PERSONAL").direct is None
    c.budgets.set_budget(ids["EXP.PERSONAL"], "2026-09", "20000")
    view = c.budgets.month_view("2026-09")
    assert line(view, "EXP.PERSONAL").budget == Decimal("20000")
    assert section(view, "Personal").budget == Decimal("20000")  # categories are inside, not added on top
    assert not view.warnings
    c.budgets.set_budget(ids["EXP.PERSONAL"], "2026-09", "5000")
    assert "more than its budget" in c.budgets.month_view("2026-09").warnings[0]


def test_actuals_roll_up_and_sections_are_separate(b):
    c, accounts, ids = b
    cib = accounts["cib"].id
    c.transactions.record_outflow("2026-09-05", cib, "1500", ids["EXP.PERSONAL.FOOD"])
    c.transactions.record_outflow("2026-09-06", cib, "300", ids["EXP.PERSONAL.TRANSPORT"])
    c.transactions.record_outflow("2026-09-07", cib, "899", ids["EXP.WORK.SOFTWARE"])
    c.transactions.record_outflow("2026-10-01", cib, "999", ids["EXP.PERSONAL.FOOD"])  # other month
    c.transactions.record_transfer("2026-09-08", cib, accounts["wallet"].id, "5000")  # never counts
    c.transactions.record_inflow("2026-09-25", cib, "42000", ids["INC.SALARY"])
    c.budgets.save_month("2026-09", {ids["EXP.PERSONAL.FOOD"]: "1000", ids["EXP.WORK"]: "1500"})
    view = c.budgets.month_view("2026-09")
    food = line(view, "EXP.PERSONAL.FOOD")
    assert food.actual == Decimal("1500") and food.remaining == Decimal("-500") and food.over
    assert line(view, "EXP.PERSONAL").actual == Decimal("1800")
    personal, work = section(view, "Personal"), section(view, "Work")
    assert (personal.budget, personal.actual) == (Decimal("1000"), Decimal("1800"))
    assert personal.unbudgeted == Decimal("300")  # transport has no budget on it or above it
    assert (work.budget, work.actual, work.unbudgeted) == (Decimal("1500"), Decimal("899"), Decimal("0"))
    assert line(view, "EXP.WORK.SOFTWARE").covered  # inside the Work budget
    assert view.income == Decimal("42000")
    assert (view.budget, view.actual) == (Decimal("2500"), Decimal("2699"))


def test_rules(b):
    c, _, ids = b
    with pytest.raises(ValidationError, match="money out"):
        c.budgets.set_budget(ids["INC.SALARY"], "2026-09", "10")
    with pytest.raises(ValidationError, match="negative"):
        c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "-1")
    with pytest.raises(ValidationError):
        c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "1.234")
    with pytest.raises(ValidationError):
        c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-13", "1")
    assert c.budgets.set_budget(ids["EXP.PERSONAL.FOOD"], "2026-09", "") is False  # nothing to clear


def test_budget_page(c, b):
    c, accounts, ids = b
    client = TestClient(create_app(c))
    page = client.get("/budget?month=2026-09")
    assert page.status_code == 200 and "Personal" in page.text and "Work" in page.text
    r = client.post("/budget?month=2026-09", data={f"b_{ids['EXP.PERSONAL.FOOD']}": "6,000",
                                                   f"b_{ids['EXP.WORK']}": "1500"})
    assert "Saved 2 budgets from 2026-09 onward" in r.text and 'value="6,000.00"' in r.text
    r = client.post("/budget?month=2026-09", data={f"b_{ids['EXP.PERSONAL.FOOD']}": "6,000.00"})
    assert "Nothing changed" in r.text
    r = client.post("/budget?month=2026-09", data={f"b_{ids['EXP.PERSONAL.FOOD']}": "abc"})
    assert r.status_code == 400 and "not a valid number" in r.text
    assert "Budget · 2026-09" in client.get("/?month=2026-09").text
