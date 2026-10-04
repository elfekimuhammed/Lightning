"""Planned and Spent cover the same months (owner screenshot 2026-10-03: Food 505 planned against
50,732 spent, because months before the first plan counted their spending but nothing planned)."""
import re
from decimal import Decimal

from fastapi.testclient import TestClient

from lightning.ui.web import create_app


def test_a_long_period_counts_spending_only_from_the_first_planned_month(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-03-31")
    accounts, cats = setup
    food = cats["EXP.PERSONAL.FOOD"]
    for month in ("01", "02", "03"):
        c.transactions.record_outflow(f"2026-{month}-10", accounts["cib"].id, "1000", food.id)
    c.budgets.set_budget(food.id, "2026-03", "1200")      # the plan starts in March
    page = TestClient(create_app(c)).get("/budget?period=ytd&month=2026-03").text
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    assert "Planned and spent from 2026-03-01, the first month with a plan." in text
    spent = re.search(r"Spent ([\d,]+) ", text).group(1)
    assert Decimal(spent.replace(",", "")) == Decimal("1000")   # March only, not 3,000
