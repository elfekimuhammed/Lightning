"""Omar's year: steps 11-28 of the reference workflow in docs/PROJECT_OVERVIEW.md.

The demo household (July-September 2026) is carried through October 2026 - September 2027, one
month at a time, with the events a salaried year brings. Each test checks one step. A step that is
wrong today is marked xfail(strict=True): when the gap is fixed the test passes, fails as
"XPASS", and the marker and the Overview's "Today" column must be updated together.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest

from lightning.bootstrap import build
from lightning.demo import build_demo

D = Decimal


def known_gap(reason: str):
    return pytest.mark.xfail(strict=True, reason=reason)


@pytest.fixture(scope="module")
def year(tmp_path_factory):
    pinned = os.environ.get("LIGHTNING_TODAY")
    os.environ["LIGHTNING_TODAY"] = "2026-09-30"
    c = build(tmp_path_factory.mktemp("omar") / "omar.db")
    try:
        yield _live_the_year(c)
    finally:
        c.db.close()
        os.environ["LIGHTNING_TODAY"] = pinned or ""


def _live_the_year(c) -> dict:
    """Run the year through the same services the screens use; return what each step needs."""
    build_demo(c)
    seen: dict = {}
    accounts = {a.name: a.id for a in c.accounts.list()}
    cib, wallet, vodafone, thndr = (accounts[name] for name in ("CIB Payroll", "Cash wallet", "Vodafone Cash", "THNDR"))
    tx = c.transactions

    def cat(code):
        return c.categories.get_by_code(code).id

    def item(name):
        return next(i for i in c.planning.items() if i.name == name)

    def payment(name, due):
        return next(p for p in c.planning.payments(item(name), due) if p.due_date == due)

    def on(day: str) -> date:
        os.environ["LIGHTNING_TODAY"] = day
        return date.fromisoformat(day)

    def month(m, salary="45,000", rent="12,000", employer="ACME Egypt"):
        """An ordinary month: pay in, rent, the car loan, groceries, phone, internet, electricity."""
        salary_txn = None
        if salary:
            salary_txn = tx.record_inflow(f"{m}-01", cib, salary, cat("EXP.WORK.SALARY"), counterparty=employer)
        tx.record_outflow(f"{m}-03", cib, rent, cat("EXP.PERSONAL.HOUSING"), counterparty="Landlord")
        tx.record_outflow(f"{m}-05", cib, "2,500", cat("EXP.SYSTEM.LOANS"), counterparty="Toyota Finance")
        tx.record_transfer(f"{m}-07", cib, vodafone, "1,000")
        tx.record_outflow(f"{m}-08", cib, "4,600", cat("EXP.PERSONAL.FOOD"), counterparty="Carrefour")
        tx.record_outflow(f"{m}-09", vodafone, "350", cat("EXP.PERSONAL.UTILITIES"), counterparty="Vodafone")
        if m >= "2027-04":
            tx.record_outflow(f"{m}-15", cib, "2,000", cat("EXP.SYSTEM.LOANS"), counterparty="valU")
        tx.record_outflow(f"{m}-20", cib, "650", cat("EXP.PERSONAL.UTILITIES"), counterparty="WE Internet")
        tx.record_outflow(f"{m}-24", cib, "480", cat("EXP.PERSONAL.UTILITIES"), counterparty="North Cairo Electricity")
        return salary_txn

    # 11 · October: an ordinary month settles itself.
    day = on("2026-10-31")
    month("2026-10")
    c.planning.match_payments(day)
    seen["october_due"] = [p for p in c.planning.all_payments(day, day) if p.status.name == "DUE"]

    # 12 · An ATM withdrawal with a fee.
    before = c.position.at(day).net_worth
    tx.record_transfer("2026-10-10", cib, wallet, "2,000")
    tx.record_outflow("2026-10-10", cib, "25", cat("EXP.PERSONAL.FEES"), counterparty="CIB")
    seen["atm_net_worth_change"] = c.position.at(day).net_worth - before

    # 13 · August's Amazon purchase is returned in October.
    tx.record_refund("2026-10-15", cib, "1,299", cat("EXP.PERSONAL.SHOPPING"), counterparty="Amazon")
    shopping = cat("EXP.PERSONAL.SHOPPING")
    seen["shopping_august"] = c.reporting.money_out_by_category("2026-08-01", "2026-08-31").get(shopping, D(0))
    seen["shopping_october"] = c.reporting.money_out_by_category("2026-10-01", "2026-10-31").get(shopping, D(0))

    # 14 · A car repair paid from the emergency fund.
    before = c.position.at(day)
    repair = tx.record_outflow("2026-10-18", cib, "6,500", cat("EXP.PERSONAL.TRANSPORT"), counterparty="Al Mansour Service")
    emergency = next(r for r in c.reserves.list_active() if r["kind"] == "EMERGENCY")
    c.reserves.set_expense_link(emergency["id"], repair.id, "6,500")
    after = c.position.at(day)
    seen["repair"] = (after.reserves, after.free_cash - before.free_cash, after.cash_you_own - before.cash_you_own)

    # 15 · November: a COMI dividend.
    day = on("2026-11-30")
    month("2026-11")
    comi = c.assets.get_asset_by_code("STK:COMI")
    c.investments.dividend("2026-11-20", thndr, comi.id, "300")
    c.planning.match_payments(day)
    seen["november_money_in"] = {r.code: r.value for r in c.reporting.money_in_by_category("2026-11-01", "2026-11-30")}

    # 16-18 · December: a reimbursed work expense, a 90,000 bonus, January's pay on the 24th.
    day = on("2026-12-31")
    month("2026-12")
    tx.record_outflow("2026-12-10", cib, "1,200", cat("EXP.WORK.TRANSPORT"), counterparty="Uber")
    tx.record_refund("2026-12-22", cib, "1,200", cat("EXP.WORK.TRANSPORT"), counterparty="ACME Egypt")
    tx.record_inflow("2026-12-20", cib, "90,000", cat("EXP.WORK.BONUS"), counterparty="ACME Egypt")
    early_salary = tx.record_inflow("2026-12-24", cib, "45,000", cat("EXP.WORK.SALARY"), counterparty="ACME Egypt")
    c.planning.match_payments(day)
    seen["december_work_spending"] = c.reporting.cash_flow("2026-12-01", "2026-12-31").work_outflows
    january_salary = payment("ACME Egypt", "2027-01-01")
    seen["january_salary_candidates"] = [row["id"] for row in c.planning.plausible_candidates(january_salary, day)]
    seen["january_salary_transaction"] = early_salary.id
    c.planning.mark_paid(january_salary.item.id, "2027-01-01", early_salary.id)
    seen["average_for_january"] = c.budgets.income_average("2027-01").amount

    # January: no salary arrives (it came early); he plans the car insurance.
    day = on("2027-01-31")
    month("2027-01", salary=None)
    c.planning.match_payments(day)
    seen["january_salary"] = payment("ACME Egypt", "2027-01-01").status.name
    seen["january_forecast_income"] = c.forecaster.forecast(day).months[0].income
    seen["average_for_february"] = c.budgets.income_average("2027-02").amount
    insurance = c.reserves.create("Car insurance", "9,000", due_date="2027-04-30")
    seen["insurance_saving"] = c.forecaster.forecast(day).months[0].goal_saving

    # 20 · February: the raise.
    day = on("2027-02-28")
    february_txn = month("2027-02", salary="50,000")
    february_salary = payment("ACME Egypt", "2027-02-01")
    seen["raise_candidates_before_confirmation"] = [
        row["id"] for row in c.planning.plausible_candidates(february_salary, day)
    ]
    seen["raise_transaction"] = february_txn.id
    seen["raise_status_before_confirmation"] = february_salary.status.name
    c.planning.mark_paid(february_salary.item.id, "2027-02-01", february_txn.id)
    c.planning.set_amount(item("ACME Egypt").id, "50,000")  # the popup's "plan later payments at this amount"
    c.planning.match_payments(day)
    seen["raise"] = (payment("ACME Egypt", "2027-02-01").status.name, payment("ACME Egypt", "2027-03-01").amount,
                     payment("ACME Egypt", "2026-12-01").paid_amount)

    # 21-22 · March: Eid gifts; a phone on 12 installments from 15 April.
    day = on("2027-03-31")
    month("2027-03", salary="50,000")
    c.planning.match_payments(day)
    tx.record_outflow("2027-03-09", wallet, "3,000", cat("EXP.PERSONAL.GIFTS"), counterparty="Eidiya")
    tx.record_inflow("2027-03-10", wallet, "1,000", cat("EXP.PERSONAL.GIFTS_RECEIVED"), counterparty="Uncle Hassan")
    owed = c.position.at(day).what_you_owe
    c.planning.create(kind="LOAN", name="Phone installments", amount="2,000", frequency="MONTHLY", interval_count="1",
                      start_date="2027-04-15", payment_count="12", principal="24,000", account_id=str(cib),
                      category_id=str(cat("EXP.SYSTEM.LOANS")), counterparty_id="")
    seen["phone_owed"] = c.position.at(day).what_you_owe - owed
    seen["average_for_april"] = c.budgets.income_average("2027-04").amount

    # 19, 23 · April: the insurance is paid from its goal; half the COMI shares are sold.
    day = on("2027-04-30")
    month("2027-04", salary="50,000")
    seen["insurance_assigned_before_paying"] = next(
        r for r in c.reserves.list_active() if r["id"] == insurance["id"])["effective_allocated"]
    c.reserves.allocate(insurance["id"], "9,000")
    paid = tx.record_outflow("2027-04-25", cib, "9,000", cat("EXP.PERSONAL.TRANSPORT"), counterparty="Misr Insurance")
    c.reserves.set_expense_link(insurance["id"], paid.id, "9,000")
    c.assets.set_price(comi.id, "2027-04-20", "95")
    c.investments.sell_total("2027-04-20", thndr, comi.id, "75", "7,100", fees="25")
    tx.record_transfer("2027-04-21", thndr, cib, "7,100")
    c.planning.match_payments(day)
    seen["comi_left"] = c.investments.holding(thndr, comi.id, "2027-04-30")
    seen["april_money_in"] = {r.code: r.value for r in c.reporting.money_in_by_category("2027-04-01", "2027-04-30")}
    seen["april_phone"] = payment("Phone installments", "2027-04-15").status.name

    # 24 · May as usual; the rent goes up 10% in June.
    day = on("2027-05-31")
    month("2027-05", salary="50,000")
    c.planning.match_payments(day)
    day = on("2027-06-30")
    month("2027-06", salary="50,000", rent="13,200")
    c.planning.match_payments(day)
    seen["june_rent"] = payment("Landlord", "2027-06-03").status.name
    c.planning.set_amount(item("Landlord").id, "13,200")
    seen["july_rent_planned"] = payment("Landlord", "2027-07-03").amount

    # 25 · July: the Sahel trip is set aside, and spent in August.
    day = on("2027-07-31")
    month("2027-07", salary="50,000", rent="13,200")
    c.planning.match_payments(day)
    trip = c.reserves.create("Sahel trip", "15,000", due_date="2027-08-15")
    c.reserves.allocate(trip["id"], "15,000")

    # 26 · August: the trip, then Omar leaves ACME with a 30,000 end-of-service payment.
    day = on("2027-08-31")
    month("2027-08", salary="50,000", rent="13,200")
    c.planning.match_payments(day)
    spent = tx.record_outflow("2027-08-12", cib, "14,200", cat("EXP.PERSONAL.TRAVEL"), counterparty="Hacienda Bay")
    c.reserves.set_expense_link(trip["id"], spent.id, "14,200")
    seen["trip_left"] = next(r for r in c.reserves.list_active() if r["id"] == trip["id"])["effective_allocated"]
    tx.record_inflow("2027-08-31", cib, "30,000", cat("EXP.WORK.BONUS"), counterparty="ACME Egypt", notes="End of service")
    seen["average_for_september"] = c.budgets.income_average("2027-09").amount
    c.planning.remove(item("ACME Egypt").id)
    c.planning.create(kind="INCOME", name="Valeo", amount="55,000", frequency="MONTHLY", interval_count="1",
                      start_date="2027-10-01", account_id=str(cib), category_id=str(cat("EXP.WORK.SALARY")),
                      counterparty_id="")

    # 27 · September: between jobs.
    day = on("2027-09-30")
    month("2027-09", salary=None, rent="13,200")
    c.planning.match_payments(day)
    forecast = c.forecaster.forecast(day)
    seen["gap"] = (forecast.next_income_date, forecast.months[1].income)
    seen["average_for_october"] = c.budgets.income_average("2027-10").amount

    # 28 · The year.
    seen["year_cash_flow"] = c.reporting.cash_flow("2026-10-01", "2027-09-30")
    seen["year_change_in_what_you_own"] = c.position.change_in_what_you_own("2026-10-01", "2027-09-30")[0]
    seen["year_position"] = c.position.at(day)
    seen["year_checks"] = {check.status for check in c.integrity.checks("2027-09-30")}
    seen["still_due"] = [p for p in c.planning.all_payments(day, day) if p.status.name == "DUE"]
    return seen


def test_11_an_ordinary_month_settles_itself(year):
    assert year["october_due"] == []


def test_12_an_atm_withdrawal_costs_only_its_fee(year):
    assert year["atm_net_worth_change"] == D("-25")


def test_13_a_refund_reduces_shopping_in_the_month_it_arrives(year):
    assert year["shopping_august"] == D("1299")
    assert year["shopping_october"] == D("-1299")  # the refund's own month, not August's


def test_14_a_repair_from_the_emergency_fund_leaves_free_cash_alone(year):
    reserves, free_cash_change, cash_change = year["repair"]
    assert reserves == D("13500")
    assert free_cash_change == 0
    assert cash_change == D("-6500")


def test_15_a_dividend_is_investment_income_not_pay(year):
    assert year["november_money_in"] == {"EXP.WORK.SALARY": D("45000"), "EXP.INVEST.DIVIDEND": D("300")}


def test_16_a_reimbursed_work_expense_nets_to_zero(year):
    assert year["december_work_spending"] == 0


def test_17_a_bonus_does_not_change_average_monthly_income(year):
    assert year["average_for_january"] == D("45000")  # today 90,000


def test_18_an_early_payday_settles_next_months_salary(year):
    assert year["january_salary_transaction"] in year["january_salary_candidates"]
    assert year["january_salary"] == "PAID"
    assert year["january_forecast_income"] == 0  # today the forecast expects 45,000 again
    assert year["average_for_february"] == D("45000")  # today 112,500


def test_19_a_yearly_bill_is_spread_over_the_months_left(year):
    assert year["insurance_saving"] == D("2250")


def test_19_saving_for_a_goal_assigns_no_cash_until_he_does(year):
    assert year["insurance_assigned_before_paying"] == 0


def test_20_a_raise_requires_confirmation_and_only_changes_later_plan_on_choice(year):
    assert year["raise_transaction"] in year["raise_candidates_before_confirmation"]
    assert year["raise_status_before_confirmation"] == "DUE"


def test_20_after_linking_the_raise_later_payments_follow_and_history_stays(year):
    assert year["raise"] == ("PAID", D("50000"), D("45000"))


def test_21_eid_gifts_do_not_change_pay(year):
    assert year["average_for_april"] == D("48333.33")


def test_22_installments_are_owed_and_settle_monthly(year):
    assert year["phone_owed"] == D("24000")
    assert year["april_phone"] == "PAID"


def test_23_a_sale_and_moving_the_cash_home_are_not_income(year):
    assert year["comi_left"] == D("75")
    assert year["april_money_in"] == {"EXP.WORK.SALARY": D("50000")}


def test_24_a_rent_rise_inside_the_tolerance_is_strictly_matched(year):
    assert year["june_rent"] == "PAID"


def test_24_the_plan_follows_the_new_rent_only_after_omar_chooses_it(year):
    assert year["july_rent_planned"] == D("13200")


def test_25_a_trip_paid_from_its_goal_leaves_the_rest(year):
    assert year["trip_left"] == D("800")


def test_26_end_of_service_does_not_change_average_monthly_income(year):
    assert year["average_for_september"] == D("50000")  # Bonus is irregular income, so it is not averaged


def test_27_between_jobs_the_next_income_is_the_new_employer(year):
    assert year["gap"] == ("2027-10-01", D("55000"))


def test_27_a_month_without_pay_does_not_raise_average_monthly_income(year):
    assert year["average_for_october"] <= D("50000")


def test_28_the_year_adds_up(year):
    flow = year["year_cash_flow"]
    assert (flow.inflows, flow.outflows) == (D("651300"), D("295186"))
    assert year["year_change_in_what_you_own"] == D("357364")
    position = year["year_position"]
    assert position.net_worth == position.what_you_own - position.what_you_owe
    assert position.loans_still_to_pay == D("34500")  # 9 car-loan and 6 phone payments left
    assert year["year_checks"] == {"PASS"}
    assert year["still_due"] == []
