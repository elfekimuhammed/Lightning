"""Chart geometry, key notes and the sample household (the demo pass on every tab)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from lightning.demo import build_demo
from lightning.ui import charts, keynotes
from lightning.ui.web import create_app

D = Decimal


# ---------------------------------------------------------------- chart geometry

def test_a_trend_with_one_month_says_so_instead_of_drawing():
    assert charts.trend(["2026-09"], [{"name": "Money out", "tone": "spend", "values": [D(100)]}])["too_short"]
    assert charts.trend([], [])["too_short"]


def test_a_trend_starts_at_zero_and_marks_months_over_plan():
    t = charts.trend(["2026-07", "2026-08", "2026-09"],
                     [{"name": "Money out", "tone": "spend", "values": [D(800), D(1200), None]}], plan=D(1000))
    assert not t["too_short"]
    assert [tick["value"] for tick in t["ticks"]][-1] == 0 and t["ticks"][-1]["y"] == 100  # the axis starts at zero
    dots = t["series"][0]["dots"]
    assert [d["label"] for d in dots] == ["2026-07", "2026-08"]  # a missing month is not drawn as zero
    assert [d["over"] for d in dots] == [False, True]
    assert 0 < t["plan"]["y"] < 100 and t["series"][0]["last"]["value"] == D(1200)


def test_bars_are_largest_first_and_fold_the_rest():
    b = charts.bars([{"label": name, "value": D(value)} for name, value in
                     (("Food", 400), ("Rent", 1000), ("Fees", 15), ("Gifts", 200), ("Zero", 0))], limit=3)
    assert [r["label"] for r in b["rows"]] == ["Rent", "Food", "Gifts"]
    assert b["rows"][0]["width"] == 100 and b["rows"][1]["width"] == 40
    assert b["more"] == 1 and b["more_total"] == D(15)  # a zero row is left out, not counted


def test_a_meter_over_plan_fills_and_says_so():
    over = charts.meter(D(90), D("67.50"))
    assert over["over"] and over["width"] == 100 and over["left"] == D("-22.50")
    under = charts.meter(D(50), D(200))
    assert not under["over"] and under["width"] == 25 and under["left"] == D(150)
    assert charts.meter(D(10), None)["left"] is None


def test_class_tones_pick_the_most_specific_code():
    assert charts.class_tone("FUND.GOLD") == "gold"
    assert charts.class_tone("FUND.MONEY_MARKET") == "deposits"
    assert charts.class_tone("FUND.EQUITY") == "equity"
    assert charts.class_tone("STOCK") == "equity"
    assert charts.class_tone("CRYPTO") == "other"


def test_a_donut_keeps_the_largest_parts_in_class_order():
    slices = [{"label": "Stocks", "value": D(500), "tone": "equity"},
              {"label": "Cash", "value": D(100), "tone": "cash"},
              {"label": "Gold", "value": D(300), "tone": "gold"},
              {"label": "Deposits", "value": D(200), "tone": "deposits"},
              {"label": "Watch", "value": D(5), "tone": "other"},
              {"label": "Car", "value": D(4), "tone": "other"}]
    d = charts.donut(slices, limit=5)
    assert [s["label"] for s in d["segments"]] == ["Cash", "Deposits", "Gold", "Stocks", "Other"]
    assert d["segments"][-1]["value"] == D(9)  # the two smallest folded, the large equity slice kept
    assert d["total"] == D(1109)
    assert round(sum(s["share"] for s in d["segments"]), 6) == 100
    assert d["segments"][0]["offset"] == 25  # starts at 12 o'clock
    assert charts.donut([{"label": "Nothing", "value": D(0), "tone": "cash"}])["segments"] == []


# ---------------------------------------------------------------- key notes

def test_budget_notes_speak_plainly_about_the_days_left():
    assert keynotes.per_day(D(300), 10) == "About 30.00 a day for 10 days"
    assert keynotes.per_day(D(300), 1) == "Today is the last day of the month"
    assert keynotes.per_day(D(-5), 3) == "Spending passed the plan"
    assert keynotes.budget_left(D(300), 10, [], "#m") == []  # the Left in plan card already says it
    notes = keynotes.budget_left(D(-50), 0, ["Food", "Fuel", "Fees"], "#m")
    assert len(notes) == 1 and notes[0]["title"] == "Food, Fuel and 1 more over plan" and notes[0]["tone"] == "attention"
    assert keynotes.budget_left(D(-50), 0, [], "#m")[0]["title"] == "50.00 over plan this month"


def test_needs_you_leads_with_the_first_item_and_counts_the_rest():
    items = [{"label": "Bill due: Rent", "detail": "Due 2026-09-03", "href": "/plan", "action": "Mark paid", "popup": True},
             {"label": "Loan payment due: Car", "detail": "Due 2026-09-05", "href": "/plan"}]
    first = keynotes.needs_you(items, D(100), "2026-10-01")
    assert first["title"] == "Bill due: Rent and 1 more" and first["popup"] and first["tone"] == "attention"
    calm = keynotes.needs_you([], D(1500), "2026-10-01")
    assert calm["title"] == "1,500.00 safe to spend until 2026-10-01" and calm["tone"] == "info"


def test_recurring_and_loan_notes_answer_share_and_end_date():
    heavy = keynotes.recurring_summary(D(12000), D(20000), D(0))
    assert heavy["title"] == "Bills take 60% of your 20,000.00 income" and heavy["tone"] == "attention"
    assert keynotes.recurring_summary(D(500), D(0), D(0))["title"] == "Add your income to see its share"

    class Payment:
        amount, due_date = D(2500), "2026-10-05"
    progress = {"still_to_pay": D(52500), "last_date": "2028-06-05", "due": [], "paid": 3, "total": 24, "next": Payment()}
    loan = keynotes.loans_summary([{"progress": progress}])
    assert loan["title"] == "Paid off on 2028-06-05"
    assert loan["text"] == "3 of 24 payments made."  # the next payment is on the loan card
    due = keynotes.loans_summary([{"progress": {**progress, "due": [Payment()]}}])
    assert due["title"] == "1 loan payment due now" and due["tone"] == "attention"


def test_comparing_spending_with_the_month_before():
    assert keynotes.compared(D(900), D(1000), "2026-08")["title"] == "100.00 less than 2026-08"
    assert keynotes.compared(D(1100), D(1000), "2026-08")["tone"] == "attention"
    assert keynotes.compared(D(1100), None, "") is None


# ---------------------------------------------------------------- the sample household

@pytest.fixture
def demo(c, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    summary = build_demo(c)
    return c, summary


def test_the_demo_household_adds_up(demo):
    c, summary = demo
    assert summary == {"accounts": 6, "from": "2026-07-01", "to": "2026-09-30"}
    position = c.position.at(date(2026, 9, 30))
    assert position.holdings_value == D("77902.50")
    assert position.held_for_others == D(10000)
    assert position.loans_still_to_pay == D(52500)  # 21 car-loan payments left
    assert position.net_worth == position.what_you_own - position.what_you_owe
    assert position.free_cash == position.cash_you_own - position.reserves - position.bills_due
    assert c.budgets.income_average("2026-09").amount == D(45000)
    assert c.budgets.has_plan("2026-09")
    assert position.reserves == D(20000)  # the emergency fund
    # Every recurring payment that went out is matched to its transaction: nothing is due.
    assert position.bills_due == 0


def test_the_demo_only_fills_an_empty_lightning(demo):
    c, _ = demo
    with pytest.raises(ValueError):
        build_demo(c)


def test_every_tab_of_the_demo_opens_with_its_key_notes(demo):
    c, _ = demo
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    with_notes = ["/", "/budget", "/birdview", "/birdview/expenses", "/investments", "/plan", "/plan/recurring",
                  "/plan/loans", "/plan/reserves"]
    for url in with_notes + ["/money-from-others", "/transactions", "/settings"]:
        page = client.get(url)
        assert page.status_code == 200, url
        if url in with_notes:
            assert 'aria-label="Key notes"' in page.text, url
    overview = client.get("/").text
    assert "chart-donut" in overview and "chart-bar-row" in overview
    assert "chart-trend" in client.get("/birdview").text  # month by month lives on Birdview


def test_the_welcome_button_adds_the_demo_only_once(c, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    assert "See Lightning with a sample household" in client.get("/").text
    added = client.post("/demo", follow_redirects=False)
    assert added.status_code == 303 and "Sample+household+added" in added.headers["location"].replace("%20", "+")
    assert len(c.accounts.list()) == 6
    again = client.post("/demo", follow_redirects=False)
    assert again.status_code == 303 and len(c.accounts.list()) == 6


def test_the_demo_launcher_never_touches_another_database(tmp_path):
    from lightning.main import main
    real = tmp_path / "lightning.db"
    real.write_bytes(b"my real money")
    with pytest.raises(SystemExit):
        main(["--demo", "--db", str(real), "--no-browser"])
    assert real.read_bytes() == b"my real money"


def test_the_demo_reuses_an_investment_added_before_any_account(c, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    comi = c.assets.create_investment("CIB", "STOCK", "COMI")
    assert build_demo(c)["accounts"] == 6
    thndr = next(a for a in c.accounts.list() if a.name == "THNDR")
    assert c.investments.holding(thndr.id, comi.id, "2026-09-30") == 150  # the same COMI, not a second one


def test_the_spending_trend_follows_a_chosen_category(demo):
    from lightning.ui import visuals
    c, _ = demo
    food = visuals.spending_trend(c, date(2026, 9, 30), "EXP.PERSONAL.FOOD")
    assert food["series"][0]["values"] == [D("4568.50"), D("4762.80"), D("4671.15")]  # Carrefour + Seoudi
    personal = visuals.spending_trend(c, date(2026, 9, 30), "EXP.PERSONAL")
    assert all(v > 0 for v in personal["series"][0]["values"])
    assert personal["plan"] is None  # the dashed plan line is the whole month's plan, so only unfiltered
    everything = visuals.spending_trend(c, date(2026, 9, 30))
    assert everything["plan"]["value"] == c.budgets.month_view("2026-09").available


def test_a_month_is_only_over_plan_against_its_own_plan(demo):
    from lightning.ui import visuals
    c, _ = demo
    # The demo plans September only: July and August can't be "over plan", whatever they spent.
    t = visuals.spending_trend(c, date(2026, 9, 30))
    assert not c.budgets.has_plan("2026-07") and not c.budgets.has_plan("2026-08")
    over = {d["label"]: d["over"] for d in t["series"][0]["dots"]}
    assert over["2026-07"] is False and over["2026-08"] is False
    assert over["2026-09"] is (t["series"][0]["values"][-1] > t["plan"]["value"])
