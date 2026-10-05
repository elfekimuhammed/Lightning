"""Numbers the 2026-10-05 routine audit found wrong, each reproduced before its fix.

The audit is quoted in each test's docstring by its number (#1 is the worst).
"""
from __future__ import annotations

from decimal import Decimal

from lightning.core.ledger import Effect, PostingLine
from lightning.core.refs import DocType

D = Decimal


def _shared_broker(c):
    """A brokerage holding one share in which you own some units and Dad owns the rest."""
    broker = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "0")
    dad = c.counterparties.create("Dad")
    income = c.categories.get_by_code("EXP.WORK.SALARY")
    cash = c.assets.cash_asset("EGP")
    c.transactions.post(DocType.IN, "2026-09-10", [
        PostingLine.cash(broker.id, cash.id, D("5000"), Effect.INFLOW, income.id, memo="Dad cash", owner_id=dad)])
    c.transactions.record_inflow("2026-09-10", broker.id, "5000", income.id, description="My cash")
    share = c.assets.create_investment("Shared share", "STOCK", "SHARED")
    return broker, dad, share


def test_1_your_share_of_a_shared_holding_is_yours_not_dads(c):
    """#1: you own 7 units and Dad owns 3, at price 200. Your holding is 1,400, not Dad's 600."""
    broker, dad, share = _shared_broker(c)
    c.investments.buy("2026-09-11", broker.id, share.id, "7", "100")
    c.investments.buy("2026-09-11", broker.id, share.id, "3", "100", owner_id=dad)
    c.assets.set_price(share.id, "2026-09-12", "200")

    holdings, _ = c.position.owned_holdings("2026-09-12")
    mine = next(h for h in holdings if h.asset_id == share.id)
    assert mine.quantity == 7
    assert mine.value == D("1400")


def test_2_your_cost_comes_from_your_own_purchases(c):
    """#2: you buy 10 @ 100 and Dad buys 10 @ 200, price 150. Your cost is 1,000, so your gain is +500."""
    broker, dad, share = _shared_broker(c)
    c.investments.buy("2026-09-11", broker.id, share.id, "10", "100")
    c.investments.buy("2026-09-11", broker.id, share.id, "10", "200", owner_id=dad)
    c.assets.set_price(share.id, "2026-09-12", "150")

    position = next(p for p in c.investments.portfolio("2026-09-12").positions if p.asset_id == share.id)
    assert position.quantity == 20 and position.cost_basis == D("3000")
    assert position.owned_quantity == 10
    assert position.owned_cost_basis == D("1000")


def test_3_old_unmarked_paydays_are_not_this_months_income(c, setup, monkeypatch):
    """#3: a 20,000 salary since June with nothing marked received: October income is 20,000, not 100,000."""
    from datetime import date
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-28")
    c.planning.create(kind="INCOME", name="Salary", amount="20000", frequency="MONTHLY", start_date="2026-06-25")
    october = c.forecaster.forecast(date(2026, 10, 28), months=2).months[0]
    assert october.income == D("20000")


def test_7_the_forecast_budget_is_the_budget_screens_left_in_plan(c, setup, monkeypatch):
    """#7: background estimates count in Left in plan, so the forecast's budget spending matches the Budget screen."""
    from datetime import date
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-01")
    accounts, cats = setup
    cib, food = accounts["cib"].id, cats["EXP.PERSONAL.FOOD"]
    transport = c.categories.get_by_code("EXP.PERSONAL.TRANSPORT")
    c.budgets.set_budget(food.id, "2026-10", "8000")
    for month in ("2026-07", "2026-08", "2026-09"):  # untracked transport: a background estimate of 3,000
        c.transactions.record_outflow(f"{month}-15", cib, "3000", transport.id)
    summary = c.budgets.plan_summary("2026-10")
    assert summary["left"] == D("11000")
    october = c.forecaster.forecast(date(2026, 10, 1), months=2).months[0]
    assert october.budget_spending == summary["left"]


def test_8_a_funded_goal_that_was_partly_spent_is_not_saved_for_again(c, setup, monkeypatch):
    """#8: a goal funded in full and partly spent reads 100% funded; the forecast must not save for it again."""
    from datetime import date
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-01")
    accounts, cats = setup
    goal = c.reserves.create("Sahel trip", "4000", due_date="2026-12-31")["id"]
    c.reserves.allocate(goal, "4000")
    spent = c.transactions.record_outflow("2026-10-01", accounts["cib"].id, "1500", cats["EXP.PERSONAL.FOOD"].id)
    c.reserves.set_expense_link(goal, spent.id, "1500")
    october = c.forecaster.forecast(date(2026, 10, 1), months=2).months[0]
    assert october.goal_saving == 0


def test_4_a_partial_loan_payment_leaves_the_rest_still_to_pay(c, setup, monkeypatch):
    """#4: a 4 × 2,500 loan with 1,000 paid on the first instalment still owes 9,000, not 7,500."""
    from datetime import date
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    accounts, _ = setup
    loans = c.categories.get_by_code("EXP.PERSONAL.FOOD")  # any spending category for the payment
    item = c.planning.create(kind="LOAN", name="Phone", amount="2500", frequency="MONTHLY",
                             start_date="2026-10-05", payment_count="4", category_id=str(loans.id))
    c.planning.record_payment(item, "2026-10-05", "2026-10-05", "1000", accounts["cib"].id)
    day = date(2026, 10, 6)
    assert c.planning.what_you_owe(day).loans_still_to_pay == D("9000")
    progress = c.planning.loan_progress(c.planning.get(item), day)
    assert progress["still_to_pay"] == D("9000") and progress["paid_amount"] == D("1000")
    assert progress["paid_amount"] + progress["still_to_pay"] == progress["total_amount"]


def test_9_a_skipped_payment_stays_owed_on_a_loan_with_an_end_date(c, setup, monkeypatch):
    """#9: a loan of 2,500 a month to 2027-01-05 (4 payments) with one skipped still owes 10,000."""
    from datetime import date
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    item = c.planning.create(kind="LOAN", name="Car", amount="2500", frequency="MONTHLY",
                             start_date="2026-10-05", end_date="2027-01-05")
    day = date(2026, 10, 6)
    assert c.planning.what_you_owe(day).loans_still_to_pay == D("10000")
    c.planning.skip(item, "2026-10-05")
    assert c.planning.what_you_owe(day).loans_still_to_pay == D("10000")
    assert c.planning.loan_progress(c.planning.get(item), day)["last_date"] == "2027-02-05"


def test_10_already_paid_keeps_the_number_of_payments(c, setup, monkeypatch):
    """#10: a 6-payment plan whose first two dates were already paid keeps 6 payments in all, not 8."""
    from datetime import date
    from lightning.planning.schedule import payment_dates
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-06")
    item = c.planning.create(kind="BILL", name="Course", amount="1000", frequency="MONTHLY",
                             start_date="2026-08-20", payment_count="6")
    assert c.planning.start_after_paid(item, date(2026, 10, 6)) == "2026-10-20"
    remaining = payment_dates(c.planning.get(item), "2099-12-31")
    assert [d for _, d in remaining] == ["2026-10-20", "2026-11-20", "2026-12-20", "2027-01-20"]
