# Architecture

**Last updated 2026-10-02 · app 0.4.0b1** (`lightning/__init__.py`, matched by `pyproject.toml`).

This file holds the technical side: stack, module boundaries, data model and every calculation contract. The product story is in [Project Overview](PROJECT_OVERVIEW.md), the visual system in the [Brand guideline](BRAND_GUIDELINE.html), and term definitions in the [Glossary](GLOSSARY.md).

Lightning is a local-first, single-user **modular monolith**: one Python process, one SQLite database, and a server-rendered browser UI. The architecture puts correctness first, then clear ownership of data, then adding new financial-asset types without duplicating transaction logic.

## Stack and local operation

| Area | Choice |
|---|---|
| Runtime | Python 3.11+, FastAPI, Uvicorn |
| UI | Jinja2 server-rendered HTML, vanilla JS/CSS; no frontend build |
| Persistence | One local SQLite file in `data/`, ordered SQL migrations, local backups |
| Financial precision | `Decimal` in Python, scaled integers (`_e6`) in SQLite; no binary floats in financial logic |
| Quality | pytest and `import-linter` boundaries |
| Network | Local-only server bound to `127.0.0.1` |

On Linux run `./run.sh`, then open `http://127.0.0.1:8765` in Firefox. Startup takes a backup, runs migrations and processes due valuation checkpoints. Keep the process running while you use the app; stopping it deletes nothing. `python -m lightning --demo` opens the sample household (`lightning/demo.py`) in a separate `data/demo.db` on port 8766. It is rebuilt on every start and entered through the same services as the screens.

## Three layers: ledger, plan, report

The product has three layers. They are separate from the import layers below: they describe what the data *is*, not which package may import which.

| Layer | Holds | Modules | Moves money? |
|---|---|---|---|
| **Ledger** (real money) | Accounts, posted transactions and their ledger lines, prices and valuations, custody (held for others) | `accounts`, `transactions`, `assets`, trades in `investments`, `money_from_others`, `physical_items` | Yes. Only `TransactionService` writes postings. |
| **Plan** (what-if) | Budget rules and carryover, reserves (amounts set aside), planned items and their payments, sale factors, the cash forecast | `budgeting`, `reserves`, `planning` | No. A plan never changes a ledger balance. "Record and mark paid" posts an ordinary transaction through `TransactionService`, and the plan then links to it. |
| **Report** | Nothing of its own: figures computed on read from the ledger and the plan | `reporting`, `planning.position` (`PositionService`), `investments.report`, `integrity`, `ui` | No. |

Rules:

- **Real money is only what the ledger says.** Cash you own, holdings value, money in and out, and investment results are ledger figures. A budget, a reserve, a scheduled bill or a forecast never appears in them.
- **A plan figure is labelled as one.** What you owe, reserves, planned amounts, safe to spend, the forecast and every "(estimate)" figure come from the plan, alone or combined with the ledger.
- **Report figures are formulas of the other two.** Each figure has one name, one formula and one function, listed in `lightning/core/figures.py` with its layer (Ledger, Plan, or Ledger + Plan). The Glossary's figure tables are generated from that file (`python -m lightning.core.figures`), and `tests/test_figures.py` checks that they match and that every named function exists.
- **Routes never compute figures.** A screen calls the function named in the registry; for example the Overview reads `PositionService.at`, `CashFlow.savings_rate`, `PositionService.change_in_what_you_own`, `investment_period` and `results_by_asset`.

## Runtime and dependency direction

```
ui/                   FastAPI routes, Jinja templates, small vanilla JS/CSS
  ↓                   calls application services; no SQL or financial calculations
workflows/            transactional use-cases spanning modules
planning/             cash planning: recurring items, loans, what you owe, cash forecast (read-only)
domain services/      accounts, assets, categories, transactions, investments, deposits, budgeting
reporting/            read-only queries and derived views (net worth, budgets, the Overview)
database/             SQLite, migrations, seed data, backup, settings, audit
core/                 dates, money, identifiers, posting rules; no app dependencies
```

`bootstrap.py` is the composition root. Cross-module operations call public services, not another module's repository. Import boundaries and UI restrictions are checked by `import-linter`/tests. Transaction posting is centralized in `TransactionService`; other modules build validated postings and ask it to write them.

## Modules

| Package/module | Responsibility |
|---|---|
| `lightning/core` | Money/date parsing, refs/codes, errors, posting rules; `figures.py` names every figure with its formula, layer and function |
| `lightning/database` | Connection, migrations, seed, backups, audit, settings |
| `lightning/accounts` + `workflows/accounts.py` | Account rules and atomic account/opening-balance workflows |
| `lightning/assets` | Asset classes, financial assets, local EGX catalogue, prices and quote adapters |
| `lightning/categories` | Activity taxonomy and archived/pickable category rules |
| `lightning/counterparties.py` | Canonical names, aliases, match suggestions and defaults |
| `lightning/transactions` | Main-ledger posting, editing, voiding, search; the only writer of postings |
| `lightning/investments` + `reevaluations.py` | Trades, positions, investment calculations and valuation checkpoints |
| `lightning/deposits` | Certificate terms and read-only interest/payout projections; principal and actual payments remain in the ledger |
| `lightning/money_from_others.py` | Custody attribution for money and units held for others |
| `lightning/bank_imports.py` + `reconciliation.py` | Staged CSV review and posting; checking an account against the bank's balance (a small difference posts one IN/OUT balance adjustment) |
| `lightning/budgeting` + `reserves.py` | Spending plans and cash reserves (separate concepts) |
| `lightning/planning` | Recurring items, loans, payments, what you owe, cash forecast; `position.py` computes every position figure once |
| `lightning/reporting` + `integrity` | Read-only queries, derived reporting and data checks |
| `lightning/workflows` | Atomic cross-module use-cases |
| `lightning/ui` | Routes, templates, static assets. `charts.py` (chart geometry), `visuals.py` (chart data read from services) and `keynotes.py` (each page's key notes) never compute a financial figure |
| `lightning/demo.py` | The sample household |

## One main ledger; one linked valuation ledger

The main ledger is the source of truth for user-recorded activity. Account registers, all-transactions, budgets, net worth, investment positions, and analysis are views or calculations over it—not separate competing transaction stores.

```
transactions (documents) ──1:n──▶ ledger_entries (account + asset effects)
                                           ▲
reevaluation_entries ──many:one── reevaluation period ──1:1 per account──▶ VAL journal in main ledger
```

The reevaluation ledger stores per-asset, per-account month-end units, price, value, and return, plus missing-price state. It links every detail row to the one aggregated system-generated `VAL` journal per account and checkpoint in the main ledger. It never copies ordinary transactions into a second activity ledger. Sale dates force a checkpoint at the sale price; monthly checkpoints fill elapsed month-ends on app startup. If a historical price is unavailable, the checkpoint remains pending for user input rather than silently using cost as a market quote.

### Physical gold item contract

- An item row is an individually named thing in one `PHYSICAL_ASSET` account; its quantity is a count of pieces (for example, one ring is `1 piece`). No ticker or ISIN is required.
- `net_gold_grams_per_piece` is the grams of gold-bearing alloy in one piece, excluding stones and other non-gold parts. The karat describes that alloy's fineness (18K = 18/24 fine gold); the number is not itself another multiplier in a gold-price valuation.
- `acquisition_cost` is the recorded total paid for the item's current acquired pieces, including any workmanship, stones, and purchase fees when known. It is historical cost and never changes when market/reference prices change.
- A shared reference asset represents price per gram for a specific karat, in account currency; for example `GLD:18K` is EGP per gram of 18K gold. The reference must match the item's karat. Estimated metal value is `piece_count × net_gold_grams_per_piece × dated_price_per_gram`. Do not multiply by `karat/24` again. Fine-gold exposure is reported separately as `piece_count × grams_per_piece × karat/24`.
- Stones and workmanship have no automatic resale value in the melt estimate. They may be described in item details and are reflected only in acquisition cost unless the user enters a manual dated total-item valuation.
- An item-specific manual valuation is a dated total value for the currently held item quantity and takes precedence over the reference-price estimate on or before that date. It is labeled `Manual`; a reference-price estimate is labeled with its source and price date; cost fallback is labeled `At cost`; missing value remains explicitly unavailable.
- Item metadata edits (name, kind, details) do not post ledger activity. Weight or karat edits change the current reference-based estimate, but do not rewrite historical cash transactions or acquisition cost; the audit log records before/after values. Past manual item valuations remain dated facts and do not silently change.
- Purchases and sales use normal `BUY`/`SEL` transactions with the item's piece count and associated gold weight kept distinct from cash paid/received. Purchase workmanship and fees remain part of cash paid/acquisition cost, not gold grams. The held piece count cannot fall below zero. Purchase itself exchanges cash for an asset and does not create income/expense or unexplained owned-wealth change.
- Physical-item values enter the owning account and existing Gold allocation/report path exactly once. Existing fungible, gram-based gold ledger positions remain untouched and continue using their recorded units and asset purity/price rules.

| Activity | Main-ledger effect |
|---|---|
| Expense 450 | Account cash −450, `OUTFLOW`, category chosen by activity |
| CIB → THNDR transfer | CIB −10,000 and THNDR +10,000, both `INTERNAL` |
| Investment buy | Brokerage cash decreases; owned asset units and cost increase; net effect is internal |
| Money held for Dad | Cash still enters the named account; custody attribution reduces the user's owned share/net worth |
| Month-end return | Per-holding detail in reevaluation ledger; one account-level `VAL` journal in main ledger |

Core posting invariants: internal lines net to zero; external inflows/outflows have an activity category; a sale cannot take an owner's position below zero; voided entries remain auditable but do not contribute to balances. `ledger_entries.owner_id` is nullable: null means user-owned, otherwise the referenced Counterparty owns that line. Transactions carry the selected owner across their cash and asset lines. Dated cash and holding balances are checked per account, asset, and owner when posting or editing. Cash can be reassigned between the user and one saved person inside one account by a zero-sum `ADJ` posting; the transaction service checks both dated ownership balances. If another person paid an expense externally, the `ADJ` contains a user-owned categorized outflow plus an equal payer-owned custody inflow. Gross account cash is unchanged, while user-owned cash and expense analysis decrease/increase respectively. The expense line remains eligible for budget, reserve, and planned-payment matching. These entries are identified by the `Ownership:` description prefix and are not ordinary income, expense or transfer totals except for the explicit expense line.

Brokerage buys must use cash in the same brokerage account as the purchased holding. The purchase's owner must have enough brokerage cash on the trade date; cash in another owner's share cannot cover the buy.

CD purchases use a different boundary: a `DEPOSIT` account is a bank-specific certificate portfolio identified by its Institution field. It cannot receive or hold cash. Each certificate is a separate non-cash `DEPOSIT.CD` financial asset with its own name and terms. A `BUY` transaction links that asset to its portfolio and debits the bank/cash account the user selects. Portfolio membership comes from the explicit account relationship; do not infer it from matching institution text.

## Data ownership and derived values

- **Where:** `accounts` are cash wallets, bank accounts, CD portfolios, brokerages, physical-asset locations, or other supported locations. A CD portfolio is a `DEPOSIT` account whose Institution identifies its bank; it holds no cash.
- **What:** `financial_assets` and `asset_classes` represent cash, stocks, funds, gold, individual CDs, and future asset kinds. A brokerage can hold cash and multiple assets; a CD portfolio groups multiple non-cash CDs issued by one bank.
- **Why:** `categories` label transaction activity: L1 is Personal, Work, or Investment; L2 is broad; L3 is intentionally unused until users need it.
- **Who:** `counterparties` are canonical people, businesses, institutions, and optional beneficial owners on ledger lines. The transaction's `Whom` choice is copied to its cash and asset lines.
- **Balances and analytics:** holdings, cash balances, budget actuals, ownership shares, gains, and net worth are calculated from posted ledger effects, owner IDs, and dated prices.

The read-only Integrity checks compare gross account values with asset-class reports, verify `owned net worth + money held for others = gross account values` overall and per account, compare categorized outflows with reported spending and budget actuals, verify reserves against owned liquid cash, and close the month-to-date net-worth bridge. Missing valuations mark affected comparisons incomplete rather than green. These checks diagnose report/subledger mismatches; they never adjust posted entries.

IDs are internal relational keys. Stable refs identify transactions; readable codes identify master records internally and for imports/search. Ordinary screens show names, not account codes. Source CSV spellings are retained during review; possible Counterparty matches are suggestions, never silent merges. Users can correct fields inline and post rows with safe incomplete metadata.

## Position and reporting contract

### Investment report contract (2026-09-28)

The Investments report uses posted, non-void main-ledger entries dated by transaction date. It scopes every calculation to `owner_id IS NULL` and keeps cost lots keyed by owner, account, and asset; an opening (`OPN`) holding is a baseline adjustment and never new money. The portfolio boundary includes investment holdings and cash in brokerage, physical-asset, and other investment accounts. Investment-account cash transfers and trades net internally; direct physical purchases/sales count only their portfolio-side holding change. Dividends are distributions, not contributions. Valuation checkpoint rows (`return_base_e6`) and aggregate `VAL` journals are reconciliation data and are excluded from return.

For a selected interval, new money is the positive posted change across that boundary and withdrawals are the absolute negative change. Money added is their difference. Gain from sales is net sale proceeds less average cost removed, with basis per owner/account/asset; purchase costs and net sale proceeds already include fees. Distributions use the cash actually posted. Price change on what you hold is the end balance less the balance immediately before the interval. Net gain or loss adds gain from sales, price change, distributions, and any separately identified FX/cost effects once. No balancing `other return` is permitted. If historical prices/ownership are missing, report the result unavailable.

At the as-of date, cost of holdings still owned is remaining basis; holdings value is units times a dated confirmed valuation; unrealized gain is value less remaining basis. Brokerage cash is owned cash in investment accounts. Holdings after sale (estimate) comes from the shared position (see below), not the investment report. Before an asset has any typed or trade price, it is valued at its remaining cost (no gain yet) and listed in the report's `at_cost` notices; this keeps Net gain or loss available and consistent with the per-class breakdown. A missing price after that point still makes Net gain or loss unavailable. Dividend asset attribution is stored in `investment_dividend_assets`; legacy memo attribution is migrated only when it uniquely matches an asset code, otherwise the dividend remains unresolved while its cash amount is retained. Fiscal-year dates are unconfigured, so YTD is labeled Calendar 2026.

- **Position figures** (What you own, Cash you own, Deposits, Holdings value, Reserves, Bills due, What you owe, Net worth, Free cash, Portfolio value, Holdings after sale, If you sold today) are computed once by `PositionService.at(date)` in `lightning/planning/position.py`. Base values are read from reporting, reserves and planning; every other figure is a property that composes them (for example `free_cash = cash_you_own − reserves − bills_due`). Routes and templates read the `Position`; they never re-add balances. Names, meanings and formulas come from `lightning/core/figures.py` and match the Glossary.
- **Sale factors:** each asset class's 0–100% factor (95% when unset, `investments.domain.DEFAULT_SALE_FACTOR`). Holdings after sale = Σ holdings value × factor; Investments if sold (estimate) adds deposits × factor; If you sold today = Free cash + that. This is a scenario using current settings, not a sale quote or a booked loss.
- **Average monthly income:** `BudgetService.income_average(month)` is the only income average. It covers the chosen income categories over the last 3 or 6 completed months that had income, or a manual amount. A posted recurring-income transaction explicitly linked to a scheduled payment is attributed to that payment's due month for this average, while cash-flow reports retain the bank-posting date; unlinked income stays in its bank month. Budget percentages, emergency-fund coverage and the cash forecast all read it.
- **Period income/spending:** posted external activity in the selected date range. Internal transfers and investment purchases are not income or expense; refunds reduce their original expense category. Custody activity is excluded from owned analysis.
- **Investment return:** remaining holdings' market value less remaining cost, plus gains from sales and dividends. The current portfolio and management XIRR must not be assumed owned-only until historical custody cash flows are verified.

The Overview and the reports share the date-range parser (Birdview was folded into the Overview on 2026-09-30; `/birdview` redirects there, and Expense analysis keeps its `/birdview/expenses` address). Positions are valued at the selected range end; expense and flow views use the selected interval. Asset-class weights divide by owned investment value and exclude cash and custody. A missing valuation is disclosed and an unavailable reserve history makes free cash and If you sold today unavailable. Historical after-sale estimates use current sale factors.

### Wealth history and performance

The four horizons apply consistently to flow, expense, and position views; the position and reserve assignments are as of the range end. Internal transfers and investment purchases are excluded from cash-flow totals. Expense categories roll up consistently across the ranked overview, L1/L2 analysis, and linked transactions. Wealth movement remains distinct from investment return.

XIRR is an annualized money-weighted rate using dated investment cash flows and an ending value. Since-inception XIRR is a separate measure from the selected period's currency return. A period-specific XIRR needs an opening valuation as an initial cash flow. If dates, flows, or ending value are inadequate, show an unavailable reason rather than 0%. Build owned-only cash flows before showing XIRR on the Overview; missing prices must not become invented historical quotes.

**Reporting read performance.** `ReportingService.holdings()` batches account, asset and asset-class metadata once per invocation; `build_investment_report()` likewise loads account and asset metadata once per report call. These maps are request-local, not shared across requests, so there is no stale-data invalidation path after a ledger edit or profile switch. The 319-transfer synthetic report uses six SQL reads, compared with 641 asset point-lookups in the former per-ledger-row pattern. This reduced row-proportional query work; the request cache below removed the page-level repeats.

**Request cache** (`lightning/core/memo.py`, added 2026-10-03). A page asks for the same figure many times: the Overview's position at several dates, every account's share of one ledger scan, the same month's spending for every budget line. `ui/web.py` wraps every request in `request_cache(container.db)`. A read decorated with `@request_cached` then computes each distinct call once per request. Outside a request (tests, workflows, startup), nothing is cached. The rules that keep it safe:

- **One request only:** nothing survives to the next click, so a save, an import, a profile switch or midnight can never show an old figure.
- **Any write empties it:** the memo compares SQLite's `total_changes` on the connection, so a write anywhere in the request, through any service, drops every cached value.
- **Never inside a transaction:** while `conn.in_transaction` is true the memo neither serves nor stores, so a rolled-back write leaves nothing behind and a workflow always reads its own writes.
- **Callers get copies:** cached lists, dicts and tuples come back copied (`deep=True` for the investment report, whose dict callers extend), so a caller that edits its result cannot change the next one.
- **What is cached:** pure reads only, with hashable arguments and dates normalised to `yyyy-mm-dd`: `ReportingService` holdings, net worth, custody by account, held-for-others value, brokerage cash by account, money out by category and first activity date; `PositionService.at`; `build_investment_report`; category tree and look-ups by id; asset classes and assets; accounts. `get(id)` on categories, assets and accounts reads from one cached map per request instead of one query per row.
- **Guard:** `tests/test_reporting_performance.py` loads Omar's 2026 plus two earlier years and checks, per main tab, a ceiling on SELECT statements. Without the cache every tab is far over it (1,100–7,100 statements). The test also checks that every tab renders byte-identical HTML with and without the cache.

**Page speed (2026-10-03, from source).** Server time per tab, median of three, on a 4-vCPU 2.1 GHz container, for a 2,239-transaction ledger (Omar's 2026 plus five earlier years). "Enc." is SQLCipher keyed as `Database.conn` keys it. The WebView2/Chromium window adds about 250–400 ms per page at 4× CPU throttle.

| Tab | Before | After | Enc. before | Enc. after |
|---|---:|---:|---:|---:|
| Overview | 507 ms | 163 ms | 962 ms | 237 ms |
| Budget, All time (the period is remembered) | 4,597 ms | 326 ms | 6,994 ms | 406 ms |
| Account register | 180 ms | 55 ms | 479 ms | 239 ms |
| All transactions | 217 ms | 80 ms | 677 ms | 305 ms |
| Investments | 360 ms | 181 ms | 520 ms | 277 ms |
| Expense analysis, All time | 461 ms | 297 ms | 921 ms | 368 ms |

SELECT statements fell from 5,198 to 785 on the Overview, from 9,948 to 1,256 on Budget › All time and from 14,750 to 854 on Expense analysis › All time. The same crawl of 700 pages produced identical HTML with and without the cache.

Also done: `Valuer` checks for the `physical_items` table once instead of on every valuation (639 checks per Overview). The profile `Guard` lets the window keep `/static/` files (`Cache-Control: private, max-age=86400`) while pages stay `no-store`; each launch has a new random port, so a cached file never outlives its launch. The logo is 96 px (5.8 KB) instead of 1,254 px (513 KB).

Still open:

- **`PRAGMA cipher_memory_security = ON`** makes ledger scans 3.2× slower (555 µs vs 173 µs for a full `GROUP BY`) and stays on for the whole process. With it off, the encrypted register and All transactions take about 85 ms instead of 250–320 ms. Turning it off is an owner decision.
- **Registers still read the whole matching history to show 50 rows** (`ReportingService.register` → `_rows`). Row look-ups now come from the request cache; the next step is to read only the page's rows, with the running balance from SQL.
- **Smaller:** legacy browser mode's Google Fonts stylesheet in `base.html` blocks rendering (about 240 ms online, longer offline); routes are `async def` with synchronous database work, so one slow page blocks other requests; the live database uses the rollback journal (`DELETE`, synchronous `FULL`).
- **A cache between clicks** (keyed by a database-wide write counter and `today()`) is not needed at these speeds.

## Cash planning contract

`lightning/planning/` owns planned items (`planned_items`) and their settled payments (`planned_payments`). It reads the ledger, budget and reserves through their services and never posts on its own; recording a payment goes through `TransactionService` like any other entry.

Loan budget lines are derived, not stored: `BudgetService.amounts_for` asks `PlanningService.loan_payments_by_category(month)` (wired in `bootstrap.py`, so budgeting never imports planning) and plans a category with no rule of its own at the loan payments scheduled that month (paid, due or upcoming; not skipped). A rule the user sets wins. `has_plan` ignores these lines, so a loan alone does not count as having made a plan.

- **Items.** A planned item is a bill, subscription, income or loan with an amount per payment and a schedule: frequency (once, weekly, monthly, every 3 months, yearly) every N periods from a first date, optionally ending at a last date or after a number of payments. Monthly-type dates keep the first date's day, clamped to the month's last day. Loans must have a number of payments or a last date.
- **Payment status.** Each scheduled date is Paid (linked to a posted transaction), Skipped, Due (on or before today, not settled) or Upcoming. A voided linked transaction makes the payment Due again. A transaction settles at most one payment.
- **Matching.** A posted, owned money-out (money-in for income) transaction settles a payment automatically when it is the only candidate within 7 days of the date, on the item's account if set, matching its counterparty or category, within 10% of the amount (1% for loans). A plausible but non-strict match (up to 45 days and 50% amount difference) is shown for explicit confirmation, including before the due date; it never settles itself. A confirmed link stores the transaction's actual amount, not the old planned amount. Ambiguous candidates stay separate choices. A changed amount prompts, but never automatically updates, later payments and a related reserve target.
- **What you owe** = bills due + loans still to pay, each payment once. **Bills due** are Due bills, subscriptions and loan payments; **loans still to pay** are every unpaid loan payment. **Net worth** = what you own − what you owe. **Free cash** = owned liquid cash − effective reserves − bills due. The Integrity check verifies free cash + reserves + bills due = owned liquid cash.
- **Cash forecast** (an estimate; changes nothing): starts from free cash today and, per month, adds scheduled income (or the three-completed-month income average when no income is scheduled, labelled) and separately labelled projected CD proceeds, subtracts upcoming bill and loan payments, the budget still planned (current month: plan less spending so far) with bills in budget-covered categories counted inside that budget rather than on top, and what dated reserve goals still need ((target − assigned) ÷ months left). CD principal returning at maturity is a projected transfer into liquid cash, never income. Safe to spend = free cash − payments before the next income − budget still planned this month − goal saving, shown with its parts; it does not spend projected CD cash before receipt.

### Certificates and time deposits

`lightning/deposits/` models a bank-specific `DEPOSIT` account as a portfolio of certificates. Each CD is a separate non-cash `DEPOSIT.CD` financial asset with its own name and terms: principal, annual percentage rate, start date, earliest withdrawal date, maturity date (chosen directly or calculated from a term in quarter-year increments), simple/compound method, payout schedule, and (for compound interest) capitalization frequency. A purchase is a `BUY` ledger transaction funded from a bank/cash account the user explicitly selects; the portfolio cannot receive or hold cash. The selected funding account must have enough user-owned cash on the recorded purchase date, and the service replays later posted cash activity to ensure the locked-up purchase does not make a later balance negative. Earlier negative history does not invalidate a purchase when sufficient cash is available on its date. The transaction ledger remains the source of actual principal and interest movements.

Interest and maturity proceeds are forecast estimates only. Forecasting never posts interest or principal: actual interest is entered manually from the bank statement, and actual redemption records principal proceeds entered by the user. Projections use actual elapsed days divided by 365 with `Decimal`, and do not change ledger balances, Net worth, or Free cash. The earliest withdrawal date is eligibility, not an automatic cash event. Before that date the CD is not immediately redeemable; from that date until maturity its *if sold today* estimate uses the inherited `DEPOSIT.CD` sale factor as an early-redemption haircut; at maturity projected proceeds use full principal and estimated interest. Once a redemption has been recorded, the certificate is no longer projected. Interest payouts are not reconciled automatically against bank postings; a recorded bank interest entry does not update the forecast schedule.

Migration `0039_cd_portfolios.sql` preserves existing account-level `cd_terms` as legacy data. It does not rewrite ledger history or infer individual certificate identities. Existing cash balances in old `DEPOSIT` accounts must be moved out by the user; legacy terms remain until an explicit, history-safe conversion workflow exists.
- **Loan payments are spending.** Recording or matching a loan payment is an ordinary money-out transaction in its category (default `EXP.SYSTEM.LOANS`, System › Loan payments, from migration 0035), so it counts in budget actuals and cash flow. The same payment leaves loans still to pay, so net worth is unchanged by paying it. The loan itself is never a ledger account.
- Historical dates use today's payment status; schedules are not versioned.

## Budget and reserve contract

Budget limits are monthly spending constraints. Reserves assign already-owned cash to emergency or project plans; the assignment is neither a ledger transaction nor a budget limit. Reserves reduce free cash. Budget room and free cash are separate values even when both are positive. Brokerage cash can be assigned as owned liquid cash, with its transfer requirement disclosed before daily use.

Budget actuals come from posted owned ledger expenses; expense-category refunds reduce spending in their original category. Custody, internal transfers, investment purchases, and revaluations are excluded. Monthly base rules are fixed EGP, a percentage of budgeting income, or a 3/6-completed-month spending average. Average windows divide by distinct months with qualifying activity; no observed month means unavailable. A direct parent limit is a ceiling for its branch, with child amounts treated as allocations and never added to the parent cap. Carryover is an opt-in spending-plan calculation: next month receives the prior tracked month’s signed Left (positive room or negative overspending), unless disabled or a dated reset boundary clears it. Carryover never moves cash, creates a liability, or changes ledger history. Multi-month summaries aggregate monthly base plans and actuals, including range-opening carryover once rather than repeating each month’s carryover-adjusted budget.

Carryover defaults off and is effective from a selected month. For a directly tracked monthly limit:

```text
current_budget(M) = base_monthly_budget(M) + incoming_carryover(M)
left(M)           = current_budget(M) - owned_spending(M)
incoming_carryover(M+1) = left(M), when enabled
incoming_carryover(M+1) = 0, when disabled or reset at M+1
```

Both positive room and negative overspending carry forward without clamping. A dated reset clears the incoming amount from that month while leaving prior history and future carryover settings intact. Parent caps remain ceilings; child allocations do not increase a parent cap. YTD, All time, and Custom summaries aggregate monthly base plans and actuals and include range-opening carryover once; partial-month plan comparisons are prorated estimates. A carryover is derived spending room, never cash or an independently posted balance.

Budget's ordinary view is a compact plan summary and Personal/Work/Investment rollup. Category rule editing and background estimates are opened on demand. Fixed EGP, budgeting-income percentage, and 3/6-observed-month averages are monthly methods; averages divide by distinct months with qualifying activity and never search beyond their configured window. The income basis uses selected owned income categories or an optional manual monthly amount. A missing baseline remains unavailable rather than becoming zero.

## Persistence, precision, and indexing

**Start fresh** (Settings › Your data, `POST /settings/fresh`) never deletes data:

- In profile mode it locks the open profile and sends you to new-profile setup.
- In browser mode it takes a backup, renames the database (and any journal) to `<name>_before-fresh_<timestamp>.db` beside it, then builds an empty database at the same path and swaps the running container. If the rename fails, the original file is reopened and nothing changes.

- SQLite with ordered, append-only migrations; never edit a migration already applied.
- Dates are stored as ISO `yyyy-mm-dd`. User entry accepts ISO, `dd/mm/yyyy`, and `dd/m` (current year); UI normalizes accepted input to ISO. CSV dates use the same parser.
- An account's legacy opening/tracking date is not a transaction-date boundary. Historical activity may predate the account metadata or opening-balance entry; balances remain chronological sums of their dated ledger lines.
- Money, prices, and quantities use `Decimal` in Python and integer `_e6` storage; new money inputs are validated to two decimal places. Display summaries round to whole currency units; entry controls retain cents.
- Important query paths are indexed by ledger account/date, asset/date, category/date, transaction id, transaction date/type/status, and price history asset/date.
- Corrections are audited. Transactions are voided/deleted through recoverable status/history flows; used categories cannot be physically removed and are archived instead.
- SQLite data and backups live locally under `data/`, which is not source controlled. Git moves code, not the personal financial database.

## UI contract

- **Names explain themselves.** Screens show a figure's registry label; there are no explanation toggles, and a name that needs explaining is renamed in `figures.py` (the old name becomes a retired alias).
- **Thin routes.** A route parses form values, calls services and renders results or errors. No SQL, and no financial calculation, in routes, templates or JavaScript. A screen calls the function the figure registry names.
- **Charts and key notes** position and phrase figures a service already computed. A key note may compare two figures, never derive a new one.
- **Every visible action leads to a working workflow.** A drilldown either applies its scope (category, dates) or is labelled as general activity. Category and date context survive drilldowns.
- **The period control** keeps custom dates and filters across submissions and supported drilldowns. Position figures use the period end; flows use the whole interval.
- **Failures stay visible.** Invalid edits keep the typed values and show the error, including inside a disclosure. A missing valuation is never replaced with zero. Expandable rows add up to their parent or say why a breakdown is unavailable.
- **Distinct concepts stay distinct:** What you own, account balances including custody, Free cash, Left in plan and If you sold today. Investment transfers are not expenses. Brokerage holdings are never counted as brokerage cash.
- **A way back without browser chrome.** The desktop window has no Back button, so a full page shows one when it was opened with `return_to`. Pages reached from many places (`/transactions`, `/investments/holding`, `/investments/planner`, `/investments/prices`) fall back to the same-origin `Referer`; the main tabs never do (`lightning/ui/web.py`, `_back_url`).
- **Brand guideline 3.6 in CSS.** The last block of `style.css` ("Guideline 3.6") holds the rules that override older layers: KPI tone by meaning (`surface-in|hold|out|over` on `stat_tile`, with an icon tile), money out in ink, soft field wells, Nile sub-tabs, no all caps. Change rules there rather than adding another layer.
- A presentation change never introduces a new financial model or forecast.

## CSV import and export contract

Import normalizes either one signed amount column or separate inflow/outflow columns into one signed amount (money out is negative) before review. Nothing downstream depends on the source CSV's shape. Rows stay unposted until the user reviews them. The AI preparation helper builds exact CSV instructions and current matching names locally and never contacts an AI provider.

Selected CSV exports are available from the transaction register, Categories, and the reevaluation ledger. Each request uses explicit selected IDs, with a 1,000-record limit; it does not silently export a whole account or database. A transaction export has one row per ledger line of each selected transaction, including stable transaction and line IDs, account, asset, category, quantity, amount, base amount, and beneficial-owner ID. A transfer or split transaction can therefore have multiple rows. Category exports include hierarchy, direction, active state, and budget flags. Reevaluation exports contain per-asset checkpoint values and the linked main-journal reference, including pending-price state. These are inspection/backup files, not the bank-import format. Amounts retain stored decimal precision and currencies are not aggregated. User-entered text that starts like a spreadsheet formula is prefixed with an apostrophe.

## Search and identity contract

Search is read-only retrieval; choosing a result is an explicit user action. Keep a single application-layer matcher for navigation and named entities, with per-surface scopes. Its result should include stable entity ID, type, display name, contextual subtitle, rank, and match reason. Use canonical Counterparty identities and their confirmed aliases; never store a fuzzy score as an alias or silently merge records. The existing limit of ten confirmed aliases per Counterparty remains.

Candidate order: exact ID/code/ref or name; normalized name; confirmed alias; prefix/word/substring; typo suggestion. Normalize Unicode, case, whitespace, punctuation, and limited script-specific marks for candidate retrieval. Preserve canonical text for display and identity; do not flatten meaningful distinctions or treat cross-script transliteration as a proven identity. [RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html) provides local similarity ranking and score cutoffs; calibrate cutoffs with real names, especially short ones, rather than using one threshold for every entity. Do not run fuzzy matching on amounts, dates, or short account codes.

Existing transaction SQL `LIKE` remains useful for exact literal filters, but searching by a matched Counterparty alias should use its canonical ID to find linked historical transactions. Similar account, category, and investment matches should resolve to their IDs before filtering ledger rows. When a page offers all entity types, group results by type so an own account cannot be mistaken for an external Counterparty. The transfer destination and custody owner must always be explicitly selected; a fuzzy match never changes posting type or beneficial ownership automatically. CSV suggestions likewise remain unposted until the user confirms.

Start with bounded local candidate lists and a small result limit. If size or measured latency later requires an index, evaluate SQLite FTS5 for candidate retrieval while retaining the same ranking and confirmation contract. Keep all query and identity logic in Python services; the UI only renders candidates and submits selected IDs.

**Planned work, in order:**

1. Agree on the contract: common misspellings, Arabic/English variants, aliases, duplicate names across entity types, short codes, and account-versus-counterparty ambiguity.
2. Build one matching service: normalize, rank exact, alias, prefix, token, substring, then RapidFuzz; return ID, type, label, context and match reason; never auto-select.
3. Apply it to scoped pickers: transfer account, counterparty, custody owner, category, instrument.
4. Add global search (keyboard shortcut and a visible entry) and page search for Accounts, People, Counterparties, Reserves and investments, grouped by type.
5. Let transaction history find rows through matched alias, account and category IDs, keeping exact date, amount and ref filters.
6. Verify zero results, near ties, one- and two-character queries, Arabic text, large histories, archived records and transfer safety, and measure latency. RapidFuzz has a native component, so Windows installation is a release check.

## Desktop app and encrypted profiles

**State: v0.4.0b1 development preview.** It is connected end to end and passes Windows CI, but it is not yet a distributable financial beta. Use dummy data until ordinary-PC acceptance passes.

**Shape.** FastAPI, Jinja and every financial service stay as they are. There is no frontend rewrite and no second financial implementation.

- **Windows:** `Lightning.exe` is a thin pywebview 6.2.1 + WebView2 shell (`lightning/desktop/`), shipped as a PyInstaller **one-folder ZIP**. It needs no Python, but it needs the WebView2 Runtime.
- **Linux:** `python -m lightning --profiles` runs the same runtime in a browser.
- **Legacy:** plain `python -m lightning` (`run.sh`, `run.bat`) is unchanged. It is plaintext and uses `data/lightning.db`.
- **Layers:** `lightning.runtime` (paths, instance lock, session, HTTP guards, launcher) sits between `lightning.desktop | lightning.main` and `lightning.ui`. `lightning.security` sits beside `lightning.database`. Browser mode never imports pywebview, pythonnet, WinForms or winreg. Windows-only dependencies are in their own lock files under `requirements/`.

**Profiles and data.** The default container is the real Documents folder, `Documents/Lightning/`: on Windows through the known-folder API, including redirection; on Linux through `XDG_DOCUMENTS_DIR`, falling back to `~/Documents`.

- **Layout:** each named profile has its own folder, `Name_YYYY-MM-DD_NNN_<id>/`, holding `<same>.db`, `keys.json`, `instance.lock` and `backups/`. An explicitly chosen database keeps its companions in `.<name>.db.lightning/` beside it.
- **Names:** the creation identity is stable across saves and releases. Backups append `_backup_<date>_<seq>_<id>`, and pre-upgrade copies use `_upgrade_`.
- **Discovery** scans only that container or a chosen folder, never all of Documents. It lists profiles and backups separately and never opens the newest-looking file on its own. Alternate locations are typed paths for now; there is no native file picker yet.
- **Rejected:** a plaintext legacy database or a backup selected as a live profile is refused with an explanation. So are hardlinked database paths.
- **Sync:** Documents may sync through OneDrive, but a local lock can't coordinate two PCs. Never open a live database on two computers; move completed encrypted backups instead.

**Encryption.**

- **Engine:** SQLCipher through `sqlcipher3` 0.6.2 (SQLCipher 4 format), keyed with a raw 32-byte data key. It is never keyed from a passphrase string, and an empty key is never passed.
- **Recovery key:** 128 random bits, shown once as 28 Crockford Base32 characters with a 12-bit check (`O→0`, `I/L→1`), and never stored. HKDF-SHA256 derives the data key from it. `key_id` is an HMAC of the data key: it identifies the key but is not secret.
- **Password slot:** `keys.json` holds the data key wrapped by AES-256-GCM. The wrapping key comes from Argon2id at 64 MiB, 3 iterations and 4 lanes. The metadata is authenticated as associated data, and its bounds are checked before any derivation.
- **Password changes** rewrap the same data key, so nothing is re-encrypted. A reset with the recovery key checks it against the database read-only, then atomically replaces the slot.
- **The same scheme on Windows and Linux** (owner decision). DPAPI and automatic unlock are deferred.
- **Threat model:** a copied database or backup without its key material is a 128-bit problem. Someone with both the database and `keys.json` can try passwords offline, which Argon2 slows but can't stop, so a passphrase must be at least 12 characters. Nothing protects an unlocked PC from malware.
- **Not in v1:** recovery-key rotation and rewriting existing backups. A safe version needs a recoverable multi-file commit protocol. Old backups keep their old `key_id`.

**Lifecycle and the database thread.**

- **One thread:** database connections are opened, migrated and closed only on the ASGI runtime's owning thread. The GUI sends commands, and network or crypto workers only return data.
- **Before any database work,** the app binds the socket and takes the instance lock.
- **Lock, switch and shutdown** stop new database operations and invalidate the session generation. They then drain active requests, close connections and wipe keys, and release the lock last.
- **Generation tokens:** finance writes carry the profile's generation token, so a stale tab cannot save into another profile.
- **Idle lock** after 15 minutes of foreground activity; background polling never extends it. Other tabs clear on a lock broadcast or at their next 15-second health check.
- **Migrations** commit each script and its version row together. A missing migration resource, or a database from a newer schema, stops the app before any write.
- **Before a pending migration,** the app writes a protected pre-upgrade encrypted backup, verifies it and keeps it outside pruning. If that backup fails, the migration is aborted.
- **Backups** are encrypted snapshots, reopened to check integrity, foreign keys, schema, row contents and sequences.
- **Not yet in the preview:** legacy import and backup restore. `database/staging.py` already builds verified candidate copies (including committed WAL data, and leaving the source untouched). Promoting one must wait for session quiescing and user confirmation, and must never copy bytes over a live file. The preview also doesn't fetch market prices or run reevaluation catch-up at startup.

**Local server security** (`lightning/runtime/http.py`).

- **Binding:** loopback only, on a random port.
- **Exact checks:** the Host and Origin must match exactly. A single-use launch code (30 seconds) is exchanged for a per-instance HttpOnly, SameSite cookie, which is required on every request.
- **Cookie names** differ per instance, so demo and real instances don't overwrite each other.
- **Headers:** `no-store` responses and a nonce-based script CSP. There are no inline event attributes.
- **Referrers:** `Referrer-Policy` is same-origin. `no-referrer` would turn same-origin POSTs into `Origin: null`; only the launch exchange uses no-referrer.
- **Uploads:** ordinary protected-profile POSTs remain capped at 512 KiB. The CSV import route accepts at most 5 MiB of source CSV (plus a bounded multipart envelope); its base64 column-mapping request and expanded review confirmation have separate, bounded limits. Starlette's multipart spool threshold is raised just above the guarded upload-body limit, keeping uploaded CSV bytes in memory rather than writing plaintext temp files. The CSV parser still enforces the 5 MiB source-file cap. PDFs are not accepted or parsed by this flow. If these limits change, retain route-specific body/field bounds and verify that the spooled upload does not roll to disk.
- **No outside requests:** fonts are local in profile mode and HTTP access logs are off. Logs never hold query strings, form values, amounts, names, tokens or key material.

**Window** (`lightning/desktop/window.py`).

- **Engine:** `edgechromium` is required and the IE fallback is rejected. A native navigation guard is attached before any page loads, and if it can't be installed, startup fails visibly.
- **Blocked:** foreign origins, unexpected schemes, new windows and file drops.
- **Never in the window:** no `js_api` and no remote debugging port. pywebview's `storage_path` is never pointed at user data, because pywebview 6.2.1 deletes that folder on exit in private mode.
- **Repeat launches** focus the locked profile's owning window.

**Build and release.**

- **CI:** `.github/workflows/desktop-probe.yml` installs hash-locked dependencies. It runs the full suite on Linux and the focused desktop, profile, database and UI tests on Windows.
- **Packaging:** `packaging/package_app.py` freezes the one-folder app, runs `--self-check` (synthetic profile create, finance routes, backup, reopen, recovery) and a real WebView2 smoke on a disposable root. Only after those pass does it zip the build with `SHA256SUMS`.
- **Probe:** `LightningProbe` is the older engineering check and is built separately.
- **Distribution:** the build is unsigned. Downloads are Actions artifacts of a private repository; there is no release page or public download yet. Never make disabling Windows protections part of installation. Signing becomes necessary if recipients' PCs refuse the build.
- **Updating:** close the app, extract the new ZIP into a fresh folder and launch it. User data stays in Documents. An old build refuses a newer schema, and rolling back needs the matching pre-upgrade backup.
- **Release ZIPs** never contain databases, backups, keys, logs or a `.venv`.
- **Developer checks:** `python desktop_app.py --self-check --report result.json` uses disposable data. On Windows, `--smoke` checks the real chooser and the blocked external navigation. `packaging/check_profile_browser.cjs` drives Chromium and Firefox through setup, saves, cross-tab lock, reopen, mobile layout and CSP.

**Open before a beta.**

- **Import and restore:** legacy import, and safe promotion of a backup restore.
- **Native file pickers.**
- **Ordinary PCs:** a clean-machine pass, including the second PC that failed at window startup.
- **Updates:** ZIP update acceptance from version N to N+1.
- **Final checks:** Windows and Linux acceptance runs.

## Working rules

1. Check `git status` first and preserve existing user changes and personal data.
2. Define a new concept in the Glossary before building it.
3. Add persistent state through a new migration and a module that owns its table. Never rewrite an applied migration.
4. Put cross-module actions in a workflow or service, with all writes in one database transaction.
5. Post every main-ledger effect through `TransactionService`. Generated valuation journals use `source=SYSTEM` and stable links to their reevaluation details.
6. Keep the UI thin (see UI contract).
7. Test the changed workflow and its invariants: date and money edge cases, ownership and net-worth effects, posting, archive and void. Run the full pytest suite, the import-boundary checks and `git diff --check`. Keep meaningful business assertions when updating old tests.
8. For UI changes, check populated and empty data and a 390px viewport in a browser, and re-run the Omar walkthrough when a workflow changes (steps 11–28 run in `tests/test_omar_year.py`).
9. Log changes under `Unreleased` in `CHANGELOG.md`, and change version headings only when releasing. Keep the four docs consistent: everything goes in Project Overview, Architecture, the Brand guideline or the Glossary, not in new files under `docs/`. The Brand guideline is one file, `docs/BRAND_GUIDELINE.html`, identical to the website's `brand-guidelines.html`.
