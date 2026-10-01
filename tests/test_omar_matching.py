from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from lightning.planning.domain import PaymentStatus
from lightning.ui.web import create_app


def _planned_income(c, accounts, category, amount="30000", start="2026-11-01"):
    party = c.counterparties.create("Omar employer")
    item_id = c.planning.create(
        kind="INCOME", name="Salary", amount=amount, frequency="MONTHLY", start_date=start,
        account_id=str(accounts["cib"].id), category_id=str(category.id), counterparty_id=party)
    return item_id, party


def test_early_salary_is_suggested_but_only_linked_after_confirmation(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-25")
    accounts, cats = setup
    item_id, _ = _planned_income(c, accounts, cats["EXP.WORK.SALARY"])
    txn = c.transactions.record_inflow("2026-10-08", accounts["cib"].id, "30000",
                                       cats["EXP.WORK.SALARY"].id, counterparty="Omar employer")
    day = date(2026, 10, 25)
    payment = c.planning.payments(c.planning.get(item_id), "2026-11-01", day)[0]

    assert c.planning.match_payments(day) == 0
    assert [row["id"] for row in c.planning.plausible_candidates(payment, day)] == [txn.id]
    assert payment.status == PaymentStatus.UPCOMING

    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    page = client.get(f"/plan/items/{item_id}/pay?due=2026-11-01").text
    assert "Possible matches" in page and "Link this payment" in page
    linked = client.post(f"/plan/items/{item_id}/pay", data={
        "due": "2026-11-01", "outcome": "link", "transaction_id": str(txn.id), "back": "/plan/recurring"},
        follow_redirects=False)
    assert linked.status_code == 303
    settled = c.planning.payments(c.planning.get(item_id), "2026-11-01", day)[0]
    assert settled.status == PaymentStatus.PAID and settled.paid_amount == Decimal("30000")


def test_salary_raise_is_suggested_and_actual_amount_is_saved_on_confirmation(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-07")
    accounts, cats = setup
    item_id, _ = _planned_income(c, accounts, cats["EXP.WORK.SALARY"], start="2026-10-01")
    txn = c.transactions.record_inflow("2026-10-01", accounts["cib"].id, "42000",
                                       cats["EXP.WORK.SALARY"].id, counterparty="Omar employer")
    day = date(2026, 10, 7)
    payment = c.planning.payments(c.planning.get(item_id), "2026-10-01", day)[0]

    assert c.planning.match_payments(day) == 0
    assert [row["id"] for row in c.planning.plausible_candidates(payment, day)] == [txn.id]
    assert payment.status == PaymentStatus.DUE

    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    response = client.post(f"/plan/items/{item_id}/pay", data={
        "due": "2026-10-01", "outcome": "link", "transaction_id": str(txn.id), "back": "/plan/recurring"},
        follow_redirects=False)
    assert response.status_code == 303
    settled = c.planning.payments(c.planning.get(item_id), "2026-10-01", day)[0]
    assert settled.status == PaymentStatus.PAID and settled.paid_amount == Decimal("42000")
    assert c.planning.get(item_id).amount == Decimal("30000")


def test_ambiguous_strict_matches_remain_unlinked_and_visible_for_choice(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-07")
    accounts, cats = setup
    item_id = c.planning.create(kind="BILL", name="Groceries", amount="400", frequency="MONTHLY",
                                start_date="2026-10-01", account_id=str(accounts["cib"].id),
                                category_id=str(cats["EXP.PERSONAL.FOOD"].id))
    first = c.transactions.record_outflow("2026-09-30", accounts["cib"].id, "400",
                                          cats["EXP.PERSONAL.FOOD"].id, counterparty="Grocer")
    second = c.transactions.record_outflow("2026-10-02", accounts["cib"].id, "400",
                                           cats["EXP.PERSONAL.FOOD"].id, counterparty="Market")
    day = date(2026, 10, 7)
    payment = c.planning.payments(c.planning.get(item_id), "2026-10-01", day)[0]

    assert c.planning.match_payments(day) == 0
    assert payment.status == PaymentStatus.DUE
    assert {row["id"] for row in c.planning.candidates(payment, day)} == {first.id, second.id}
    page = TestClient(create_app(c), base_url="http://127.0.0.1").get(
        f"/plan/items/{item_id}/pay?due=2026-10-01").text
    assert page.count("Use this") == 2


def test_changed_rent_amount_alerts_to_update_plan_and_review_exactly_linked_reserve(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-01")
    accounts, _ = setup
    housing = c.categories.get_by_code("EXP.PERSONAL.HOUSING")
    item_id = c.planning.create(kind="BILL", name="Rent", amount="20000", frequency="MONTHLY",
                                start_date="2026-10-01", account_id=str(accounts["cib"].id),
                                category_id=str(housing.id))
    txn = c.transactions.record_outflow("2026-10-01", accounts["cib"].id, "24000", housing.id,
                                        counterparty="Landlord")
    reserve = c.reserves.create("Rent reserve", "24000", category_id=housing.id)
    c.reserves.allocate(reserve["id"], "24000")
    c.reserves.set_expense_link(reserve["id"], txn.id, "24000")

    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    linked = client.post(f"/plan/items/{item_id}/pay", data={
        "due": "2026-10-01", "outcome": "link", "transaction_id": str(txn.id), "back": "/plan/recurring"},
        follow_redirects=False)
    assert linked.status_code == 303
    recurring = client.get("/plan/recurring").text

    assert "Review Rent amount" in recurring
    assert "was 24,000" in recurring and "planned at 20,000" in recurring
    assert f"/plan/items/{item_id}/amount" in recurring
    assert "Review reserve target for Rent reserve" in recurring
    assert c.reserves.get(reserve["id"])["target"] == Decimal("24000")
    payment = c.planning.payments(c.planning.get(item_id), "2026-10-01", date(2026, 10, 1))[0]
    assert payment.paid_amount == Decimal("24000")


def test_recurring_page_offers_early_salary_review_before_due_date(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-12-31")
    accounts, cats = setup
    item_id, _ = _planned_income(c, accounts, cats["EXP.WORK.SALARY"], start="2027-01-01")
    first = c.transactions.record_inflow("2026-12-24", accounts["cib"].id, "30000",
                                         cats["EXP.WORK.SALARY"].id, counterparty="Omar employer")
    second = c.transactions.record_inflow("2026-12-23", accounts["cib"].id, "36000",
                                          cats["EXP.WORK.SALARY"].id, counterparty="Omar employer")
    day = date(2026, 12, 31)
    assert c.planning.match_payments(day) == 0

    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    recurring = client.get("/plan/recurring").text
    assert "Next 2027-01-01" in recurring
    assert "Possible early/changed payment — review" in recurring
    assert f'/plan/items/{item_id}/pay?due=2027-01-01&amp;back=%2Fplan%2Frecurring' in recurring

    pay_page = client.get(f"/plan/items/{item_id}/pay?due=2027-01-01").text
    assert pay_page.count("Link this payment") == 2
    assert {row["id"] for row in c.planning.plausible_candidates(
        c.planning.payments(c.planning.get(item_id), "2027-01-01", day)[0], day)} == {first.id, second.id}
    assert c.planning.payments(c.planning.get(item_id), "2027-01-01", day)[0].status == PaymentStatus.UPCOMING
