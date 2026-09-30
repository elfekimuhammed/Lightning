# Architecture

## Document status

- **Last updated:** 2026-09-30
- **Document revision:** 2026-09-30.1
- **App version:** 0.3.0 (`lightning/__init__.py`); packaging metadata in `pyproject.toml` still says 0.1.0.
- **Role:** module boundaries and financial calculation contracts. Product workflow and roadmap live in [Project Overview](PROJECT_OVERVIEW.md); term definitions live in [Glossary](GLOSSARY.md).

Lightning is a local-first, single-user **modular monolith**: one Python process, one SQLite database, and a server-rendered browser UI. The architecture prioritizes correctness, understandable ownership of data, and adding new financial-asset types without duplicating transaction logic.

## Runtime and dependency direction

```
ui/                   FastAPI routes, Jinja templates, small vanilla JS/CSS
  ↓                   calls application services; no SQL or financial calculations
workflows/            transactional use-cases spanning modules
planning/             cash planning: recurring items, loans, what you owe, cash forecast (read-only)
domain services/      accounts, assets, categories, transactions, investments, budgeting
reporting/            read-only queries and derived views (net worth, budgets, Birdview)
database/             SQLite, migrations, seed data, backup, settings, audit
core/                 dates, money, identifiers, posting rules; no app dependencies
```

`bootstrap.py` is the composition root. Cross-module operations call public services, not another module's repository. Import boundaries and UI restrictions are checked by `import-linter`/tests. Transaction posting is centralized in `TransactionService`; other modules build validated postings and ask it to write them.

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

Core posting invariants: internal lines net to zero; external inflows/outflows have an activity category; a sale cannot take an owner's position below zero; voided entries remain auditable but do not contribute to balances. `ledger_entries.owner_id` is nullable: null means user-owned, otherwise the referenced Counterparty owns that line. Transactions carry the selected owner across their cash and asset lines. Dated cash and holding balances are checked per account, asset, and owner when posting or editing.

Brokerage buys must use cash in the same brokerage account as the purchased holding. The purchase's owner must have enough brokerage cash on the trade date; cash in another owner's share cannot cover the buy.

## Data ownership and derived values

- **Where:** `accounts` are cash wallets, bank accounts, CDs, brokerages, physical-asset locations, or other supported locations.
- **What:** `financial_assets` and `asset_classes` represent cash, stocks, funds, gold, CDs as supported assets, and future asset kinds. A brokerage account can hold cash and multiple assets.
- **Why:** `categories` label transaction activity: L1 is Personal, Work, or Investment; L2 is broad; L3 is intentionally unused until users need it.
- **Who:** `counterparties` are canonical people, businesses, institutions, and optional beneficial owners on ledger lines. The transaction's `Whom` choice is copied to its cash and asset lines.
- **Balances and analytics:** holdings, cash balances, budget actuals, ownership shares, gains, and net worth are calculated from posted ledger effects, owner IDs, and dated prices.

The read-only Integrity checks compare gross account values with asset-class reports, verify `owned net worth + money held for others = gross account values` overall and per account, compare categorized outflows with reported spending and budget actuals, verify reserves against owned liquid cash, and close the month-to-date net-worth bridge. Missing valuations mark affected comparisons incomplete rather than green. These checks diagnose report/subledger mismatches; they never adjust posted entries.

IDs are internal relational keys. Stable refs identify transactions; readable codes identify master records internally and for imports/search. Ordinary screens show names, not account codes. Source CSV spellings are retained during review; possible Counterparty matches are suggestions, never silent merges. Users can correct fields inline and post rows with safe incomplete metadata.

## Search and identity contract

Search is read-only retrieval; choosing a result is an explicit user action. Keep a single application-layer matcher for navigation and named entities, with per-surface scopes. Its result should include stable entity ID, type, display name, contextual subtitle, rank, and match reason. Use canonical Counterparty identities and their confirmed aliases; never store a fuzzy score as an alias or silently merge records. The existing limit of ten confirmed aliases per Counterparty remains.

Candidate order: exact ID/code/ref or name; normalized name; confirmed alias; prefix/word/substring; typo suggestion. Normalize Unicode, case, whitespace, punctuation, and limited script-specific marks for candidate retrieval. Preserve canonical text for display and identity; do not flatten meaningful distinctions or treat cross-script transliteration as a proven identity. [RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html) provides local similarity ranking and score cutoffs; calibrate cutoffs with real names, especially short ones, rather than using one threshold for every entity. Do not run fuzzy matching on amounts, dates, or short account codes.

Existing transaction SQL `LIKE` remains useful for exact literal filters, but searching by a matched Counterparty alias should use its canonical ID to find linked historical transactions. Similar account, category, and investment matches should resolve to their IDs before filtering ledger rows. When a page offers all entity types, group results by type so an own account cannot be mistaken for an external Counterparty. The transfer destination and custody owner must always be explicitly selected; a fuzzy match never changes posting type or beneficial ownership automatically. CSV suggestions likewise remain unposted until the user confirms.

Start with bounded local candidate lists and a small result limit. If size or measured latency later requires an index, evaluate SQLite FTS5 for candidate retrieval while retaining the same ranking and confirmation contract. Keep all query and identity logic in Python services; the UI only renders candidates and submits selected IDs.

## Position and reporting contract

### Investment report contract (2026-09-28)

The Investments report uses posted, non-void main-ledger entries dated by transaction date. It scopes every calculation to `owner_id IS NULL` and keeps cost lots keyed by owner, account, and asset; an opening (`OPN`) holding is a baseline adjustment and never new money. The portfolio boundary includes investment holdings and cash in brokerage, physical-asset, and other investment accounts. Investment-account cash transfers and trades net internally; direct physical purchases/sales count only their portfolio-side holding change. Dividends are distributions, not contributions. Valuation checkpoint rows (`return_base_e6`) and aggregate `VAL` journals are reconciliation data and are excluded from return.

For a selected interval, new money is the positive posted change across that boundary and withdrawals are the absolute negative change. Net money added is their difference. Realized gain is net sale proceeds less average cost removed, with basis per owner/account/asset; purchase costs and net sale proceeds already include fees. Distributions use the cash actually posted. Change in unrealized gain is the end balance less the balance immediately before the interval. Investment result adds realized gain, unrealized change, distributions, and any separately identified FX/cost effects once. No balancing `other return` is permitted. If historical prices/ownership are missing, report the result unavailable.

At the as-of date, cost of holdings still owned is remaining basis; holdings value is units times a dated confirmed valuation; unrealized gain is value less remaining basis. Uninvested investment cash is owned cash in investment accounts. Estimated cash after sale adds that cash to each owned holding value times its asset-class liquidation factor; it is a scenario and excludes reserves. A cost fallback is not a confirmed price. Dividend asset attribution is stored in `investment_dividend_assets`; legacy memo attribution is migrated only when it uniquely matches an asset code, otherwise the dividend remains unresolved while its cash amount is retained. Fiscal-year dates are unconfigured, so YTD is labeled Calendar 2026.

- **Full owned wealth:** known value of all tracked assets belonging to the user, including assigned reserves and brokerage cash, after custody is excluded. Missing valuations are reported; certain obligations (what you owe) are shown beside it as a separate item and give net worth; receivables remain outside the model.
- **Free cash:** owned wallet, bank, and brokerage cash less effective reserve assignments and bills due as of the selected date. Brokerage cash is included once but needs a transfer before everyday spending. Reserve history begins at the recorded baseline; earlier dates are unavailable instead of borrowing today's assignments.
- **Estimated available value:** free cash plus each owned investment class's value multiplied by its own 0–100% liquidation factor. Class settings use stable asset-class IDs. This is a scenario estimate using current factor settings, not full owned wealth, a sale quote, or a booked loss.
- **Period income/spending:** posted external activity in the selected date range. Internal transfers and investment purchases are not income or expense; refunds reduce their original expense category. Custody activity is excluded from owned analysis.
- **Investment return:** remaining holdings' market value less remaining cost, plus realized gains and dividends. The current portfolio and management XIRR must not be assumed owned-only until historical custody cash flows are verified.

Overview and Birdview share the date-range parser. Positions in both are valued at the selected range end. Birdview expense and flow views use the selected interval; its asset-class weights divide by owned investment value and exclude cash and custody. A missing valuation is disclosed and an unavailable reserve history makes free cash and estimated available value unavailable. Historical liquidation estimates use current factor settings.

### Birdview history and performance

Birdview's four horizons apply consistently to flow, expense, and position views; the position and reserve assignments are as of the range end. Internal transfers and investment purchases are excluded from cash-flow totals. Expense categories roll up consistently across the ranked overview, L1/L2 analysis, and linked transactions. Wealth movement remains distinct from investment return.

XIRR is an annualized money-weighted rate using dated investment cash flows and an ending value. Since-inception XIRR is a separate measure from the selected period's currency return. A period-specific XIRR needs an opening valuation as an initial cash flow. If dates, flows, or ending value are inadequate, show an unavailable reason rather than 0%. Build owned-only cash flows before placing XIRR in Birdview; missing prices must not become invented historical quotes.

## Cash planning contract

`lightning/planning/` owns planned items (`planned_items`) and their settled payments (`planned_payments`). It reads the ledger, budget and reserves through their services and never posts on its own; recording a payment goes through `TransactionService` like any other entry.

- **Items.** A planned item is a bill, subscription, income or loan with an amount per payment and a schedule: frequency (once, weekly, monthly, every 3 months, yearly) every N periods from a first date, optionally ending at a last date or after a number of payments. Monthly-type dates keep the first date's day, clamped to the month's last day. Loans must have a number of payments or a last date.
- **Payment status.** Each scheduled date is Paid (linked to a posted transaction), Skipped, Due (on or before today, not settled) or Upcoming. A voided linked transaction makes the payment Due again. A transaction settles at most one payment.
- **Matching.** A posted, owned money-out (money-in for income) transaction settles a payment automatically when it is the only candidate within 7 days of the date, on the item's account if set, matching its counterparty or category, within 10% of the amount (1% for loans). Anything ambiguous is left for the user; recurring-payment suggestions never create items.
- **What you owe** = bills due + loans still to pay, each payment once. **Bills due** are Due bills, subscriptions and loan payments; **loans still to pay** are every unpaid loan payment. **Net worth** = what you own − what you owe. **Free cash** = owned liquid cash − effective reserves − bills due. The Integrity check verifies free cash + reserves + bills due = owned liquid cash.
- **Cash forecast** (an estimate; changes nothing): starts from free cash today and, per month, adds scheduled income (or the three-completed-month income average when no income is scheduled, labelled), subtracts upcoming bill and loan payments, the budget still planned (current month: plan less spending so far) with bills in budget-covered categories counted inside that budget rather than on top, and what dated reserve goals still need ((target − assigned) ÷ months left). Safe to spend = free cash − payments before the next income − budget still planned this month − goal saving, shown with its parts.
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

- SQLite with ordered, append-only migrations; never edit a migration already applied.
- Dates are stored as ISO `yyyy-mm-dd`. User entry accepts ISO, `dd/mm/yyyy`, and `dd/m` (current year); UI normalizes accepted input to ISO. CSV dates use the same parser.
- An account's legacy opening/tracking date is not a transaction-date boundary. Historical activity may predate the account metadata or opening-balance entry; balances remain chronological sums of their dated ledger lines.
- CSV import normalizes either a signed amount column or separately mapped inflow/outflow columns into one signed Amount before row review; money-out is negative. The ledger and downstream reporting do not depend on source CSV shape.
- Money, prices, and quantities use `Decimal` in Python and integer `_e6` storage; new money inputs are validated to two decimal places. Display summaries round to whole currency units; entry controls retain cents.
- Important query paths are indexed by ledger account/date, asset/date, category/date, transaction id, transaction date/type/status, and price history asset/date.
- Corrections are audited. Transactions are voided/deleted through recoverable status/history flows; used categories cannot be physically removed and are archived instead.
- SQLite data and backups live locally under `data/`, which is not source controlled. Git moves code, not the personal financial database.

## Major modules in this repository

| Package/module | Responsibility |
|---|---|
| `lightning/core` | Money/date parsing, refs/codes, errors, posting validation |
| `lightning/database` | Connection, migrations, seed, backups, audit, configuration |
| `lightning/accounts` + `workflows/accounts.py` | Account rules and atomic account/opening-balance workflows |
| `lightning/assets` | Asset classes, financial assets, local EGX catalogue, prices and quote adapters |
| `lightning/categories` | Activity taxonomy and archived/pickable category rules |
| `lightning/counterparties.py` | Canonical names, aliases, match suggestions and defaults |
| `lightning/transactions` | Main-ledger document and line posting, editing, voiding, search |
| `lightning/investments` + `reevaluations.py` | Trades/positions and scheduled/historical valuation checkpoints |
| `lightning/money_from_others.py` | Ownership/custody attribution for funds and assets held for others |
| `lightning/bank_imports.py` + `reconciliation.py` | Staged CSV review, inline corrections, posting and statement reconciliation |
| `lightning/budgeting` + `reserves.py` | Spending plans and cash-reserve goals (separate concepts) |
| `lightning/reporting` | Read-only queries and computed portfolio/net-worth/budget reporting |
| `lightning/ui` | Browser routes, templates, static assets |

## Extension rules

1. Define the product term and taxonomy in `docs/GLOSSARY.md` before adding a new concept.
2. Add persistent state through a new migration and a module that owns its repository/table.
3. Put cross-module actions in a workflow/service and wrap all writes in one database transaction.
4. Post all main-ledger effects through `TransactionService`; generated valuation journals use `source=SYSTEM` and stable links to their reevaluation details.
5. Keep UI thin: parse form values, call services, display results/errors. No SQL or financial calculations in route/template/JavaScript code.
6. Add focused tests for date/money edge cases, ownership/net-worth effects, posting invariants, and archive/void behavior; run the full pytest suite and import-boundary checks.
7. Add release/version notes to `CHANGELOG.md` when shipping a version; update the overview at the owner's request.

## Local run and Windows portability

On Linux, run `./run.sh`; Lightning serves on `http://127.0.0.1:8765`, which the user opens manually in Firefox. Windows has `run.bat` and uses the same `python -m lightning` entry point; it opens the default browser unless `--no-browser` is supplied. Startup handles backup/migrations and attempts due investment reevaluations. Keep the server process alive while using the app; stopping it does not delete data.

The core uses `pathlib`, Python's `sqlite3`, FastAPI, and bundled Jinja/static files; no Linux-only runtime API is required for the ledger. Windows support still needs native verification. The launcher's Python version check and pip failure handling are weak, and `run.bat` currently installs requirements on every launch. Price fetching calls `ZoneInfo("Africa/Cairo")`; Windows commonly lacks an IANA time-zone database, so declare `tzdata` and verify dates there. Python's [zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html#data-sources) recommends that dependency for cross-platform applications.

Current default data is `PROJECT_ROOT/data/lightning.db`. This works for a user-writable source checkout but is unsuitable for an installer placed in a protected program directory. Before packaging, define a per-user data location and migration/backup behavior for existing databases. Do not move an existing user's database silently. The first Windows acceptance pass should use a source checkout in a writable folder and test spaces in paths, UTF-8 names, CSV files, migrations, backups, startup re-use, and occupied ports.
