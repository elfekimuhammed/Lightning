from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lightning.core.errors import ValidationError
from lightning.planning.domain import Frequency, PaymentStatus, PlanKind, PlannedItem
from lightning.planning.schedule import describe, payment_dates
from lightning.ui.web import create_app


def _item(**kw) -> PlannedItem:
    base = dict(id=1, kind=PlanKind.BILL, name="Bill", amount=Decimal("100"), frequency=Frequency.MONTHLY,
                interval_count=1, start_date="2026-01-31", end_date=None, payment_count=None, account_id=None,
                category_id=None, counterparty_id=None, principal=None, active=True, notes="")
    return PlannedItem(**(base | kw))


# ---------------------------------------------------------------- schedule
def test_month_end_dates_clamp_to_the_last_day():
    dates = [d for _, d in payment_dates(_item(), "2026-04-30")]
    assert dates == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"]


def test_payment_count_ends_a_loan_and_weekly_and_once_work():
    loan = _item(kind=PlanKind.LOAN, start_date="2026-10-05", payment_count=3)
    assert [d for _, d in payment_dates(loan, "2030-01-01")] == ["2026-10-05", "2026-11-05", "2026-12-05"]
    weekly = _item(frequency=Frequency.WEEKLY, interval_count=2, start_date="2026-09-01")
    assert [d for _, d in payment_dates(weekly, "2026-09-30")] == ["2026-09-01", "2026-09-15", "2026-09-29"]
    once = _item(frequency=Frequency.ONCE, start_date="2026-09-10")
    assert payment_dates(once, "2027-01-01") == [(1, "2026-09-10")]
    assert describe(loan) == "Monthly on day 5 · 3 payments"


# ------------------------------------------------------------ what you owe
def test_only_due_bills_and_loans_count_as_owed(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, cats = setup
    c.planning.create(kind="BILL", name="Internet", amount="650", frequency="MONTHLY", start_date="2026-09-20",
                      account_id=str(accounts["cib"].id))
    c.planning.create(kind="SUBSCRIPTION", name="Streaming", amount="120", frequency="MONTHLY",
                      start_date="2026-10-05")
    c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY", start_date="2026-09-05",
                      payment_count="4")
    owe = c.planning.what_you_owe(date(2026, 9, 30))
    # Internet (09-20) and the first loan payment (09-05) are due; streaming is upcoming.
    assert owe.bills_due == Decimal("3150")
    assert owe.loans_still_to_pay == Decimal("10000")
    assert owe.other_bills_due == Decimal("650")
    assert owe.total == Decimal("10650")  # the due loan payment is counted once


def test_loan_needs_payments_left_or_a_last_date(c):
    with pytest.raises(ValidationError):
        c.planning.create(kind="LOAN", name="Phone", amount="900", frequency="MONTHLY", start_date="2026-10-01")


# ---------------------------------------------------------------- matching
def test_a_posted_payment_settles_the_bill_and_voiding_it_reopens(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, cats = setup
    food = cats["EXP.PERSONAL.FOOD"]
    item_id = c.planning.create(kind="BILL", name="Groceries box", amount="400", frequency="MONTHLY",
                                start_date="2026-09-12", account_id=str(accounts["cib"].id),
                                category_id=str(food.id))
    txn = c.transactions.record_outflow("2026-09-13", accounts["cib"].id, "395", food.id, counterparty="Box")
    assert c.planning.match_payments(date(2026, 9, 30)) == 1
    payment = c.planning.payments(c.planning.get(item_id), "2026-09-30", date(2026, 9, 30))[0]
    assert payment.status == PaymentStatus.PAID and payment.transaction_id == txn.id
    assert c.planning.what_you_owe(date(2026, 9, 30)).bills_due == 0
    c.transactions.void(txn.id)
    payment = c.planning.payments(c.planning.get(item_id), "2026-09-30", date(2026, 9, 30))[0]
    assert payment.status == PaymentStatus.DUE


def test_two_candidates_are_left_for_the_user(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, cats = setup
    food = cats["EXP.PERSONAL.FOOD"]
    c.planning.create(kind="BILL", name="Box", amount="400", frequency="MONTHLY", start_date="2026-09-12",
                      category_id=str(food.id))
    c.transactions.record_outflow("2026-09-11", accounts["cib"].id, "400", food.id)
    c.transactions.record_outflow("2026-09-14", accounts["wallet"].id, "400", food.id)
    assert c.planning.match_payments(date(2026, 9, 30)) == 0


# ---------------------------------------------------------------- forecast
def test_forecast_counts_a_budgeted_bill_once_and_estimates_income(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-15")
    accounts, cats = setup
    salary, food = cats["EXP.WORK.SALARY"], cats["EXP.PERSONAL.FOOD"]
    c.transactions.record_inflow("2026-09-01", accounts["cib"].id, "30000", salary.id)
    c.budgets.set_budget(food.id, "2026-10", "5000")
    c.budgets.set_budget(food.id, "2026-11", "5000")
    c.planning.create(kind="BILL", name="Groceries box", amount="1200", frequency="MONTHLY", start_date="2026-11-10",
                      category_id=str(food.id))
    forecast = c.forecaster.forecast(date(2026, 10, 15), months=2)
    november = forecast.months[1]
    assert november.commitments == Decimal("1200")
    assert november.budget_spending == Decimal("3800")  # 5,000 plan less the 1,200 bill inside it
    assert november.income == Decimal("30000.00") and november.income_estimated
    assert forecast.average_income == Decimal("30000.00") and forecast.average_income_months == 1


# -------------------------------------------------------------------- screens
def test_screens_show_bills_due_and_net_worth(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, cats = setup
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    created = client.post("/plan/items", data={
        "kind": "BILL", "name": "Electricity", "amount": "480", "frequency": "MONTHLY", "interval_count": "1",
        "start_date": "2026-09-25", "account_id": str(accounts["cib"].id),
        "category_id": str(cats["EXP.PERSONAL.FOOD"].id), "counterparty": "Electricity Co", "past_due": "due"})
    assert created.status_code == 200 and "Electricity added." in created.text
    client.post("/plan/items", data={"kind": "LOAN", "name": "Car loan", "amount": "2500", "frequency": "MONTHLY",
                                     "interval_count": "1", "start_date": "2026-10-05", "payment_count": "2"})
    overview = client.get("/").text
    assert "Net worth" in overview and "What you owe" in overview and "Bills due" in overview
    assert "−5,480.00" in overview  # 480 due + 5,000 of loan payments still to pay
    checks = client.get("/checks").text
    assert "Free cash plus reserves and bills due equals owned liquid cash" in checks
    assert client.get("/reserves", follow_redirects=False).headers["location"] == "/plan/reserves"
    for page in ("/plan", "/plan/recurring", "/plan/loans", "/plan/reserves"):
        assert client.get(page).status_code == 200
    item = next(i for i in c.planning.items() if i.name == "Electricity")
    paid = client.post(f"/plan/items/{item.id}/pay", data={
        "due": "2026-09-25", "back": "/plan", "outcome": "record", "date_paid": "2026-09-26", "amount": "480",
        "account_id": str(accounts["cib"].id)}, follow_redirects=False)
    assert paid.status_code == 303 and "marked%20paid" in paid.headers["location"]
    assert c.planning.what_you_owe(date(2026, 9, 30)).bills_due == 0


def test_loan_payments_count_as_spending_and_leave_net_worth_unchanged(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-31")
    accounts, cats = setup
    loans_category = c.categories.get_by_code("EXP.PERSONAL.LOANS")
    assert loans_category.name == "Loan payments"
    item_id = c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY",
                                start_date="2026-10-05", payment_count="24", account_id=str(accounts["cib"].id))
    assert c.planning.get(item_id).category_id == loans_category.id  # default when none is chosen
    day = date(2026, 10, 31)
    before_owe = c.planning.what_you_owe(day).total
    before_net = c.reporting.net_worth(day).total - before_owe
    before_spent = c.reporting.cash_flow(date(2026, 10, 1), day).outflows
    c.planning.record_payment(item_id, "2026-10-05", "2026-10-05", "2500", None)
    after_owe = c.planning.what_you_owe(day).total
    assert c.reporting.cash_flow(date(2026, 10, 1), day).outflows - before_spent == Decimal("2500")
    assert before_owe - after_owe == Decimal("2500")
    assert c.reporting.net_worth(day).total - after_owe == before_net


def test_overview_lists_due_bills_under_needs_you(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, _ = setup
    c.planning.create(kind="BILL", name="Electricity", amount="480", frequency="MONTHLY", start_date="2026-09-25")
    c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY", start_date="2026-09-05",
                      payment_count="3")
    page = TestClient(create_app(c), base_url="http://127.0.0.1").get("/").text
    attention = page[page.index('id="attention-heading">Needs you'):]
    assert "Bill due: Electricity" in attention and "Due 2026-09-25 · 480.00" in attention
    assert "Loan payment due: Car loan" in attention and "Mark paid" in attention
    start = page.index('aria-label="Key notes"')
    notes = page[start:page.index("</section>", start)]
    assert "and 1 more" in notes  # the first key note leads with what needs you


def test_a_due_bill_inside_a_budget_is_not_counted_twice(c, setup, monkeypatch):
    # Rent is due and unpaid: it comes off free cash as a bill due, so it must not also be
    # budget still to spend (Omar, 2026-10-06: Safe to spend was 12,000 too low).
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, cats = setup
    housing = c.categories.get_by_code("EXP.PERSONAL.HOUSING")
    c.budgets.set_budget(housing.id, "2026-10", "12000")
    c.planning.create(kind="BILL", name="Rent", amount="12000", frequency="MONTHLY", start_date="2026-10-03",
                      category_id=str(housing.id))
    day = date(2026, 10, 6)
    october = c.forecaster.forecast(day).months[0]
    assert c.planning.what_you_owe(day).bills_due == Decimal("12000")
    assert october.budget_spending == 0
    parts = dict(c.forecaster.forecast(day).safe_to_spend_parts)
    assert "Left in plan after bills" not in parts  # nothing left once the due rent is counted


def test_manual_link_suggests_only_plausible_transactions(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, cats = setup
    item_id = c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY",
                                start_date="2026-10-05", payment_count="24")
    c.transactions.record_outflow("2026-09-25", accounts["cib"].id, "2000", cats["EXP.PERSONAL.FOOD"].id,
                                  counterparty="Mom")
    c.transactions.record_outflow("2026-10-04", accounts["cib"].id, "2480", cats["EXP.PERSONAL.FOOD"].id,
                                  counterparty="Toyota")
    payment = c.planning.payments(c.planning.get(item_id), "2026-10-05", date(2026, 10, 6))[0]
    amounts = [r["amount"] for r in c.planning.candidates(payment, date(2026, 10, 6), loose=True)]
    assert amounts == [Decimal("2480")]  # the 2,000 gift to Mom is not offered


def test_a_loan_adds_its_payments_as_a_budget_line(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, _ = setup
    loans = c.categories.get_by_code("EXP.PERSONAL.LOANS")
    assert not c.budgets.has_plan("2026-10")
    c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY", start_date="2026-10-05",
                      payment_count="2", account_id=str(accounts["cib"].id))
    assert not c.budgets.has_plan("2026-10")  # a loan alone does not count as having made a plan

    def line(month):
        view = c.budgets.month_view(month)
        return next(l for s in view.sections for l in s.lines if l.category_id == loans.id)
    october = line("2026-10")
    assert october.budget == Decimal("2500") and october.from_loans
    assert line("2026-11").budget == Decimal("2500")
    assert not any(l.category_id == loans.id and l.budget for s in c.budgets.month_view("2026-12").sections
                   for l in s.lines)  # the loan has ended: no plan line
    page = TestClient(create_app(c), base_url="http://127.0.0.1").get("/budget?month=2026-10").text
    assert "Loan payments scheduled this month" in page
    c.budgets.set_budget(loans.id, "2026-10", "3000")  # a rule you set replaces the scheduled amount
    assert line("2026-10").budget == Decimal("3000") and not line("2026-10").from_loans


def test_skipping_a_loan_payment_moves_it_to_the_end(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    item_id = c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY",
                                start_date="2026-10-05", payment_count="24")
    day = date(2026, 10, 6)
    assert c.planning.what_you_owe(day).loans_still_to_pay == Decimal("60000")
    c.planning.skip(item_id, "2026-10-05")
    progress = c.planning.loan_progress(c.planning.get(item_id), day)
    assert c.planning.what_you_owe(day).loans_still_to_pay == Decimal("60000")  # still owed
    assert progress["total"] == 24 and progress["last_date"] == "2028-10-05" and len(progress["skipped"]) == 1
    c.planning.reopen(item_id, "2026-10-05")
    assert c.planning.loan_progress(c.planning.get(item_id), day)["last_date"] == "2028-09-05"


def test_lazy_input_and_next_month(c, setup, monkeypatch):
    from lightning.core.dates import parse_date
    from lightning.core.money import to_decimal
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    assert to_decimal("١٢٬٥٠٠٫٥") == Decimal("12500.5") and to_decimal("۶۰۰") == Decimal("600")
    assert parse_date("٥/١٠") == date(2026, 10, 5)
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    ahead = client.get("/budget?month=2026-11", follow_redirects=False)
    assert ahead.status_code == 303 and "has%20not%20started" in ahead.headers["location"]
    item_id = c.planning.create(kind="BILL", name="Gym", amount="600", frequency="MONTHLY", start_date="2026-10-05")
    form = client.get(f"/plan/items/{item_id}/edit").text
    assert ">Delete<" in form and "cannot be undone" in form
    c.planning.skip(item_id, "2026-10-05")
    form = client.get(f"/plan/items/{item_id}/edit").text
    assert ">Stop<" in form and "First due date" in form


def test_a_past_first_date_that_was_paid_starts_from_the_next_one(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    base = {"kind": "BILL", "amount": "600", "frequency": "MONTHLY", "interval_count": "1", "start_date": "2026-10-05"}
    added = client.post("/plan/items", data={**base, "name": "Gym"}, follow_redirects=False)
    assert "next%20one%20is%20due%202026-11-05" in added.headers["location"]
    gym = next(i for i in c.planning.items() if i.name == "Gym")
    assert gym.start_date == "2026-11-05" and c.planning.what_you_owe(date(2026, 10, 6)).bills_due == 0
    client.post("/plan/items", data={**base, "name": "Club", "past_due": "due"})
    assert c.planning.what_you_owe(date(2026, 10, 6)).bills_due == Decimal("600")  # still unpaid, so due


def test_paying_a_new_amount_offers_to_plan_it_from_now_on(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, _ = setup
    housing = c.categories.get_by_code("EXP.PERSONAL.HOUSING")
    item_id = c.planning.create(kind="BILL", name="Rent", amount="12000", frequency="MONTHLY", start_date="2026-10-03",
                                account_id=str(accounts["cib"].id), category_id=str(housing.id))
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    paid = client.post(f"/plan/items/{item_id}/pay", data={"due": "2026-10-03", "back": "/plan", "outcome": "record",
                       "date_paid": "2026-10-03", "amount": "12500", "account_id": str(accounts["cib"].id)},
                       follow_redirects=False)
    assert "12%2C500.00%20from%20now%20on" in paid.headers["location"]
    page = client.get("/plan/recurring").text
    assert "Use 12,500.00 from now on" in page
    client.post(f"/plan/items/{item_id}/amount", data={"amount": "12500", "back": "/plan/recurring"})
    assert c.planning.get(item_id).amount == Decimal("12500")


def test_tiny_repeats_are_not_suggested(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, cats = setup
    for month in ("07", "08", "09"):
        c.transactions.record_outflow(f"2026-{month}-28", accounts["cib"].id, "15", cats["EXP.PERSONAL.FOOD"].id,
                                      counterparty="Bank fee")
        c.transactions.record_outflow(f"2026-{month}-20", accounts["cib"].id, "650", cats["EXP.PERSONAL.FOOD"].id,
                                      counterparty="WE")
    names = [s["name"] for s in c.planning.suggestions(date(2026, 10, 6))]
    assert "WE" in names and "Bank fee" not in names
