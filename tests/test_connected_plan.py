"""The parts of the plan talk to each other (owner request 2026-10-05): the savings target set in
Financial health limits the budget, dated goals count in what a month must leave, and the budget,
Needs you, Financial health and Reserves read one check (HealthService.plan_check)."""
import shutil
from decimal import Decimal

from lightning.core.dates import today
from lightning.database import migrator
from lightning.database.connection import Database
from lightning.ui.web import create_app
from lightning.workflows.review import ReviewInbox
from tests.screens import _ScreenClient, visible_text

MONTH = "2026-12"  # conftest pins today to 2026-12-31


def _plan(c, spend: str, fund: str = "60000"):
    """Income 10,000 a month; the emergency fund full (six months) unless the test says otherwise."""
    c.settings.set("budget_manual_monthly_income", "10000")
    if fund:
        c.reserves.set_emergency_fund(fund)
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD").id
    c.budgets.set_budget(food, MONTH, spend)


def test_a_plan_that_leaves_the_savings_target_passes(c):
    _plan(c, "8000")
    check = c.health.plan_check(MONTH)
    assert (check.income, check.planned, check.target_percent) == (Decimal("10000"), Decimal("8000"), Decimal("20"))
    assert check.savings_target == Decimal("2000.00") and check.spending_room == Decimal("8000.00")
    assert check.plan_saves == Decimal("2000") and check.planned_savings_rate == Decimal("20")
    assert check.over_by == 0


def test_a_plan_that_spends_into_the_savings_target_says_how_much_to_cut(c):
    _plan(c, "9000")
    check = c.health.plan_check(MONTH)
    assert check.planned_savings_rate == Decimal("10") and check.over_by == Decimal("1000.00")
    assert check.short_for == "target"
    c.health.set_limit("savings_rate", "5")  # a lower target makes the same plan fine
    assert c.health.plan_check(MONTH).over_by == 0


def test_dated_goals_raise_what_the_month_must_leave(c):
    _plan(c, "8000")
    c.reserves.create("New laptop", "3000", due_date="2026-12-31")  # 3,000 still needed this month
    check = c.health.plan_check(MONTH)
    assert check.goals == Decimal("3000.00") and check.short_for == "goals"
    assert check.to_save == Decimal("3000.00") and check.over_by == Decimal("1000.00")


def test_no_income_or_no_plan_means_no_check(c):
    check = c.health.plan_check(MONTH)
    assert check.planned is None and check.over_by == 0
    assert c.health.plan_check(MONTH).planned_savings_rate is None


def test_screens_share_the_one_check(c):
    _plan(c, "9000")
    c.reserves.create("New laptop", "1200", due_date="2027-11-30")  # 100 a month over 12 months
    browser = _ScreenClient(create_app(c), "http://testserver")
    budget = visible_text(browser.get(f"/budget?period=month&month={MONTH}").text)
    assert "Below your savings target 10%" in budget
    assert "Plan 1,000 less to keep 2,000 a month." in budget
    assert "Plan leaves to save 1,000 (10%); your target is 20%." in budget
    inbox = {item["label"]: item for item in ReviewInbox(c).items(today())}
    item = inbox["This month's plan is below your savings target"]
    assert item["href"] == f"/budget?month={MONTH}" and "Plan 1,000 EGP less" in item["detail"]
    health = visible_text(browser.get("/financial-health").text)
    assert "Planned savings rate" in health and "10.0%" in health
    reserves = visible_text(browser.get("/reserves").text)
    assert "About 100 EGP a month" in reserves


def test_budget_settings_point_to_the_savings_target_instead_of_a_ceiling(c):
    browser = _ScreenClient(create_app(c), "http://testserver")
    page = browser.get("/settings?section=budget").text
    assert "ceiling_percent" not in page
    assert "follows your savings target" in visible_text(page)


def test_migration_0042_keeps_a_custom_ceiling_as_the_savings_target(monkeypatch, tmp_path):
    before = tmp_path / "migrations"
    before.mkdir()
    for path in sorted(migrator._BUNDLED_MIGRATIONS_DIR.glob("*.sql")):
        if int(path.name[:4]) <= 41:
            shutil.copy(path, before / path.name)
    db = Database(":memory:")
    monkeypatch.setattr(migrator, "MIGRATIONS_DIR", before)
    migrator.migrate(db)
    db.execute("INSERT INTO settings(key,value,updated_at) VALUES ('budget_monthly_ceiling_percent','72.5','2026-10-01')")
    monkeypatch.setattr(migrator, "MIGRATIONS_DIR", migrator._BUNDLED_MIGRATIONS_DIR)
    assert migrator.migrate(db)[0] == "0042_savings_target_from_ceiling (APPLIED)"  # later migrations follow it
    assert db.scalar("SELECT value FROM settings WHERE key='financial_health_limit_savings_rate'") == "27.5"
    assert db.scalar("SELECT COUNT(*) FROM settings WHERE key='budget_monthly_ceiling_percent'") == 0


def test_bills_and_subscriptions_are_planned_like_loans_until_you_set_your_own(c):
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD").id
    c.planning.create(kind="SUBSCRIPTION", name="Gym", amount="120", frequency="MONTHLY",
                      start_date="2026-12-20", category_id=food)
    line = next(l for s in c.budgets.month_view(MONTH).sections for l in s.lines if l.category_id == food)
    assert line.budget == Decimal("120") and line.from_bills and not line.from_loans
    assert c.budgets.bill_lines(MONTH) == {food: Decimal("120")}
    c.budgets.set_budget(food, MONTH, "3000")  # your own amount replaces the automatic line
    assert c.budgets.bill_lines(MONTH) == {}


def test_an_emergency_fund_below_six_months_adds_its_top_up(c):
    _plan(c, "8000", fund="12000")  # 12,000 of a 60,000 target: 48,000 over 24 months
    check = c.health.plan_check(MONTH)
    assert check.emergency == Decimal("2000.00") and check.needs == Decimal("2000.00")
    assert check.over_by == 0  # the 20% target already leaves 2,000
    c.reserves.create("New laptop", "500", due_date="2026-12-31")
    check = c.health.plan_check(MONTH)
    assert check.short_for == "goals" and check.over_by == Decimal("500.00")
    assert check.needs_label == "your goals and emergency fund need"


def test_fill_this_month_stops_at_most_you_can_plan(c):
    c.settings.set("budget_manual_monthly_income", "10000")
    c.reserves.set_emergency_fund("60000")
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD").id
    transport = c.categories.get_by_code("EXP.PERSONAL.TRANSPORT").id
    c.budgets.set_budget(food, "2026-11", "9000", only_this_month=True)
    c.budgets.set_budget(transport, "2026-11", "1000", only_this_month=True)
    proposal, left = c.health.fit_fill(c.budgets.fill_proposal(MONTH, "last_month"))
    rows = {row.category_id: row for row in proposal.rows}
    assert not rows[food].selected and "Past Most you can plan: 8,000 of room left." in rows[food].conflict
    assert rows[transport].selected and left == Decimal("7000.00")
    page = visible_text(_ScreenClient(create_app(c), "http://testserver").get(f"/budget/fill?month={MONTH}").text)
    assert "Most you can plan 8,000 EGP, to leave 2,000 to save." in page


def test_saving_a_bill_or_loan_says_where_your_limits_stand(c):
    c.settings.set("budget_manual_monthly_income", "10000")
    c.planning.create(kind="BILL", name="Rent", amount="4500", frequency="MONTHLY", start_date="2027-01-01")
    assert c.health.commitments_note("BILL") == "Fixed costs to income is now 45%, within your 50% limit."
    c.planning.create(kind="LOAN", name="Car loan", amount="2500", frequency="MONTHLY",
                      start_date="2027-01-01", payment_count="12")
    assert c.health.commitments_note("LOAN") == ("Fixed costs to income is now 70%, above your 50% limit; "
                                                 "Loan payments to income is now 25%, above your 20% limit.")
    assert c.health.commitments_note("INCOME") == ""
    browser = _ScreenClient(create_app(c), "http://testserver")
    form = browser.get("/plan/items/new?kind=SUBSCRIPTION")
    assert form.status_code == 200


# ---- More of the plan connected (owner request 2026-10-05: "make things smart")

def test_safe_to_spend_and_the_forecast_keep_the_emergency_top_up(c):
    # The budget asks each month to leave the fund's top-up; the forecast and Safe to spend hold it back too.
    _plan(c, "8000", fund="12000")  # 48,000 short of 60,000: 2,000 a month
    f = c.forecaster.forecast(today())
    assert [m.emergency_saving for m in f.months] == [Decimal("2000.00")] * 3
    assert all(m.money_out == m.commitments + m.budget_spending + m.goal_saving + m.emergency_saving for m in f.months)
    parts = dict(f.safe_to_spend_parts)
    assert parts["Emergency fund top-up"] == Decimal("-2000.00")
    assert f.safe_to_spend == f.free_cash + sum(v for k, v in parts.items() if k != "Free cash")
    c.reserves.set_emergency_fund("60000")  # a full fund needs nothing
    assert "Emergency fund top-up" not in dict(c.forecaster.forecast(today()).safe_to_spend_parts)


def test_recurring_income_stands_in_until_a_month_has_income(c):
    # A new profile with its salary set up in Recurring gets a checked plan from the first day.
    assert c.budgets.income_average(MONTH).amount is None
    c.planning.create(kind="INCOME", name="Salary", amount="12000", frequency="MONTHLY", start_date="2027-01-01")
    average = c.budgets.income_average(MONTH)
    assert (average.amount, average.scheduled, average.window) == (Decimal("12000.00"), True, "from your recurring income")
    c.reserves.set_emergency_fund("72000")
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD").id
    c.budgets.set_budget(food, MONTH, "11000")
    assert c.health.plan_check(MONTH).over_by == Decimal("1400.00")  # 20% of 12,000 is 2,400; the plan leaves 1,000
    page = visible_text(_ScreenClient(create_app(c), "http://testserver").get("/plan/reserves").text)
    assert "From your recurring income" in page


def test_saving_the_target_or_a_goal_says_what_it_does_to_the_plan(c):
    _plan(c, "8000")
    assert c.health.plan_note() == "Most you can plan this month is now 8,000; this month's plan fits."
    c.health.set_limit("savings_rate", "30")
    assert c.health.plan_note() == "Most you can plan this month is now 7,000; this month's plan is 1,000 over it."
    c.planning.create(kind="BILL", name="Rent", amount="7500", frequency="MONTHLY", start_date="2027-01-01")
    assert c.health.plan_note().endswith("Bills and loan payments alone come to 7,500 a month, more than that.")
    c.reserves.create("Wedding", "20000", due_date="2026-12-31")
    assert c.health.plan_note() == ("Saving needed is now 20,000 a month, all of your income: "
                                    "give a goal a later date or a smaller target.")
    browser = _ScreenClient(create_app(c), "http://testserver")
    page = visible_text(browser.post("/settings/financial-health-limit",
                                     data={"key": "savings_rate", "value": "25", "action": "save"}).text)
    assert "Financial health limit saved. Saving needed is now 20,000 a month" in page
    page = visible_text(browser.post("/reserves", data={"name": "Phone", "target": "600",
                                                        "due_date": "2027-05-31"}).text)
    assert "Created Phone. Saving needed is now" in page


def test_needs_you_names_a_category_planned_below_its_bills(c):
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD").id
    c.planning.create(kind="BILL", name="Groceries box", amount="900", frequency="MONTHLY",
                      start_date="2026-12-20", category_id=food)
    assert c.budgets.below_scheduled(MONTH) == []  # no rule of its own: the bill plans the category
    c.budgets.set_budget(food, MONTH, "500")
    assert c.budgets.below_scheduled(MONTH) == [{"category_id": food, "name": "Food & Groceries", "planned": Decimal("500"),
                                                 "scheduled": Decimal("900")}]
    inbox = {item["label"]: item for item in ReviewInbox(c).items(today())}
    item = inbox["Food & Groceries is planned below its bills"]
    assert item["detail"] == "Planned 500 EGP; bills and loan payments scheduled this month come to 900."
    assert item["href"] == f"/budget?month={MONTH}"
    c.budgets.set_budget(food, MONTH, "900")
    assert c.budgets.below_scheduled(MONTH) == []
