from decimal import Decimal

from fastapi.testclient import TestClient

from lightning.ui.charts import line_chart
from lightning.ui.web import create_app


def test_line_chart_keeps_missing_observations_as_gaps():
    chart = line_chart([Decimal("10"), Decimal("20"), None, Decimal("15"), Decimal("30")])
    assert len(chart["segments"]) == 2
    assert len(chart["dots"]) == 4
    assert line_chart([None, Decimal("12")])["segments"] == []


def test_expense_category_filter_applies_to_total_and_monthly_trend(c, setup):
    accounts, categories = setup
    account = accounts["cib"]
    food = categories["EXP.PERSONAL.FOOD"]
    work = categories["EXP.WORK.SOFTWARE"]
    c.transactions.record_outflow("2026-10-05", account.id, "100", food.id)
    c.transactions.record_outflow("2026-11-05", account.id, "150", food.id)
    c.transactions.record_outflow("2026-11-06", account.id, "500", work.id)

    page = TestClient(create_app(c)).get(
        f"/birdview/expenses?period=custom&date_from=2026-10-01&date_to=2026-11-30&category_id={food.id}"
    )
    assert page.status_code == 200
    assert "250" in page.text
    assert "2026-10" in page.text and "2026-11" in page.text
    assert "150" in page.text and "100" in page.text
    assert "650" not in page.text  # November's unfiltered total
