"""One name, one meaning, one formula and one function for every figure Lightning reports.

Lightning has three layers:

- **Ledger** — real money. Posted transactions: where money actually came from and went.
- **Plan** — what-if. Budgets, reserves, scheduled bills and loans, sale factors and the forecast.
  Nothing in it moves money; it sits on top of the ledger to help you plan.
- **Report** — reads the other two and presents them. It stores nothing of its own.

Every figure below is shown by the report layer. Its ``layer`` says where its inputs come from
(the ledger, the plan, or both), and ``function`` names the one piece of code that computes it.
Screens read labels and formulas from here, so a figure is never called one thing on one tab and
something else on another, and a derived figure is a formula of other figures, never computed a
second way. docs/GLOSSARY.md is generated from this table; tests keep them in step and check that
every ``function`` exists.
"""
from __future__ import annotations

from dataclasses import dataclass


LEDGER, PLAN, BOTH = "Ledger", "Plan", "Ledger + Plan"
LAYERS = {
    LEDGER: "Real money: posted transactions and the balances and prices they give.",
    PLAN: "What-if: budgets, reserves, scheduled bills and loans, sale factors and forecasts. Moves no money.",
    BOTH: "Real money adjusted by a plan, for example cash after what is set aside.",
}


@dataclass(frozen=True)
class Figure:
    key: str
    label: str
    meaning: str
    formula: str = ""        # empty for a base figure read directly from its layer
    layer: str = LEDGER      # where its inputs come from
    function: str = ""       # dotted path of the code that computes it

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
    ("reserves", "Reserves", "Cash you set aside for emergencies and dated goals, less what linked payments "
     "already used. It stays in your accounts and in what you own."),
    ("bills_due", "Bills due", "Bills, subscriptions and loan payments dated today or earlier that nothing has paid yet."),
    ("loans_still_to_pay", "Loans still to pay", "Every loan payment not paid yet, due or upcoming."),
    ("what_you_owe", "What you owe", "Payments you are certain to make: bills already due and loans.",
     "Bills due (other than loan payments) + Loans still to pay"),
    ("net_worth", "Net worth", "What you own after what you owe.", "What you own − What you owe"),
    ("free_cash", "Free cash", "Cash you can spend without touching reserves or leaving a bill unpaid.",
     "Cash you own − Reserves − Bills due"),
    ("portfolio_value", "Portfolio value", "Your holdings at their latest price. Cash waiting in a brokerage "
     "account is not part of it: it counts in Cash you own (owner decision 2026-10-04).", "Holdings value"),
    ("holdings_after_sale", "Holdings after sale (estimate)",
     "What your holdings might fetch if sold, after each class's sale factor.",
     "Σ Holdings value of each class × its sale factor"),
    ("investments_after_sale", "Investments if sold (estimate)",
     "What redeemable deposits and holdings might fetch if cashed in today. CDs before earliest withdrawal "
     "contribute 0; early-redeemable CDs use ledger balance × CD sale factor; matured CDs use ledger balance.",
     "Deposits × sale factor + Holdings after sale (estimate)"),
    ("if_you_sold_today", "If you sold today (estimate)",
     "Free cash plus what your deposits and holdings might fetch.",
     "Free cash + Investments if sold (estimate)"),
    # ------------------------------------------------------------ activity (a period)
    ("money_in", "Money in", "Your posted income in the period. Transfers, trades and money held for others are left out."),
    ("money_out", "Money out", "Your posted spending in the period, after refunds. Transfers, trades and money held for others are left out."),
    ("net_flow", "Net flow", "What was left of money in after money out.", "Money in − Money out"),
    ("savings_rate", "Savings rate", "The share of money in that you kept.", "Net flow ÷ Money in"),
    ("opening_balances_in_period", "Opening balances in the period", "Money and assets you recorded as already yours (opening balances and existing holdings) during the period. They were yours before, so they are not a change."),
    ("change_in_what_you_own", "Change in what you own", "How much what you own grew or shrank in the period.",
     "What you own at the end − What you own the day before the start − Opening balances in the period"),
    ("change_in_net_worth", "Change in net worth", "How much net worth grew or shrank in the period.",
     "Net worth at the end − Net worth the day before the start − Opening balances in the period"),
    ("investing_rate", "Investing rate", "The share of money in that you moved into investments, out of what you saved, so it is never more than the savings rate.",
     "Money added ÷ Money in"),
    ("average_monthly_income", "Average monthly income",
     "Income in your chosen income categories, averaged over the last 3 or 6 completed months that had any "
     "(Settings › Budget). The budget, reserves and the cash forecast all use it."),
    # ------------------------------------------------------------ budget (a month)
    ("base_budget", "Base budget", "The amount the budget rule gives: fixed, a share of income or an average."),
    ("carryover", "Carryover", "Unused plan from last month, added to this month when carryover is on.",
     "Left in plan last month"),
    ("planned", "Planned", "What you plan to spend this month. The month's total also counts background "
     "estimates for untracked categories; one from a single month of spending is low confidence and shows a "
     "\"!\" that says why.", "Base budget + Carryover"),
    ("spent", "Spent", "Money out in the category this month."),
    ("left_in_plan", "Left in plan", "What is left of the plan; the Overview and Budget show the same month "
     "figure, and a negative one reads \"Over plan\". One-off categories are left out of Spent.", "Planned − Spent"),
    # ------------------------------------------------------------ investments (a period)
    ("cost", "Cost", "What you paid for the units you still hold."),
    ("unrealized_gain", "Unrealized gain", "Gain or loss on units you still hold.", "Holdings value − Cost"),
    ("change_in_unrealized_gain", "Price change on what you hold", "How unrealized gain moved in the period.",
     "Unrealized gain at the end − Unrealized gain at the start"),
    ("realized_gain", "Gain from sales", "Sale proceeds less the cost of the units sold."),
    ("dividends_and_interest", "Dividends and interest", "Distributions and interest received."),
    ("result", "Net gain or loss", "What your investments earned or lost in the period: sales, price changes and payouts.",
     "Gain from sales + Price change on what you hold + Dividends and interest"),
    ("new_money_in", "Money added", "Cash moved into investment accounts from outside, less cash taken out."),
    ("average_cost", "Average cost", "What you paid for each unit you still hold, fees included.", "Cost ÷ Units"),
    ("period_growth", "Growth", "Net gain or loss as a share of what the portfolio started the period with, plus money added.",
     "Net gain or loss ÷ (Portfolio value at the start + Money added)"),
    # ------------------------------------------------------------ cash planning
    ("safe_to_spend", "Safe to spend", "Free cash after what is promised before your next income. An estimate. Budget left to spend and Saving for goals count for every month until that income (only the days before it in the month it lands), so a long gap between pays is covered.",
     "Free cash − Bills and loan payments before next income − Budget left to spend − Saving for goals"),
    ("bills_inside_the_plan", "Bills inside the plan",
     "This month's scheduled bills, due or upcoming, in a category that has a budget. They are part of that budget."),
    ("left_in_plan_after_bills", "Budget left to spend",
     "This month's left in plan less the scheduled bills it already covers, so a bill is never counted twice.",
     "Left in plan − Bills inside the plan"),
    ("payments_before_next_income", "Bills and loan payments before next income",
     "Scheduled bills, subscriptions and loan payments that are not due yet, up to your next income."),
    ("saving_for_goals", "Saving for goals", "What dated reserve goals still need this month, spread over the months left."),
]

P, WYO, CF, BL = ("lightning.planning.position.Position", "lightning.planning.domain.WhatYouOwe",
                  "lightning.reporting.service.CashFlow", "lightning.budgeting.domain.BudgetLine")
INV, FC = "lightning.investments.report", "lightning.planning.forecast.CashForecaster"
_SOURCES = {
    "in_your_accounts": (LEDGER, f"{P}.in_your_accounts"),
    "held_for_others": (LEDGER, "lightning.reporting.service.ReportingService.money_from_others_total"),
    "what_you_own": (LEDGER, "lightning.reporting.service.ReportingService.net_worth"),
    "bank_and_wallet_cash": (LEDGER, f"{P}.bank_and_wallet_cash"),
    "brokerage_cash": (LEDGER, "lightning.reporting.service.ReportingService.owned_brokerage_cash"),
    "cash_you_own": (LEDGER, f"{P}.cash_you_own"),
    "deposits": (LEDGER, f"{P}.deposits"),
    "holdings_value": (LEDGER, f"{P}.holdings_value"),
    "other_you_own": (LEDGER, f"{P}.other_you_own"),
    "reserves": (PLAN, "lightning.reserves.CashReserveService.breakdown_at"),
    "bills_due": (PLAN, f"{WYO}.bills_due"),
    "loans_still_to_pay": (PLAN, f"{WYO}.loans_still_to_pay"),
    "what_you_owe": (PLAN, f"{WYO}.total"),
    "net_worth": (BOTH, f"{P}.net_worth"),
    "free_cash": (BOTH, f"{P}.free_cash"),
    "portfolio_value": (LEDGER, f"{P}.portfolio_value"),
    "holdings_after_sale": (BOTH, f"{P}.holdings_after_sale"),
    "investments_after_sale": (BOTH, f"{P}.investments_after_sale"),
    "if_you_sold_today": (BOTH, f"{P}.if_you_sold_today"),
    "money_in": (LEDGER, f"{CF}.inflows"),
    "money_out": (LEDGER, f"{CF}.outflows"),
    "net_flow": (LEDGER, f"{CF}.net"),
    "savings_rate": (LEDGER, f"{CF}.savings_rate"),
    "opening_balances_in_period": (LEDGER, "lightning.reporting.service.ReportingService.opening_balances_between"),
    "change_in_what_you_own": (LEDGER, "lightning.planning.position.PositionService.change_in_what_you_own"),
    "change_in_net_worth": (BOTH, "lightning.planning.position.PositionService.change_in_net_worth"),
    "investing_rate": (LEDGER, f"{INV}.investing_rate"),
    "average_monthly_income": (LEDGER, "lightning.budgeting.service.BudgetService.income_average"),
    "base_budget": (PLAN, f"{BL}.budget"),
    "carryover": (BOTH, f"{BL}.opening_carryover"),
    "planned": (BOTH, f"{BL}.available"),
    "spent": (LEDGER, f"{BL}.actual"),
    "left_in_plan": (BOTH, f"{BL}.remaining"),
    "cost": (LEDGER, f"{INV}.build_investment_report"),
    "unrealized_gain": (LEDGER, f"{INV}.build_investment_report"),
    "change_in_unrealized_gain": (LEDGER, f"{INV}.investment_period"),
    "realized_gain": (LEDGER, f"{INV}.build_investment_report"),
    "dividends_and_interest": (LEDGER, f"{INV}.build_investment_report"),
    "result": (LEDGER, f"{INV}.investment_period"),
    "new_money_in": (LEDGER, f"{INV}.build_investment_report"),
    "average_cost": (LEDGER, "lightning.investments.domain.Position.average_cost"),
    "period_growth": (LEDGER, f"{INV}.period_growth"),
    "safe_to_spend": (BOTH, f"{FC}._safe_to_spend"),
    "bills_inside_the_plan": (PLAN, f"{FC}.forecast"),
    "left_in_plan_after_bills": (BOTH, "lightning.planning.domain.ForecastMonth.budget_spending"),
    "payments_before_next_income": (PLAN, f"{FC}._safe_to_spend"),
    "saving_for_goals": (PLAN, f"{FC}._goal_need"),
}
FIGURES: dict[str, Figure] = {
    row[0]: Figure(*row, layer=_SOURCES[row[0]][0], function=_SOURCES[row[0]][1]) for row in _TABLE}

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
    "Yours": "what_you_own",
    "Total spending": "money_out", "Net income less spending": "net_flow", "Cashflow": "net_flow",
    "Average monthly salary": "average_monthly_income", "Budgeted": "planned", "Current budget": "planned",
    "Invested capital": "cost", "What you paid in total": "cost",
    "Unrealized gain/loss": "unrealized_gain", "Change in unrealized value": "change_in_unrealized_gain",
    "Realized gain or loss": "realized_gain", "Distributions": "dividends_and_interest",
    "Investment result": "result", "Period result": "result", "Period gain/loss": "result", "Result": "result",
    "Realized gain": "realized_gain", "Change in unrealized gain": "change_in_unrealized_gain",
    "New money in": "new_money_in", "Left in plan after bills": "left_in_plan_after_bills",
    "Deposits and holdings after sale (estimate)": "investments_after_sale",
    "New money added this period": "new_money_in", "Cash added and withdrawn": "new_money_in",
}


def label(key: str) -> str:
    return FIGURES[key].label


def equation(key: str) -> str:
    return FIGURES[key].equation


# Fields on the forms that record values, one name each (layer = where the value is recorded).
FIELDS = [
    ("Date", LEDGER, "The day money moved.", "Date paid, Date received"),
    ("As of", LEDGER, "The day a balance, holding, price or value is true.", "Price date, Statement date"),
    ("Amount", BOTH, "Money moved, in the account's currency. A trade's amount includes fees unless "
     "*Fees are extra* is ticked; a scheduled item's amount is each payment.",
     "Total paid, Total paid / received, Each payment, Total amount received"),
    ("Balance", LEDGER, "An account balance on the As of date.", "Statement closing balance"),
    ("Value", LEDGER, "What a holding or item is worth on the As of date.", "Total item value, Current value"),
    ("Cost", LEDGER, "What you paid in total for units you already hold, fees included.",
     "What you paid in total, Invested capital"),
    ("Units", LEDGER, "Shares, fund units, grams or pieces.", "Quantity, Pieces, Units you hold"),
    ("Account", BOTH, "Where the money moves or the holding sits.", "Held in, Received into, Paid from, Paid into"),
    ("Cash account", LEDGER, "The account that pays or receives the cash for a trade in another account.",
     "Paid from / received into, Money goes to"),
    ("Counterparty", BOTH, "Who you paid or who paid you.", "Paid to, From, Search counterparty"),
    ("Held for", LEDGER, "The person the money or units belong to, if not you.",
     "Whom, Owned by, Owner, Money held for someone else"),
    ("Category", BOTH, "What the money was for.", "Search category"),
    ("Type", BOTH, "The kind of record.", "Kind, Action"),
    ("Name", BOTH, "The record's name.", "Item name"),
    ("Notes", BOTH, "Free text.", "Details"),
    ("Fees", LEDGER, "Fees inside the amount (tick *Fees are extra* when they are not).",
     "Fees included in total, Fees are excluded from the total"),
    ("Due date", PLAN, "When a scheduled payment is due; when adding, the next one; when editing, the first.",
     "Next date, Next payment date"),
    ("Last due date", PLAN, "The last scheduled payment, when a recurring item ends.", "Last date"),
    ("Payments left / Number of payments", PLAN, "How many loan payments; counted from the first due date.", ""),
    ("Amount set aside", PLAN, "Cash assigned to a reserve. It stays in your account.", "Cash reserved, Cash assigned"),
    ("Target amount", PLAN, "What a reserve is saving towards.", ""),
    ("Sale factor", PLAN, "The share of a class's value you expect if you sold today (95% when not set).",
     "Liquidation factor"),
]

MODULES = {
    LEDGER: ("`lightning.accounts`, `lightning.transactions`, `lightning.assets`, investment trades in "
             "`lightning.investments`", "Yes. Every posted transaction."),
    PLAN: ("`lightning.budgeting`, `lightning.reserves`, `lightning.planning` (items, payments, forecast), "
           "sale factors", "No. Recording a payment from the plan posts an ordinary ledger transaction."),
    "Report": ("`lightning.reporting`, `lightning.planning.position`, `lightning.investments.report`, "
               "`lightning.integrity`, every screen in `lightning.ui`", "No. It only reads the other two."),
}


def glossary_markdown() -> str:
    """The Glossary's figures section, generated from this module (see tests/test_figures.py)."""
    short = lambda path: path.removeprefix("lightning.")
    out = ["## Three layers: ledger, plan, report", "",
           "Lightning keeps real money and plans apart, and reports on both:", "",
           "| Layer | What it holds | Where in the code | Moves money? |", "|---|---|---|---|",
           f"| **Ledger** (real money) | {LAYERS[LEDGER]} | {MODULES[LEDGER][0]} | {MODULES[LEDGER][1]} |",
           f"| **Plan** (what-if) | {LAYERS[PLAN]} | {MODULES[PLAN][0]} | {MODULES[PLAN][1]} |",
           f"| **Report** | Reads the ledger and the plan and presents them; stores nothing. | {MODULES['Report'][0]} "
           f"| {MODULES['Report'][1]} |", "",
           "The plan reads the ledger; the report reads both. A plan figure never changes a ledger balance, "
           "and a report figure is always a formula of ledger and plan figures.", "",
           "## Reported figures: one name, one calculation, one function", "",
           "Every figure a screen shows is listed here once. **From** says which layer its inputs come from. "
           "A figure with a calculation is a formula of other figures in these tables and is never computed "
           "a second way; **Function** is the one piece of code that computes it. Screens show the "
           "calculation under the figure.", ""]
    for layer, title in ((LEDGER, "From the ledger — real money"), (PLAN, "From the plan — what-if"),
                         (BOTH, "Ledger + Plan — real money after your plans")):
        out += [f"### {title}", "", "| Figure | Meaning | How it is calculated | Function |", "|---|---|---|---|"]
        for f in FIGURES.values():
            if f.layer == layer:
                calc = f.formula or "Read directly from the " + ("ledger" if layer == LEDGER else "plan")
                out.append(f"| **{f.label}** | {f.meaning} | {calc} | `{short(f.function)}` |")
        out.append("")
    out += ["### Entry-form fields", "", "Forms that record values use the same field names everywhere.", "",
            "| Field | Layer | Meaning | Replaces |", "|---|---|---|---|"]
    out += [f"| **{name}** | {layer} | {meaning} | {old or '—'} |" for name, layer, meaning, old in FIELDS]
    out += ["", "### Retired names", "", "These names no longer appear on screens. Each is now called:", "",
            "| Old name | Now |", "|---|---|"]
    out += [f"| {old} | {FIGURES[key].label} |" for old, key in RETIRED_NAMES.items()]
    return "\n".join(out) + "\n"


START, END = "<!-- figures:start (generated by python -m lightning.core.figures) -->", "<!-- figures:end -->"

if __name__ == "__main__":  # rewrite the generated section of docs/GLOSSARY.md
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "docs" / "GLOSSARY.md"
    text = path.read_text()
    head, rest = text.split(START, 1)
    path.write_text(head + START + "\n" + glossary_markdown() + END + rest.split(END, 1)[1])
