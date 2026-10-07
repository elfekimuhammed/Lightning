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


def test_one_payment_does_not_repeat_its_amount_in_four_kpis(c, setup):
    accounts, categories = setup
    c.transactions.record_outflow("2026-11-05", accounts["cib"].id, "100", categories["EXP.PERSONAL.FOOD"].id)
    page = TestClient(create_app(c)).get(
        "/birdview/expenses?period=custom&date_from=2026-11-01&date_to=2026-11-30"
    )
    assert page.status_code == 200
    assert page.text.count('class="stat-tile surface-') == 1


def test_close_plan_payments_use_separate_timeline_label_rows(c, monkeypatch):
    from datetime import date
    from lightning.ui import visuals

    day = date(2026, 10, 1)
    monkeypatch.setenv("LIGHTNING_TODAY", day.isoformat())
    for name, due in (("Rent", "2026-10-02"), ("Phone", "2026-10-04"),
                      ("Gym", "2026-10-06"), ("Internet", "2026-10-12")):
        c.planning.create(kind="BILL", name=name, amount="100", frequency="ONCE", start_date=due)
    marks = visuals.cash_plan(c, c.forecaster.forecast(day), day)["marks"]
    assert [mark["row"] for mark in marks[:3]] == [0, 1, 2]
    same_row = [mark["x"] for mark in marks if mark["row"] == 0]
    assert all(right - left >= 22 for left, right in zip(same_row, same_row[1:]))
