"""Four rich fictional Egyptian sample stories for the empty-profile welcome screen."""
from __future__ import annotations

from datetime import date

from lightning.core.dates import fmt_date, today


# Published personas and the analysis case each is meant to make visible.  Values cover Jan–Oct 2026.
STORY_PROFILES = {
    "amr": {"name": "Amr", "label": "Cash flow", "title": "The resourceful side hustler",
              "opening": "28000", "income": [14500] * 10,
              "extra": [0, 7000, 0, 12000, 0, 22000, 0, 9000, 0, 16000],
              "spending": [13800, 14200, 15100, 14400, 15800, 14900, 15100, 14600, 16000, 15000],
              "question": "Which months run short if a side deal pays late?"},
    "abdelrahman": {"name": "Abdelrahman", "label": "Consistency", "title": "The steady engineer",
                      "opening": "60000", "income": [32000] * 5 + [36000] * 5,
                      "extra": [0, 0, 0, 0, 15000, 0, 0, 0, 0, 0],
                      "spending": [20300, 20100, 20500, 20700, 21100, 29400, 20400, 20900, 20600, 21000],
                      "question": "How does one overspend month affect steady investing?"},
    "menna": {"name": "Menna", "label": "Safety", "title": "The freelance artist",
                "opening": "60000", "income": [12000, 26000, 0, 33000, 8000, 0, 28000, 15000, 0, 24000],
                "extra": [0] * 10, "spending": [15300, 16100, 14800, 16600, 15500, 14900, 16400, 15800, 15100, 16000],
                "question": "How much reserve bridges quiet months and late invoices?"},
    "fatma": {"name": "Fatma", "label": "Emergency reserve", "title": "The household organiser",
                "opening": "30000", "income": [18000] * 10, "extra": [0] * 10,
                "spending": [17300, 17100, 17400, 17200, 17300, 25100, 17200, 17400, 17300, 17100],
                "question": "How does a gradual reserve absorb a refrigerator repair?"},
}


def sample_stories() -> list[dict[str, str]]:
    return [{"key": key, "name": story["name"], "label": story["label"], "title": story["title"],
             "question": story["question"]} for key, story in STORY_PROFILES.items()]


def load_story(c, key: str, as_of: date | None = None) -> dict:
    """Load a rich fictional 2026 story into an empty profile; no external test/CSV files needed."""
    if c.accounts.list():
        raise ValueError("A sample story can only be added to an empty Lightning.")
    story = STORY_PROFILES.get(key)
    if story is None:
        raise ValueError("There is no such sample story.")
    day = min(as_of or today(), date(2026, 10, 31))
    day = max(day, date(2026, 1, 1))
    category = {code: c.categories.get_by_code(code).id for code in (
        "EXP.WORK.SALARY", "EXP.WORK.BONUS", "EXP.PERSONAL.HOUSING", "EXP.PERSONAL.FOOD",
        "EXP.PERSONAL.UTILITIES", "EXP.PERSONAL.SHOPPING", "EXP.INVEST.INTEREST")}
    with c.db.transaction():
        bank = c.account_flows.open_account(f"{story['name']} bank", "BANK", "2026-01-01", story["opening"],
                                            institution="CIB")
        brokerage = equity_fund = None
        if key == "abdelrahman":
            brokerage = c.account_flows.open_account("Abdelrahman investments", "BROKERAGE", "2026-01-01", "0",
                                                     institution="Fictional Equity Fund")
            equity_fund = c.assets.create_investment("Fictional Egyptian Equity Fund", "FUND.EQUITY", "SAMPLEEQ")
        posted = 0
        for month in range(1, 11):
            income_date = date(2026, month, 1)
            if income_date > day:
                break
            income = story["income"][month - 1]
            if income:
                c.transactions.record_inflow(fmt_date(income_date), bank.id, str(income),
                                             category["EXP.WORK.SALARY"], counterparty="Salary or client payment")
                posted += 1
            extra = story["extra"][month - 1]
            extra_date = date(2026, month, 15)
            if extra and extra_date <= day:
                kind = category["EXP.WORK.BONUS"] if key == "abdelrahman" else category["EXP.INVEST.INTEREST"]
                c.transactions.record_inflow(fmt_date(extra_date), bank.id, str(extra), kind,
                                             counterparty="Performance bonus" if key == "abdelrahman" else "Side project")
                posted += 1
            rent_date, day_to_day_date = date(2026, month, 3), date(2026, month, 18)
            rent = round(story["spending"][month - 1] * 0.48)
            if rent_date <= day:
                c.transactions.record_outflow(fmt_date(rent_date), bank.id, str(rent), category["EXP.PERSONAL.HOUSING"],
                                              counterparty="Landlord")
                posted += 1
            if day_to_day_date <= day:
                c.transactions.record_outflow(fmt_date(day_to_day_date), bank.id, str(story["spending"][month - 1] - rent),
                                              category["EXP.PERSONAL.FOOD"], counterparty="Household and everyday spending")
                posted += 1
            invest_date = date(2026, month, 25)
            if brokerage is not None and equity_fund is not None and invest_date <= day:
                contribution = 6000 if month < 6 else 8500
                c.transactions.record_transfer(fmt_date(invest_date), bank.id, brokerage.id, str(contribution))
                c.investments.buy_total(fmt_date(invest_date), brokerage.id, equity_fund.id,
                                        str(contribution / 100), str(contribution), notes="Monthly investment")
                c.assets.set_price(equity_fund.id, fmt_date(invest_date), str(100 + month * 2))
                posted += 2
        month = fmt_date(day)[:7]
        suggested = c.budgets.suggested_plan(month)
        if suggested:
            c.budgets.save_month(month, suggested)
        if key == "menna":
            c.reserves.set_emergency_fund("4000", "60000")
        elif key == "fatma":
            c.reserves.set_emergency_fund("7800", "54000")
    return {"name": story["name"], "accounts": len(c.accounts.list()), "rows": posted,
            "from": "2026-01-01", "to": fmt_date(day)}
