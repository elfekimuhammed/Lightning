# Glossary and taxonomy

Canonical product and technical terms. The product story is in [Project Overview](PROJECT_OVERVIEW.md), calculation contracts in [Architecture](ARCHITECTURE.md), and the visual system in the [Brand guideline](BRAND_GUIDELINE.html). The figures table under "Reported figures" is generated from `lightning/core/figures.py` (`python -m lightning.core.figures`), and `tests/test_figures.py` keeps the two in step: change a figure there, never here.

## Contents

Look up one term with `grep -n -i '<term>' docs/GLOSSARY.md`. Read a whole section only when you add or rename terms in it.

| Section | Holds |
|---|---|
| The basic model | Ledger, accounts, transactions, postings and the other core nouns |
| Device authority | Home node, borrower, checkout, checkpoint and hand-back receipts |
| Three layers: ledger, plan, report | What each layer may do |
| Reported figures: one name, one calculation, one function | Every figure a screen shows, its formula and its function (generated) |
| Category taxonomy (why the activity happened) | L1, L2 and L3 categories |
| Names and identifiers | Names versus codes |
| Asset and account taxonomy (what vs where) | Asset classes and account kinds |
| Transaction and posting types | Every transaction and posting type |

This is Lightning's canonical language for product, database, code, and UI. Use these definitions consistently. The user's visible label is the **Name**; IDs and codes support data integrity and lookup and should not clutter ordinary screens.

## Device authority

| Term | Meaning |
|---|---|
| **Home node** | The device holding the centralized accepted database and deciding which device may write. The phone is the intended default. |
| **Borrower** | A paired device holding temporary write authority for one checkout; initially a PC. |
| **Checkout** | One grant of write authority, identified by a random checkout ID and increasing home epoch. |
| **Checkpoint** | An immutable, verified encrypted database version with an ID and ciphertext hash. The live home file may later change. |
| **Lend** | Home records a grant and becomes read-only before the borrower enables writes. |
| **Hand back** | Borrower freezes its working copy and returns an encrypted candidate for home verification and publication. |
| **Received** | Home durably holds a complete ciphertext candidate; the borrower remains read-only, and home has not resumed writing. |
| **Accepted** | Home has verified and durably published the candidate and issued a durable receipt for its new checkpoint. |

## The basic model

Each term belongs to one layer: **Ledger** (real money that actually moved), **Plan** (what-if; moves no money) or **Report** (read from the other two). See [Three layers](#three-layers-ledger-plan-report).

| Term | Layer | Meaning | Example |
|---|---|---|---|
| **Account** | Ledger | Where value is held. | CIB, Cash wallet, THNDR brokerage |
| **Financial asset** | Ledger | What value is held or counted in an account. Designed as an extensible type so new products can be added without changing the account model. | EGP cash, COMI share, fund unit, CD, gold gram |
| **Asset class** | Ledger | A grouping for financial assets; describes what kind of wealth it is, not where held or why a payment happened. | Funds → Money Market |
| **Exposure** | Ledger | What economic value an asset tracks, separately from its wrapper/class. | Gold fund → Gold exposure |
| **Holding / position** | Ledger | Calculated quantity of one financial asset in one account at a date. | 100 COMI shares in THNDR |
| **Physical item** | Ledger | Individually named tangible asset tracked by piece count, per-piece net gold-bearing weight, karat, cost, and valuation reference. Its item record is not a tickered security. | One Gold ring, 1 piece, 4.2 g of 18K alloy |
| **Net gold weight** | Ledger | Grams of gold-bearing alloy per physical piece, excluding stones and non-gold parts. It is not fine-gold grams unless the item's karat is 24K. | Ring: 4.2 g at 18K |
| **Fine-gold exposure** | Ledger | Pure-gold-equivalent grams derived for allocation/reporting: piece count × net gold grams per piece × karat/24. This reporting measure does not change the item's display weight or reference valuation formula. | 1 × 4.2 g × 18/24 = 3.15 g fine gold |
| **Karat-specific gold price** | Ledger | Price per gram of alloy at the named karat. Multiply by matching-karat net gold weight; never adjust the quote by purity again. | EGP per gram of 18K gold |
| **Acquisition cost** | Ledger | Historical total paid for the item's current acquired quantity; may include workmanship, stones, and fees. Reference-price updates never change it. | 18,000 EGP including workmanship |
| **Manual item valuation** | Ledger | User-entered dated total value for a physical item and its held quantity, used when the shared gold price is unsuitable. | Ring's 2026-09-26 resale estimate |
| **Balance** | Ledger | Calculated value/quantity of an account or position on a date; not an independent user-entered fact. | 12,000 EGP; 100 shares |
| **Activity** | Ledger | The broad reason/kind of a transaction, represented by its category family. It is independent of whether money came in or went out. | Personal, Work, Investment |
| **Category** | Ledger | A label for the activity behind a transaction. Categories do not describe the counterparty, account, or owned asset. | Personal → Food & Groceries |
| **Counterparty** | Ledger | The canonical person, business, institution, or own account on the other side of a transaction. A saved canonical name can have confirmed aliases; close matches are suggestions and require an explicit user decision. | Talabat, employer, CIB |
| **Confirmed alias** | Ledger | User-approved alternative spelling attached to one canonical Counterparty; up to ten per Counterparty. A typo suggestion is not an alias until confirmed. | “Talbat” saved for Talabat |
| **Search suggestion** | Ledger | A ranked possible match shown to help recover from spelling mistakes; it never silently chooses an identity, transfer, category, or custody owner. | “Did you mean Talabat?” |
| **Transaction** | Ledger | A dated user or system event shown in the main ledger. | 450 EGP Talabat payment |
| **Main ledger** | Ledger | The single activity ledger from which account registers, all-transaction view, budget actuals, and reporting are derived. | Register filtered to CIB |
| **Ledger line / journal line** | Ledger | One transaction's effect on a particular account and financial asset. | CIB cash −450 EGP |
| **Owner ID** | Ledger | Optional Counterparty reference on a ledger line (shown as **Held for**); blank means the user owns the value on that line. | Dad owns 2,000 EGP of THNDR cash |
| **Money in / money out** | Ledger | Direction in which value crosses an account boundary. Direction does not determine category. | Salary is money in; grocery purchase is money out |
| **Transfer** | Ledger | Value moved between accounts owned by the user; not income or expense. Selecting an owned account as Counterparty creates both account effects. | CIB → THNDR |
| **Investment trade** | Ledger | Exchange of brokerage cash for asset units (buy) or units for cash (sell). It is recorded inside that brokerage account's register. | Buy 10 fund units |
| **Budget** | Plan | Planned spending amount attached to a category/group and month. Budget limits are not reserve accounts or ledger transactions. | Monthly Food limit |
| **Monthly base budget** | Plan | A tracked category’s monthly plan before any carryover: fixed EGP, a selected percentage of Average monthly income, or an observed-month spending average. Shown as **Base budget**. | Food fixed at 3,000 EGP or 10% of income |
| **Observed-month average** | Plan | Spending average whose 3m/6m window is divided by the distinct months with qualifying recorded activity. Months without activity are not treated as zero and the window is not extended backward. | 12,000 EGP across two observed months in a six-month window = 6,000 EGP |
| **Budget carryover** | Plan | Optional unused spending room added to a later month's limit. It never sets aside cash, creates a transaction, or reduces free cash. | 500 EGP of unused Food limit carried into October |
| **Held for** | Ledger | Who the money or units in the user's account actually belong to, when not the user. Separate from Counterparty: one identifies transaction context, the other identifies beneficial owner/custody. The field is called Held for on every form (formerly Whom / Owned by / Owner). | Dad owns part of THNDR cash |
| **Change ownership** | Ledger | A zero-sum cash entry that reassigns part of one account's balance between the user and one saved person. It changes beneficial ownership, not the account's gross balance. | Set aside 5,000 EGP in CIB for Dad |
| **Expense paid for you** | Ledger | An expense the user chooses to record in their account even though another person paid externally. The categorized, user-owned expense is paired with an equal custody amount for the payer, so gross account cash stays unchanged. | Dad paid 2,500 EGP for groceries; record the expense and mark that cash as Dad's |
| **Reserve** | Plan | A plan assigning some already-owned cash to an emergency fund or future goal. Assignment does not itself move money or change net worth; the actual payment is a normal ledger transaction. | Rent reserve |
| **Emergency fund** | Plan | Permanent, dedicated reserve section. Coverage = Reserves for emergencies ÷ Average monthly income (or ÷ Average monthly spending, if Settings › Budget says so), shown in months. The aim is six. | 13 months of average monthly income |
| **Cash planning** | Plan | The tab for spendable cash and commitments. Sub-tabs: Plan, Recurring, Loans, Reserves. Nothing in it posts to the ledger on its own. | — |
| **Recurring item** | Plan | A bill, subscription or income that repeats on a schedule (weekly, monthly, every 3 months, yearly, or once). | WE Internet · 650 EGP monthly on day 20 |
| **Loan** | Plan | A loan or installment plan, entered as its payments: amount per payment, the next payment date, and payments left. Optional amount borrowed. Each payment counts as spending when paid, in System › Loan payments unless another category is chosen. While that category has no budget rule, its Planned amount each month is the loan payments scheduled that month (shown as *Loan payments scheduled this month*); setting an amount replaces it; paying one lowers cash, spending room and loans still to pay together, so it does not change net worth. | Car loan · 24 × 2,500 EGP from 2026-10-05 |
| **Payment status** | Plan | For each scheduled date: **Paid** (settled by a posted transaction), **Skipped** (the user says it won't happen), **Due** (the date is today or earlier and nothing settled it) or **Upcoming**. Voiding the linked transaction makes it Due again. | Rent · 2026-10-03 · Upcoming |
| **Cash forecast** | Plan | An estimate that carries free cash forward month by month with scheduled payments, separately labelled projected CD proceeds, Left in plan after bills and Saving for goals. A bill in a budgeted category counts inside that budget, never on top. Projected CD principal is a transfer into spendable cash, not income; the forecast never changes net worth or free cash. | 2026-11 ends with 93,220 EGP |
| **CD terms** | Plan | The dates and interest rules for a funded certificate account: start, earliest withdrawal, maturity, principal, annual rate, simple-interest payout or compound capitalization frequency, and destination. Terms forecast cash but never post it. | NBE CD · 18% simple · monthly payout |
| **Earliest withdrawal date** | Plan | First date a CD can be redeemed early; it is not a promised payout. Before this date the CD is not immediately realizable. Maturity is when the normal principal return is projected. | Earliest withdrawal 1 March; maturity 1 September |
| **Sale factor** | Plan | User-selected 0–100% estimate of what one asset class would fetch if sold today; 95% when not set. The same factors feed Holdings after sale on Investments and If you sold today on Overview. A CD with terms uses its class factor as an early-redemption estimate only after its earliest withdrawal date; at maturity its remaining principal uses 100%. It does not change holdings or what you own. Historical scenarios use current settings. Formerly *liquidation factor*. | Gold 90%; CD early redemption 95% |
| **Revaluation** | Ledger | Change in investment value caused by price changes, not deposits, purchases, or withdrawals. | Shares appreciate by 1,000 EGP |
| **Opening adjustment** | Ledger | A holding entered as already owned when tracking began; it establishes a baseline and is not period contribution. | 5,000 EGP cost basis entered on tracking start |
| **Reevaluation ledger** | Ledger | Monthly per-account/per-asset record of units, prices, values, and returns. Its account-level total links to one generated journal transaction in the main ledger. | September COMI return detail linked to one THNDR `VAL` journal |
| **System-generated posting** | Ledger | An auditable ledger transaction created by application rules, not manually entered by the user. | Monthly `VAL` journal |
| **Cost basis / average cost** | Ledger | Remaining units' recorded acquisition cost, including buy fees when fees are included in total. | Remaining shares cost 9,500 EGP |
| **Realized / unrealized return** | Report | Gain/loss from units sold / change in value of units still held. | Sale gain / current paper gain |
| **XIRR** | Report | Annualized money-weighted investment return from dated cash flows and an ending value. A since-inception rate and a selected-period currency return answer different questions; an unavailable result needs an explanation. | Portfolio XIRR since first contribution |
| **Opening balance** | Ledger | A separately dated ledger entry for the account's value at a chosen point. It does not set a minimum date for later-entered activity; users can add earlier transactions at any time. | CIB starts at 50,000 EGP on 1 January; a December transaction may be added later |
| **Void / delete** | Ledger | A recoverable correction that removes a transaction from active balances while retaining history. | Void a duplicate import |
| **Linked (import row)** | Ledger | A statement row tied to a transaction you already recorded, instead of posting it again. It moves no money and changes nothing on the transaction; one row per account per transaction. | The CIB statement's Carrefour −450.00 linked to the purchase entered on the phone |

<!-- figures:start (generated by python -m lightning.core.figures) -->
## Three layers: ledger, plan, report

Lightning keeps real money and plans apart, and reports on both:

| Layer | What it holds | Where in the code | Moves money? |
|---|---|---|---|
| **Ledger** (real money) | Real money: posted transactions and the balances and prices they give. | `lightning.accounts`, `lightning.transactions`, `lightning.assets`, investment trades in `lightning.investments` | Yes. Every posted transaction. |
| **Plan** (what-if) | What-if: budgets, reserves, scheduled bills and loans, sale factors and forecasts. Moves no money. | `lightning.budgeting`, `lightning.reserves`, `lightning.planning` (items, payments, forecast), sale factors | No. Recording a payment from the plan posts an ordinary ledger transaction. |
| **Report** | Reads the ledger and the plan and presents them; stores nothing. | `lightning.reporting`, `lightning.planning.position`, `lightning.investments.report`, `lightning.integrity`, every screen in `lightning.ui` | No. It only reads the other two. |

The plan reads the ledger; the report reads both. A plan figure never changes a ledger balance, and a report figure is always a formula of ledger and plan figures.

## Reported figures: one name, one calculation, one function

Every figure a screen shows is listed here once. **From** says which layer its inputs come from. A figure with a calculation is a formula of other figures in these tables and is never computed a second way; **Function** is the one piece of code that computes it. Screens show the calculation under the figure.

### From the ledger — real money

| Figure | Meaning | How it is calculated | Function |
|---|---|---|---|
| **In your accounts** | Everything in your accounts, including what you hold for other people. | What you own + Held for others | `planning.position.Position.in_your_accounts` |
| **Held for others** | Money and units in your accounts that belong to other people. | Read directly from the ledger | `reporting.service.ReportingService.money_from_others_total` |
| **What you own** | The value of everything in your accounts that is yours. | Cash you own + Holdings value + Other you own | `reporting.service.ReportingService.net_worth` |
| **Bank and wallet cash** | Your cash in bank accounts and wallets. | Read directly from the ledger | `planning.position.Position.bank_and_wallet_cash` |
| **Brokerage cash** | Your uninvested cash inside brokerage accounts. | Read directly from the ledger | `reporting.service.ReportingService.owned_brokerage_cash` |
| **Cash you own** | Your cash in banks, wallets and brokerage accounts. | Bank and wallet cash + Brokerage cash | `planning.position.Position.cash_you_own` |
| **Deposits** | Your certificates and time deposits, at their balance. They are part of Holdings value. | Read directly from the ledger | `planning.position.Position.deposits` |
| **Holdings value** | Everything you own that is not cash, at its latest value: certificates and deposits, stocks, funds, gold and other assets. Assets that are not cash sit under one roof (owner decision 2026-10-04). | Read directly from the ledger | `planning.position.Position.holdings_value` |
| **Other you own** | Anything you own that is neither cash nor a holding. | What you own − Cash you own − Holdings value | `planning.position.Position.other_you_own` |
| **Portfolio value** | Holdings value under the name the Investments tab uses: everything you own that is not cash. Cash waiting in a brokerage account counts in Cash you own (owner decisions 2026-10-04). | Holdings value | `planning.position.Position.portfolio_value` |
| **Money in** | Your posted income in the period. Transfers, trades and money held for others are left out. | Read directly from the ledger | `reporting.service.CashFlow.inflows` |
| **Money out** | Your posted spending in the period, after refunds. Transfers, trades and money held for others are left out. | Read directly from the ledger | `reporting.service.CashFlow.outflows` |
| **Net flow** | What was left of money in after money out. | Money in − Money out | `reporting.service.CashFlow.net` |
| **Savings rate** | The share of money in that you kept. | Net flow ÷ Money in | `reporting.service.CashFlow.savings_rate` |
| **Opening balances in the period** | Money and assets you recorded as already yours (opening balances and existing holdings) during the period. They were yours before, so they are not a change. | Read directly from the ledger | `reporting.service.ReportingService.opening_balances_between` |
| **Change in what you own** | How much what you own grew or shrank in the period. | What you own at the end − What you own the day before the start − Opening balances in the period | `planning.position.PositionService.change_in_what_you_own` |
| **Per month** | A period's money out divided by the calendar months it covers, so a year to date compares with a single month. | Read directly from the ledger | `reporting.spending.spending_profile` |
| **Usual month** | The average money out of the last six whole months before the period. | Read directly from the ledger | `reporting.spending._against_history` |
| **Usual range** | The lowest, middle and highest monthly money out of the twelve whole months before the period. It needs three of them. | Read directly from the ledger | `reporting.spending._against_history` |
| **Investing rate** | The share of money in that you moved into investments, out of what you saved, so it is never more than the savings rate. | Money added ÷ Money in | `investments.report.investing_rate` |
| **Average monthly income** | Income in your chosen income categories, averaged over the last 3 or 6 completed months that had any (Settings › Budget). The budget, reserves and the cash forecast all use it. | Read directly from the ledger | `budgeting.service.BudgetService.income_average` |
| **Average monthly spending** | Money out in your budget categories, leaving out investments and one-off categories, averaged over the same 3 or 6 completed months as Average monthly income. The emergency fund can be counted in it (Settings › Budget). | Read directly from the ledger | `budgeting.service.BudgetService.spending_average` |
| **Spent** | Money out in the category this month. | Read directly from the ledger | `budgeting.domain.BudgetLine.actual` |
| **Cost** | What you paid for the units you still hold. | Read directly from the ledger | `investments.report.build_investment_report` |
| **Unrealized gain** | Gain or loss on units you still hold. | Holdings value − Cost | `investments.report.build_investment_report` |
| **Price change on what you hold** | How unrealized gain moved in the period. | Unrealized gain at the end − Unrealized gain at the start | `investments.report.investment_period` |
| **Gain from sales** | Sale proceeds less the cost of the units sold. | Read directly from the ledger | `investments.report.build_investment_report` |
| **Dividends and interest** | Distributions and interest received. | Read directly from the ledger | `investments.report.build_investment_report` |
| **Net gain or loss** | What your investments earned or lost in the period: sales, price changes and payouts. | Gain from sales + Price change on what you hold + Dividends and interest | `investments.report.investment_period` |
| **Money added** | Cash moved into investment accounts from outside, less cash taken out. | Read directly from the ledger | `investments.report.build_investment_report` |
| **Typical move** | How much a holding's month-end price usually moves in a month: the spread (standard deviation) of its monthly price changes, once there are three. | Read directly from the ledger | `investments.journey.holding_history` |
| **Fall from its high** | How far a holding's month-end price sits below the highest month-end price before it, in percent. | Read directly from the ledger | `investments.journey.holding_history` |
| **Average cost** | What you paid for each unit you still hold, fees included. | Cost ÷ Units | `investments.domain.Position.average_cost` |
| **Growth** | Net gain or loss as a share of what the portfolio started the period with, plus money added. | Net gain or loss ÷ (Portfolio value at the start + Money added) | `investments.report.period_growth` |

### From the plan — what-if

| Figure | Meaning | How it is calculated | Function |
|---|---|---|---|
| **Reserves** | Cash you set aside for emergencies and dated goals, less what linked payments already used. It stays in your accounts and in what you own. | Read directly from the plan | `reserves.CashReserveService.breakdown_at` |
| **Bills due** | Bills, subscriptions and loan payments dated today or earlier that nothing has paid yet. | Read directly from the plan | `planning.domain.WhatYouOwe.bills_due` |
| **Loans still to pay** | Every loan payment not paid yet, due or upcoming. | Read directly from the plan | `planning.domain.WhatYouOwe.loans_still_to_pay` |
| **What you owe** | Payments you are certain to make: bills already due and loans. | Bills due (other than loan payments) + Loans still to pay | `planning.domain.WhatYouOwe.total` |
| **Bills and subscriptions a month** | What your recurring bills and subscriptions come to in a month: a weekly one counts 52 times a year, a yearly one once, a one-off payment not at all. | Read directly from the plan | `planning.health.HealthService.bills_a_month` |
| **Loan payments a month** | What your loan payments come to in a month, counting only loans with payments still to make. | Read directly from the plan | `planning.health.HealthService.loans_a_month` |
| **Base budget** | The amount the budget rule gives: fixed, a share of income or an average. | Read directly from the plan | `budgeting.domain.BudgetLine.budget` |
| **Bills inside the plan** | This month's scheduled bills, due or upcoming, in a category that has a budget. They are part of that budget. | Read directly from the plan | `planning.forecast.CashForecaster.forecast` |
| **Bills and loan payments before next income** | Scheduled bills, subscriptions and loan payments that are not due yet, up to your next income. | Read directly from the plan | `planning.forecast.CashForecaster._safe_to_spend` |
| **Saving for goals** | What dated reserve goals still need this month, spread over the months left. | Read directly from the plan | `planning.forecast.CashForecaster._goal_need` |

### Ledger + Plan — real money after your plans

| Figure | Meaning | How it is calculated | Function |
|---|---|---|---|
| **Net worth** | What you own after what you owe. | What you own − What you owe | `planning.position.Position.net_worth` |
| **Debt to net worth** | What you owe for each pound of net worth. None when net worth is zero or less. | What you owe ÷ Net worth | `planning.health.Ratio.percent` |
| **Debt to cash** | What you owe for each pound of cash you own: could your cash clear it today? | What you owe ÷ Cash you own | `planning.health.Ratio.percent` |
| **Loan payments to income** | The share of your income that goes to loan payments, counting only loans with payments still to make. | Loan payments a month ÷ Average monthly income | `planning.health.Ratio.percent` |
| **Fixed costs to income** | The share of your income already promised to bills, subscriptions and loan payments. | (Bills and subscriptions a month + Loan payments a month) ÷ Average monthly income | `planning.health.Ratio.percent` |
| **Free cash** | Cash you can spend without touching reserves or leaving a bill unpaid. | Cash you own − Reserves − Bills due | `planning.position.Position.free_cash` |
| **Holdings after sale (estimate)** | What your holdings, deposits included, might fetch if sold or cashed in today, after each class's sale factor. CDs before their earliest withdrawal count 0; early-redeemable CDs count their balance × the CD sale factor; matured CDs count their balance. | Σ Holdings value of each class × its sale factor | `planning.position.Position.holdings_after_sale` |
| **If you sold today (estimate)** | Free cash plus what your holdings might fetch. | Free cash + Holdings after sale (estimate) | `planning.position.Position.if_you_sold_today` |
| **Change in net worth** | How much net worth grew or shrank in the period. | Net worth at the end − Net worth the day before the start − Opening balances in the period | `planning.position.PositionService.change_in_net_worth` |
| **Carryover** | Unused plan from last month, added to this month when carryover is on. | Left in plan last month | `budgeting.domain.BudgetLine.opening_carryover` |
| **Planned** | What you plan to spend this month. The month's total also counts background estimates for untracked categories; one from a single month of spending is low confidence and shows a "!" that says why. | Base budget + Carryover | `budgeting.domain.BudgetLine.available` |
| **Left in plan** | What is left of the plan; the Overview and Budget show the same month figure, and a negative one reads "Over plan". One-off categories are left out of Spent. | Planned − Spent | `budgeting.domain.BudgetLine.remaining` |
| **Safe to spend** | Free cash after what is promised before your next income. An estimate. Budget left to spend and Saving for goals count for every month until that income (only the days before it in the month it lands), so a long gap between pays is covered. | Free cash − Bills and loan payments before next income − Budget left to spend − Saving for goals | `planning.forecast.CashForecaster._safe_to_spend` |
| **Budget left to spend** | This month's left in plan less the scheduled bills it already covers, so a bill is never counted twice. | Left in plan − Bills inside the plan | `planning.domain.ForecastMonth.budget_spending` |

### Entry-form fields

Forms that record values use the same field names everywhere.

| Field | Layer | Meaning | Replaces |
|---|---|---|---|
| **Date** | Ledger | The day money moved. | Date paid, Date received |
| **As of** | Ledger | The day a balance, holding, price or value is true. | Price date, Statement date |
| **Amount** | Ledger + Plan | Money moved, in the account's currency. A trade's amount includes fees unless *Fees are extra* is ticked; a scheduled item's amount is each payment. | Total paid, Total paid / received, Each payment, Total amount received |
| **Balance** | Ledger | An account balance on the As of date. | Statement closing balance |
| **Value** | Ledger | What a holding or item is worth on the As of date. | Total item value, Current value |
| **Cost** | Ledger | What you paid in total for units you already hold, fees included. | What you paid in total, Invested capital |
| **Units** | Ledger | Shares, fund units, grams or pieces. | Quantity, Pieces, Units you hold |
| **Account** | Ledger + Plan | Where the money moves or the holding sits. | Held in, Received into, Paid from, Paid into |
| **Cash account** | Ledger | The account that pays or receives the cash for a trade in another account. | Paid from / received into, Money goes to |
| **Counterparty** | Ledger + Plan | Who you paid or who paid you. | Paid to, From, Search counterparty |
| **Held for** | Ledger | The person the money or units belong to, if not you. | Whom, Owned by, Owner, Money held for someone else |
| **Category** | Ledger + Plan | What the money was for. | Search category |
| **Type** | Ledger + Plan | The kind of record. | Kind, Action |
| **Name** | Ledger + Plan | The record's name. | Item name |
| **Notes** | Ledger + Plan | Free text. | Details |
| **Fees** | Ledger | Fees inside the amount (tick *Fees are extra* when they are not). | Fees included in total, Fees are excluded from the total |
| **Due date** | Plan | When a scheduled payment is due; when adding, the next one; when editing, the first. | Next date, Next payment date |
| **Last due date** | Plan | The last scheduled payment, when a recurring item ends. | Last date |
| **Payments left / Number of payments** | Plan | How many loan payments; counted from the first due date. | — |
| **Amount set aside** | Plan | Cash assigned to a reserve. It stays in your account. | Cash reserved, Cash assigned |
| **Target amount** | Plan | What a reserve is saving towards. | — |
| **Sale factor** | Plan | The share of a class's value you expect if you sold today (95% when not set). | Liquidation factor |

### Retired names

These names no longer appear on screens. Each is now called:

| Old name | Now |
|---|---|
| All accounts | In your accounts |
| Gross balances | In your accounts |
| Money from others | Held for others |
| Cash held for others | Held for others |
| Owned value | What you own |
| Owned net worth | What you own |
| What I own | What you own |
| Liquid cash | Cash you own |
| Owned liquid cash | Cash you own |
| Investment cash | Brokerage cash |
| Investments and deposits | Deposits |
| Investment holdings | Holdings value |
| Current owned value | Holdings value |
| Other owned assets | Other you own |
| Assigned reserves | Reserves |
| Assigned to reserves | Reserves |
| Cash reserved | Reserves |
| Estimated liquid investments | Holdings after sale (estimate) |
| Estimated cash after sale | Holdings after sale (estimate) |
| Estimated available value | If you sold today (estimate) |
| Yours | What you own |
| Total spending | Money out |
| Net income less spending | Net flow |
| Cashflow | Net flow |
| Average monthly salary | Average monthly income |
| Budgeted | Planned |
| Current budget | Planned |
| Invested capital | Cost |
| What you paid in total | Cost |
| Unrealized gain/loss | Unrealized gain |
| Change in unrealized value | Price change on what you hold |
| Realized gain or loss | Gain from sales |
| Distributions | Dividends and interest |
| Investment result | Net gain or loss |
| Period result | Net gain or loss |
| Period gain/loss | Net gain or loss |
| Result | Net gain or loss |
| Realized gain | Gain from sales |
| Change in unrealized gain | Price change on what you hold |
| New money in | Money added |
| Left in plan after bills | Budget left to spend |
| Deposits and holdings after sale (estimate) | Holdings after sale (estimate) |
| Investments if sold (estimate) | Holdings after sale (estimate) |
| New money added this period | Money added |
| Cash added and withdrawn | Money added |
<!-- figures:end -->

## Category taxonomy (why the activity happened)

There are three levels in the model, but only two are used now:

- **L1 — Activity family:** Personal · Work · Investment.
- **L2 — Broad category:** the simple, useful analysis bucket within one family.
- **L3 — Detail:** intentionally unused/empty for now. Do not prepopulate it; add only when a user chooses to track more detail.

Examples: `Personal → Food & Groceries`, `Work → Salary`, `Investment → Dividends`. Categories are not divided into income and expense trees: choose the activity that explains the event regardless of sign. For example, a refund should retain the original activity category. Counterparty defaults may suggest a category (Talabat → Personal / Food & Groceries), but the user can choose another.

Categories are selected from an explicit list, not silently created by typing. Names are sorted alphabetically within their parent. A category with historical use cannot be physically deleted; it is archived. Archived categories remain legible on old transactions but cannot be selected for new ones. Names should be unique among siblings; the same broad term may exist under different L1 families when meaning differs (e.g., Transportation under Personal and Work).

## Names and identifiers

| Term | Rule | Example |
|---|---|---|
| **Name** | Human-readable label shown in ordinary app screens. Account codes never appear under account names in normal UI. Canonical Counterparty names are unique; other taxonomy names may repeat under different parents. | CIB; Talabat; Food & Groceries |
| **Code** | Stable machine-friendly identifier for relationships, imports, and technical search. It is not the display name and should not appear in ordinary account UI. | `STK:COMI` |
| **ID** | Internal database key; not meaningful to a person and never displayed. | `account_id = 12` |
| **Ticker / symbol** | Public exchange/provider symbol used to find an instrument. It is not Lightning's code or database ID. | `COMI` |
| **ISIN** | Optional global security identifier, useful for source matching; ordinary users need not know or enter it. | Egyptian security ISIN |
| **Unit** | What is counted for an asset. | EGP, share, fund unit, gram |
| **Transaction reference (ref)** | Fixed human-readable ID assigned to a transaction. It does not change if its date is edited and has no account prefix because transfers can touch two accounts. | `OUT-2026-09-25-003` |
| **Ledger-line reference** | A transaction ref plus its line number. | `TRF-2026-09-26-001/2` |
| **Date input** | Accepts ISO (`2026-01-31`), day/month/year (`31/1/2026`), or day/month (`31/1`, current year); stored canonically as ISO. Ambiguous numeric dates are interpreted day-first. | `31/1` → `2026-01-31` in 2026 |
| **Amount input** | Accepts a number (`1,250.50`, Arabic-Indic digits) or a sum with + - * / ^ and round brackets. Order: brackets, then ^, then * and /, then + and -, left to right; a bracket after a number or a bracket multiplies. Anything unclear is refused with the reason (`-2^2`, `2^3^2`, `8/2(2+2)`, a sign too many or too few, an uneven division, %, a date). The window shows the result before saving. | `3+5*8` → 43; `2(3+5)` → 16 |
| **Tag** | A #word in a transaction's notes: letters, digits, - or _, with at least one letter; case does not matter. A note shows it as a link to every transaction carrying it, headed with their count, Money in and Money out. Typing it in a register's search is the same exact filter. | `#Eid` and `#eid` are one tag; `#eid2026` is another; `invoice #4521` has none |

## Asset and account taxonomy (what vs where)

Financial assets can include currency/cash, stocks, funds, physical gold, deposits/CDs, and future supported asset kinds. Asset class and exposure are separate dimensions: a gold fund is a Fund by wrapper/class but has Gold exposure. Account types describe location/container, for example cash wallet, bank account, deposit account, brokerage, physical-asset location, and other asset account. A brokerage may contain both its cash balance and many investment holdings.

Example internal-code patterns (for data/search, not routine UI labels):

- Account: `INSTITUTION-TYPE-CURRENCY`, e.g. `THNDR-BRK-EGP`.
- Financial asset: `CLASS:SYMBOL`, e.g. `CASH:EGP`, `STK:COMI`, `FND:AZG`, `GLD:21K`.
- Category/asset-class path: dotted tree code; nesting in the UI is by parent, not repeated breadcrumb text on every child.

## Transaction and posting types

`OPN` opening · `IN` inflow · `OUT` outflow · `TRF` internal-account transfer · `BUY` investment buy · `SEL` sell · `DIV` dividend · `VAL` system-generated valuation · `ADJ` reconciliation adjustment · `CNV` conversion (future/multi-currency use).

An investment overview is a filtered/calculated view, not a separate place for buy/sell/dividend entry: those transactions are entered within the brokerage account register. Monthly return details live in the reevaluation ledger; one aggregate per affected account is journaled in the main ledger for reconciliation.
