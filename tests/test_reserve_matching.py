def test_matching_expense_waits_for_confirmation_and_completion_frees_cash(c):
    account = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "1000")
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD")
    reserve = c.reserves.create("Groceries", "100", "PROJECT", "2026-10-01",
                                account_id=account.id)
    c.reserves.allocate(reserve["id"], "100")
    expense = c.transactions.record_outflow("2026-09-10", account.id, "100", food.id)

    assert c.reserves.auto_link_transaction(expense.id) == 0
    assert c.reserves.links_for_transaction(expense.id) == []
    assert [row["id"] for row in c.reserves.suggested_reserves(expense.id)] == [reserve["id"]]

    c.reserves.set_expense_link(reserve["id"], expense.id, "100")
    c.reserves.complete(reserve["id"])
    assert c.reserves.get(reserve["id"])["status"] == "COMPLETE"
    assert c.reserves.cash_summary(c.reporting.owned_liquid_cash("2026-09-10"))["allocated"] == 0


def test_the_reserves_page_lists_a_goal_with_a_linked_payment(c):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    account = c.account_flows.open_account("CIB", "BANK", "2026-09-01", "10000")
    reserve = c.reserves.create("Car insurance", "9000")
    c.reserves.allocate(reserve["id"], "9000")
    paid = c.transactions.record_outflow("2026-09-10", account.id, "6000",
                                         c.categories.get_by_code("EXP.PERSONAL.TRANSPORT").id)
    c.reserves.set_expense_link(reserve["id"], paid.id, "6000")
    page = TestClient(create_app(c), base_url="http://127.0.0.1").get("/plan/reserves")
    assert page.status_code == 200
    assert "Car insurance" in page.text and "6,000" in page.text
