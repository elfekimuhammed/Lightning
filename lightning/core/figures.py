"""One name, one meaning and one formula for every figure Lightning reports.

Screens read labels and formulas from here, so a figure is never called one thing on one tab and
something else on another. A derived figure is written as a formula of other figures in this
table; it is never computed a second way. docs/GLOSSARY.md mirrors this table, and a test keeps
them in step.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Figure:
    key: str
    label: str
    meaning: str
    formula: str = ""        # empty for a base figure read from the ledger

    @property
    def equation(self) -> str:
        return f"{self.label} = {self.formula}" if self.formula else ""


_TABLE = [
    # ------------------------------------------------------------ position (a date)
    ("in_your_accounts", "In your accounts", "Everything in your accounts, including what you hold for other people.",
     "What you own + Held for others"),
    ("held_for_others", "Held for others", "Money and units in your accounts that belong to other people."),
    ("what_you_own", "What you own", "The value of everything in your accounts that is yours.",
     "Cash you own + Deposits + Holdings value + Other you own"),
    ("bank_and_wallet_cash", "Bank and wallet cash", "Your cash in bank accounts and wallets."),
    ("brokerage_cash", "Brokerage cash", "Your uninvested cash inside brokerage accounts."),
    ("cash_you_own", "Cash you own", "Your cash in banks, wallets and brokerage accounts.",
     "Bank and wallet cash + Brokerage cash"),
    ("deposits", "Deposits", "Your certificates and time deposits, at their balance."),
    ("holdings_value", "Holdings value", "Your stocks, funds, gold and other holdings at their latest price."),
    ("other_you_own", "Other you own", "Anything you own that is not cash, a deposit or a holding.",
     "What you own − Cash you own − Deposits − Holdings value"),
    ("reserves", "Reserves", "Cash you set aside for emergencies and dated goals. It stays in what you own."),
    ("bills_due", "Bills due", "Bills, subscriptions and loan payments dated today or earlier that nothing has paid yet."),
    ("loans_still_to_pay", "Loans still to pay", "Every loan payment not paid yet, due or upcoming."),
    ("what_you_owe", "What you owe", "Payments you are certain to make: bills already due and loans.",
     "Bills due (other than loan payments) + Loans still to pay"),
    ("net_worth", "Net worth", "What you own after what you owe.", "What you own − What you owe"),
    ("free_cash", "Free cash", "Cash you can spend without touching reserves or leaving a bill unpaid.",
     "Cash you own − Reserves − Bills due"),
    ("portfolio_value", "Portfolio value", "Your holdings and the cash waiting in your brokerage accounts.",
     "Holdings value + Brokerage cash"),
    ("holdings_after_sale", "Holdings after sale (estimate)",
     "What your holdings might fetch if sold, after each class's sale factor.",
     "Σ Holdings value of each class × its sale factor"),
    ("investments_after_sale", "Deposits and holdings after sale (estimate)",
     "What deposits and holdings might fetch if cashed in today.",
     "Deposits × sale factor + Holdings after sale (estimate)"),
    ("if_you_sold_today", "If you sold today (estimate)",
     "Free cash plus what your deposits and holdings might fetch.",
     "Free cash + Deposits and holdings after sale (estimate)"),
    # ------------------------------------------------------------ activity (a period)
    ("money_in", "Money in", "Your posted income in the period. Transfers, trades and money held for others are left out."),
    ("money_out", "Money out", "Your posted spending in the period, after refunds. Transfers, trades and money held for others are left out."),
    ("net_flow", "Net flow", "What was left of money in after money out.", "Money in − Money out"),
    ("savings_rate", "Savings rate", "The share of money in that you kept.", "Net flow ÷ Money in"),
    ("change_in_what_you_own", "Change in what you own", "How much what you own grew or shrank in the period.",
     "What you own at the end − What you own the day before the start"),
    ("average_monthly_income", "Average monthly income",
     "Income in your chosen income categories, averaged over the last 3 or 6 completed months that had any "
     "(Settings › Budget). The budget, reserves and the cash forecast all use it."),
    # ------------------------------------------------------------ budget (a month)
    ("base_budget", "Base budget", "The amount the budget rule gives: fixed, a share of income or an average."),
    ("carryover", "Carryover", "Last month's left in plan, when carryover is on."),
    ("planned", "Planned", "What you plan to spend this month.", "Base budget + Carryover"),
    ("spent", "Spent", "Money out in the category this month."),
    ("left_in_plan", "Left in plan", "What is left of the plan.", "Planned − Spent"),
    # ------------------------------------------------------------ investments (a period)
    ("cost", "Cost", "What you paid for the units you still hold."),
    ("unrealized_gain", "Unrealized gain", "Gain or loss on units you still hold.", "Holdings value − Cost"),
    ("change_in_unrealized_gain", "Change in unrealized gain", "How unrealized gain moved in the period.",
     "Unrealized gain at the end − Unrealized gain at the start"),
    ("realized_gain", "Realized gain", "Sale proceeds less the cost of the units sold."),
    ("dividends_and_interest", "Dividends and interest", "Distributions and interest received."),
    ("result", "Result", "What your investments earned in the period.",
     "Realized gain + Change in unrealized gain + Dividends and interest"),
    ("new_money_in", "New money in", "Cash moved into investment accounts from outside, less cash taken out."),
    # ------------------------------------------------------------ cash planning
    ("safe_to_spend", "Safe to spend", "Free cash after what is promised before your next income. An estimate.",
     "Free cash − Bills and loan payments before next income − Left in plan this month − Saving for goals"),
    ("payments_before_next_income", "Bills and loan payments before next income",
     "Scheduled bills, subscriptions and loan payments that are not due yet, up to your next income."),
    ("saving_for_goals", "Saving for goals", "What dated reserve goals still need this month, spread over the months left."),
]

FIGURES: dict[str, Figure] = {row[0]: Figure(*row) for row in _TABLE}

# Names that used to appear on screens, each mapped to the figure that replaced it.
RETIRED_NAMES = {
    "All accounts": "in_your_accounts", "Gross balances": "in_your_accounts",
    "Money from others": "held_for_others", "Cash held for others": "held_for_others",
    "Owned value": "what_you_own", "Owned net worth": "what_you_own", "What I own": "what_you_own",
    "Liquid cash": "cash_you_own", "Owned liquid cash": "cash_you_own",
    "Investment cash": "brokerage_cash",
    "Investments and deposits": "deposits", "Investment holdings": "holdings_value",
    "Current owned value": "holdings_value", "Other owned assets": "other_you_own",
    "Assigned reserves": "reserves", "Assigned to reserves": "reserves", "Cash reserved": "reserves",
    "Estimated liquid investments": "investments_after_sale", "Estimated cash after sale": "holdings_after_sale",
    "Estimated available value": "if_you_sold_today",
    "Total spending": "money_out", "Net income less spending": "net_flow", "Cashflow": "net_flow",
    "Average monthly salary": "average_monthly_income", "Budgeted": "planned", "Current budget": "planned",
    "Invested capital": "cost", "What you paid in total": "cost",
    "Unrealized gain/loss": "unrealized_gain", "Change in unrealized value": "change_in_unrealized_gain",
    "Realized gain or loss": "realized_gain", "Distributions": "dividends_and_interest",
    "Investment result": "result", "Period result": "result", "Period gain/loss": "result",
    "New money added this period": "new_money_in", "Cash added and withdrawn": "new_money_in",
}


def label(key: str) -> str:
    return FIGURES[key].label


def equation(key: str) -> str:
    return FIGURES[key].equation
