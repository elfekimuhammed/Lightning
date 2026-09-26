# Architecture

## Document status

- **Last updated:** 2026-09-26
- **Document revision:** 2026-09-26.3
- **App version:** 0.3.0 (`lightning/__init__.py`); packaging metadata in `pyproject.toml` still says 0.1.0.
- **Role:** module boundaries and financial calculation contracts. Product workflow and roadmap live in [Project Overview](PROJECT_OVERVIEW.md); term definitions live in [Glossary](GLOSSARY.md).

Lightning is a local-first, single-user **modular monolith**: one Python process, one SQLite database, and a server-rendered browser UI. The architecture prioritizes correctness, understandable ownership of data, and adding new financial-asset types without duplicating transaction logic.

## Runtime and dependency direction

```
ui/                   FastAPI routes, Jinja templates, small vanilla JS/CSS
  ↓                   calls application services; no SQL or financial calculations
workflows/            transactional use-cases spanning modules
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

| Activity | Main-ledger effect |
|---|---|
| Expense 450 | Account cash −450, `OUTFLOW`, category chosen by activity |
| CIB → THNDR transfer | CIB −10,000 and THNDR +10,000, both `INTERNAL` |
| Investment buy | Brokerage cash decreases; owned asset units and cost increase; net effect is internal |
| Money held for Dad | Cash still enters the named account; custody attribution reduces the user's owned share/net worth |
| Month-end return | Per-holding detail in reevaluation ledger; one account-level `VAL` journal in main ledger |

Core posting invariants: internal lines net to zero; external inflows/outflows have an activity category; a sale cannot take a position below zero; voided entries remain auditable but do not contribute to balances.

## Data ownership and derived values

- **Where:** `accounts` are cash wallets, bank accounts, CDs, brokerages, physical-asset locations, or other supported locations.
- **What:** `financial_assets` and `asset_classes` represent cash, stocks, funds, gold, CDs as supported assets, and future asset kinds. A brokerage account can hold cash and multiple assets.
- **Why:** `categories` label transaction activity: L1 is Personal, Work, or Investment; L2 is broad; L3 is intentionally unused until users need it.
- **Who:** `counterparties` are canonical people, businesses, institutions, and the other side of ledger activity. `whom` is a separate custody-owner attribution for money belonging to someone else.
- **Balances and analytics:** holdings, cash balances, budget actuals, ownership shares, gains, and net worth are calculated from posted ledger effects plus dated prices/custody metadata.

IDs are internal relational keys. Stable refs identify transactions; readable codes identify master records internally and for imports/search. Ordinary screens show names, not account codes. Source CSV spellings are retained during review; possible Counterparty matches are suggestions, never silent merges. Users can correct fields inline and post rows with safe incomplete metadata.

## Search and identity contract

Search is read-only retrieval; choosing a result is an explicit user action. Keep a single application-layer matcher for navigation and named entities, with per-surface scopes. Its result should include stable entity ID, type, display name, contextual subtitle, rank, and match reason. Use canonical Counterparty identities and their confirmed aliases; never store a fuzzy score as an alias or silently merge records. The existing limit of ten confirmed aliases per Counterparty remains.

Candidate order: exact ID/code/ref or name; normalized name; confirmed alias; prefix/word/substring; typo suggestion. Normalize Unicode, case, whitespace, punctuation, and limited script-specific marks for candidate retrieval. Preserve canonical text for display and identity; do not flatten meaningful distinctions or treat cross-script transliteration as a proven identity. [RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html) provides local similarity ranking and score cutoffs; calibrate cutoffs with real names, especially short ones, rather than using one threshold for every entity. Do not run fuzzy matching on amounts, dates, or short account codes.

Existing transaction SQL `LIKE` remains useful for exact literal filters, but searching by a matched Counterparty alias should use its canonical ID to find linked historical transactions. Similar account, category, and investment matches should resolve to their IDs before filtering ledger rows. When a page offers all entity types, group results by type so an own account cannot be mistaken for an external Counterparty. The transfer destination and custody owner must always be explicitly selected; a fuzzy match never changes posting type or beneficial ownership automatically. CSV suggestions likewise remain unposted until the user confirms.

Start with bounded local candidate lists and a small result limit. If size or measured latency later requires an index, evaluate SQLite FTS5 for candidate retrieval while retaining the same ranking and confirmation contract. Keep all query and identity logic in Python services; the UI only renders candidates and submits selected IDs.

## Position and reporting contract

- **Owned position / net worth within Lightning's scope:** the user's share of tracked cash and investment assets, excluding outstanding value held for others. Liabilities and receivables are not modeled. An account's full ledger balance may therefore exceed the user's owned share.
- **Free cash today:** owned liquid cash minus the effective amounts assigned to active cash reserves. It is a current allocation measure, not a forecast or permission to spend all of it.
- **Estimated liquidatable assets:** owned liquid cash plus owned investment assets multiplied by the user's liquidation factor. This is a scenario estimate, not full owned position, a sale quote, or free cash.
- **Period income/spending:** posted external activity in the selected date range. Internal transfers and investment purchases are not income or expense; refunds reduce their original expense category. Custody activity is excluded from owned analysis.
- **Investment return:** remaining holdings' market value less remaining cost, plus realized gains and dividends. The current portfolio and management XIRR must not be assumed owned-only until historical custody cash flows are verified.

Overview and Birdview should share one dated owned-position breakdown. The screenshots accompanying the UI review show a 400,050 EGP total on both pages but conflicting cash/investment splits. Treat that as an unresolved reconciliation task; do not hide the discrepancy by adjusting labels or charts alone. Missing or stale investment prices need explicit states and dates.

### Birdview history and performance, planned

The current Birdview period selector changes income/expense analysis; position cards are as of today. A later selected-period owned-value view must derive opening and closing positions from posted effects and dated valuations, then explain the change as external owned income minus spending, investment/FX returns, and explicit corrections/openings. Transfers and buys change allocation but have zero owned-position effect. Every bridge component should link to source transactions or valuations, and the closing value must reconcile to the displayed position.

XIRR is an annualized money-weighted rate using dated investment cash flows and an ending value. Since-inception XIRR is a separate measure from the selected period's currency return. A period-specific XIRR needs an opening valuation as an initial cash flow. If dates, flows, or ending value are inadequate, show an unavailable reason rather than 0%. Build owned-only cash flows before placing XIRR in Birdview; missing prices must not become invented historical quotes.

## Budget and reserve contract

Budget limits are monthly spending constraints. Reserves assign already-owned cash to emergency or project plans; the assignment is neither a ledger transaction nor a budget limit. Only reserves reduce free cash. Budget room and free cash are separate values even when both are positive.

The Budget service supports direct category or group limits, limits repeating from an effective month, one-month overrides, and optional 3/6-complete-month rolling averages. The first-plan UI previews suggestions and saves only after acceptance; accepted suggestions become fixed recurring limits unless the user deliberately chooses an average. Budget actuals follow posted owned spending, including refund reductions, and exclude custody activity. A direct parent limit is the ceiling for its entire branch; child limits are not added to that ceiling. Parent and child rows must not be double-counted in summary totals.

**Optional carryover is spending-limit-only**, defaults off, and is effective from the selected month. For a directly configured limit:

```text
available_limit(month) = monthly_limit(month) + opening_carryover(month)
remaining_limit(month) = available_limit(month) - actual_spending(month)
next_opening_carryover = max(remaining_limit(month), 0)  if carryover is enabled
next_opening_carryover = 0                              otherwise
```

Overspending remains visible in its original month and does not create a negative next-month carryover. A parent with its own limit keeps its own ceiling: child carryover never silently raises it. A parent without a direct limit derives its available amount from children. Carryover requires a direct limit, whether manual or average; clearing that limit ends later carryover until a new direct limit is set. Historical edits to transactions, refunds, limits, or average-derived amounts recalculate later carryover. Carryover is derived spending room, never cash or an independently posted balance.

The Budget screen should distinguish no plan, a zero limit, within plan, over plan, and spending with no covering limit. It should expose one-category adjustment as a focused workflow while preserving the full grid for advanced edits. The past-month review should explain opening carryover and link back to the month and transactions that caused it.

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
