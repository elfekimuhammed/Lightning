# Lightning — Project Overview

## Document status

- **Last updated:** 2026-09-27
- **Document revision:** 2026-09-27.1
- **App version:** 0.3.0 (`lightning/__init__.py`); `pyproject.toml` still reports 0.1.0 and needs correction at the next release/package update.
- **Role:** product purpose, current workflows, user questions, and delivery roadmap. [Architecture](ARCHITECTURE.md) owns calculation contracts; [Glossary](GLOSSARY.md) owns terminology.

## Product purpose

Lightning is a local-first personal wealth-management app for Egyptians. It helps people understand where money is held, what it is invested in, how spending compares with plans, and how owned wealth changes over time. The main workflow is deliberately simple: record or import activity, resolve unclear Counterparties/categories, then use analysis to understand patterns and build savings goals.

The model separates two questions: **Account — where is value held?** (CIB, Cash wallet, THNDR, gold at home) and **Financial asset — what value is held?** (EGP cash, COMI shares, fund units, gold grams, supported deposits).

Product priorities: simplest useful workflow and fewer clicks; consistent terminology; durable, searchable data; clean code boundaries; and broad coverage of normal personal-finance cases. Avoid expensive AI calls for deterministic app features. Calculations, matching, monthly price processing, and categorization defaults should be ordinary code, not AI calls.

## Decisions that must stay consistent

- There is **one main transaction ledger**. Account registers, all-account view, budget actuals, investments, Birdview, and analysis are filtered or computed views of it.
- The **reevaluation ledger** is valuation detail, not another activity ledger. Its per-asset checkpoint rows link to one aggregated `VAL` journal per account in the main ledger.
- Accounts are locations; financial assets are what is held; asset classes group assets; categories describe activity; Counterparty identifies the other side. A nullable ledger-line `owner_id` records beneficial ownership: blank means the user owns the line; a selected Counterparty owns it otherwise.
- A physical item is individually named and held as a piece-count record with net gold-bearing weight per piece, karat, and acquisition cost. A matching-karat gold price reference is per gram of that karat; item value is piece count × net grams per piece × that price. Purity is descriptive and is not applied a second time to a karat-specific price. Stones and workmanship are excluded from gold weight and metal-value estimate; acquisition cost may include them.
- Category L1 is **Personal / Work / Investment**; L2 is broad; L3 stays empty until users choose to add detail. Categories follow activity, not money direction.
- Counterparty names are canonical. Similar spellings are suggestions requiring deliberate selection or explicit creation—never silently merge or create duplicates.
- Other people's money stays in the full account/holding balance but is attributed to its owner and excluded from the user's owned totals/net worth. It is not income/expense or a receivable. **Liabilities and money owed to the user are out of scope.**
- Owner balances are calculated from dated ledger lines by account and asset. Posting, editing, and restoring an owner's entries must not make that owner's cash or holdings negative. Brokerage buys use cash already in that brokerage account and only the selected owner's share.
- Ordinary screens show names, not account codes. Codes and IDs are for internal identity, linking, import, and search.
- Summary amounts display rounded to whole currency units; inputs retain cents. New money entries are validated to two decimals; `_e6` storage remains exact.
- Dates are stored canonically as ISO `yyyy-mm-dd`. User entry accepts `31/1` (current year), `31/1/2026`, or `2026-01-31`; numeric day/month is day-first and accepted input normalizes to ISO.
- An account's stored opening/tracking date does not block historical activity. Users can add, edit, import, or restore transactions dated before it; the opening balance remains its own dated ledger entry.
- Keep lists alphabetical. Used categories cannot be physically deleted; archive instead. Archived categories are not selectable for new transactions.
- Reserves are plans for already-owned cash, not transactions or budget limits. Emergency Fund is a permanent main section and reports its size as multiples of completed six-month average salary.
- The Linux desktop workflow starts the local server and opens `http://127.0.0.1:8765` manually in Firefox. The Windows launcher exists but its end-to-end setup and operation still need a native Windows verification pass; it currently opens the default browser.
- Update this overview when the owner asks. Record shipped changes in `CHANGELOG.md`; do not bump the version unless actually releasing.

## Technology and local operation

| Area | Choice |
|---|---|
| Runtime | Python 3.11+, FastAPI, Uvicorn |
| UI | Jinja2 server-rendered HTML, vanilla JS/CSS; no frontend build |
| Persistence | One local SQLite file in `data/`, ordered SQL migrations, local backups |
| Financial precision | `Decimal` in Python, scaled integers (`_e6`) in SQLite; no binary floats in financial logic |
| Quality | pytest and `import-linter` boundaries |
| Network | Local-only server bound to `127.0.0.1` |

On Linux run `./run.sh`, then open `http://127.0.0.1:8765` in Firefox. Windows has `run.bat`, but support is provisional until the Windows readiness milestone below passes. Startup performs backups/migrations and processes due investment checkpoints. Keep the process running while using the app. Financial data is local and is not committed to Git; syncing code does not sync the database.

## Current user workflows

- **Accounts and ledger:** open an account with a starting balance or enter first activity; signed money movements and transfers; edit, void/restore, multi-select/delete, search, and statement reconciliation.
- **Counterparties/categories:** dedicated Counterparty management, aliases/default categories, Personal/Work/Investment L1 and broad L2 categories, alphabetized explicit selection, and per-category or bulk activate/archive/delete actions (used categories archive instead of being erased).
- **CSV import:** stage CSV for supported account types; map either one signed amount column or separate inflow/outflow columns. Separate columns merge into one signed Amount (inflow positive, outflow negative) before inline review. Resolve uncertain Counterparties/categories and post valid rows when optional metadata is incomplete. Similar names are suggestions, not automatic merges.
- **Budget:** a suggested first plan or one broad limit, monthly status and attention items, manual or rolling-average category/group limits, optional spending-limit carryover, and a past-month review. Budget limits are separate from cash reserves. Focused single-category adjustment remains a workflow improvement.
- **Investments:** create/search assets, record buy/sell/dividend inside the brokerage account, enter total or unit price, and view current valuation/ownership/returns in the investment overview. Account codes are hidden in ordinary UI.
- **Valuation:** startup processes due month-end checkpoints; supported sources may fetch prices, otherwise missing historical prices require user input. A sale forces a sale-day checkpoint. Detail links to one generated account journal in the main ledger.
- **Money from others:** custody owner attribution for funds/assets held in tracked accounts, with full account balance and user's owned share distinguished.
- **Birdview/reserves:** current owned wealth, liquidity/reserves, and broad cash-flow/asset views. Emergency Fund is fixed; other reserves are separate plan rows and do not themselves move cash.

## Code map

```
lightning/core/             dates, money, codes, refs, errors, posting rules
lightning/database/         SQLite, migrations, seed, backup, audit/settings
lightning/accounts/         account identities and rules
lightning/assets/           financial assets/classes, EGX catalogue, prices
lightning/categories/       Personal/Work/Investment category tree
lightning/transactions/     only writer of main-ledger postings
lightning/investments/      trades, positions and investment calculations
lightning/reevaluations.py  monthly detail and linked account-level VAL journal
lightning/money_from_others.py  custody ownership attribution
lightning/budgeting/        monthly plans and rolling average methods
lightning/reserves.py       emergency fund and other reserve plans
lightning/bank_imports.py   CSV staging/review/posting
lightning/reconciliation.py cleared items and statement comparison
lightning/reporting/        read-only queries and derived reporting
lightning/workflows/        atomic cross-module account workflows
lightning/ui/               FastAPI routes, templates, static JS/CSS
```

## Questions and screen ownership

| User question | Screen today | Next useful action |
|---|---|---|
| Where do I stand? | Overview shows owned value at the selected period end, owned cash after dated reserve assignments, income and spending for the exact period, and current attention items. | Open Birdview for analysis, Budget for spending plans, Reserves for assigned cash, or an account for a transaction. |
| What is mine and how much cash is free? | Birdview shows owned liquid cash, investments, reserves, and an estimated liquidation value. | Open an account, holding, or reserve. |
| Where did money come from or go? | Birdview has all-time/year/month/custom income and expense views and transaction links. | Inspect the supporting transactions. |
| Am I following my spending plan? | Budget shows monthly available limit, spent, room, attention items, category status, and carryover. | Inspect category transactions or edit a limit. |
| What happened in this account? | Account register shows balances and activity. | Record, correct, import, or find an account transaction. |
| How did owned wealth change over time? | A current position and backend bridge exist. The Birdview period filter currently affects flows, not historical position. | Historical owned-value series and an explainable period bridge are planned. |
| How are investments performing? | Holdings, costs, returns, and XIRR exist in the investment management view; Birdview has capital and return breakdowns. | Owned-only XIRR and valuation quality in Birdview remain planned. |

All owned-position, budget-actual, and performance views must exclude transactions and balances marked as money from others. Internal transfers do not create income or expense. Refunds reduce spending in their original category.

## Customer workflow and UI decisions

The intended path is **understand on Overview → explain on Birdview, Budget, or Reserves → record in an account → review exceptions at import**. Overview is a status screen across All time, YTD, Monthly, and Custom ranges; it does not own analysis, plans, reserve management, or transaction entry. All-account transactions remains a search/history workspace.

| Screen | Current friction | Intended hierarchy and action |
|---|---|---|
| Overview | Previously mixed analysis, reserve details, budget plan, and transaction history into the status screen. | Owned position at the range end, change from the prior position where reliable, cash available after dated reserve assignments, income/outflow bars for the selected range, and up to three current actionable attention items. |
| Birdview | Current asset position sits below a page-wide period selector; discounted assets lead while full owned value is secondary. | Full owned position, owned cash, free cash after reserves, and investment value first. Show liquidation-factor estimate as a secondary scenario. Put period controls inside income/spending analysis. Keep holdings and reserves links beside their breakdowns. |
| Account | Four duplicate balance figures on a normal cash wallet; maintenance buttons compete with entry; a crowded inline entry row explains signed amounts and transfers in one paragraph. | One meaningful balance, with total/held-for-others/owned bridge only where needed. Primary Add transaction action with account preselected and Money out / Money in / Transfer choices; ledger below for history. Import is secondary; edit, reconciliation, and deactivation move to an account menu. |
| Budget | Full edit grid remains the main route for many adjustments. | First plan in one action, then monthly status, short attention list, one-category action, and a past-month review. Full grid remains advanced. “Room in plan” is never cash available. |
| Reserves | Creation exposes many optional fields at once. | Start with purpose and amount; ask for due date, recurrence, and counterparty matching only when useful. Overview and Birdview cash-available figures link to this workflow. |
| Import | Review exposes many editable fields on every row. | Lead with Ready to post, Needs a decision, and Possible duplicates; expand row editing for exceptions. |

The supplied UI screenshots show Overview and Birdview reaching the same 400,050 EGP total with different cash/investment splits. That discrepancy must be diagnosed before presenting a shared asset chart. The first figure to trust is the owned total with an as-of date; every breakdown must reconcile to it.

## Budget customer flow

Budget answers: **What did I plan to spend, what has happened, and where should I act?** A budget limit changes the spending plan only. A reserve assigns already-owned cash and reduces free cash; the two are never added together or substituted for each other.

1. **First visit:** with useful prior spending, preview suggested fixed monthly limits from previous complete months, then let the user accept or adjust them. With sparse history, ask for one broad Personal limit. Opening Budget alone never saves a plan. Work appears when used.
2. **Ordinary month:** open on available limit, spent, room in plan, separate free cash, and a small set of over-limit or uncovered-spending items. Category rows lead to transactions and adjustment. Detailed manual/3- or 6-month-average controls live under Edit full plan.
3. **Transaction/import feedback:** show category impact near the saved entry and offer Add to plan when uncovered, without blocking posting.
4. **Month review:** show planned, spent, overspent, and unused room. Optional carryover raises a later spending limit only; it does not move cash. Historical edits recalculate later derived carryover.

The first-plan, monthly status, feedback, optional carryover, and basic past-month review are implemented. A focused one-category adjustment and stronger links from attention items to the exact causes still need refinement. See the calculation contract in [Architecture](ARCHITECTURE.md#budget-and-reserve-contract).

## Delivery roadmap

| Milestone | State at this revision | Outcome or next work |
|---|---|---|
| M0–M1 Foundation and cash accounts | Shipped | Ledger, opening balances, account registers, transfers, edit/void, search. |
| B Budget foundation | Shipped | Monthly category/group limits, manual and rolling averages. |
| B.1 Budget customer flow | Partly shipped | Finish focused category adjustment and inspect setup/attention/feedback with real user data. Optional carryover is spending-limit-only. |
| M2 Reports and corrections | Partial | Reconciliation, splits, and refunds exist; balance adjustments, report pages, and month close remain. Reconciliation is not a primary workflow priority. |
| M3 Manual investments | Shipped | Assets, trades, dividends, prices, holdings, gains, allocation, investment management XIRR. |
| M3.1 Instrument catalogue | Partial | Local catalogue search/prefill exists; coverage and identifier quality need evaluation. |
| UI workflow overhaul | Planned | Follow the bounded tasks below; avoid a single broad rewrite. |
| Windows readiness | Planned, launcher exists | Verify native Windows setup and all core workflows; harden Python selection, dependency installation, time-zone data, and failure messages. |
| Search consistency | Planned | One typo-tolerant ranking contract across navigation, accounts, people, counterparties, categories, investments, reserves, and transactions. |
| M3.2 Birdview history/performance | Planned after base UI | Historical owned position, selected-period change bridge, valuation quality, owned-only XIRR. |
| M4 Market data and FX | Planned | Wider price coverage, currency conversion, multi-currency accounts, FX revaluation. |
| M6 Deposits and gold details | Planned | CD lifecycle, local gold costs and buyback, corporate actions. |
| Physical gold items | In progress | Named pieces, matching-karat reference/manual valuations, item purchase/sale activity, and report integration; preserve existing gram holdings unchanged. |
| M7 Planning and imports | Partial | CSV import and reserves exist; manual-entry/import matching, review inbox, recurring transactions, and dated cash outlook remain. Forecasting follows a solid base. |

Credit cards, loans, other liabilities, and receivables/money owed to the user are out of scope by owner decision. Money held for others is tracked separately. Bank connections and device sync depend on provider and deployment choices.

### Small UI tasks for Luna

Each task should leave the app usable, include a concise before/after workflow description, and verify empty, cash, custody, and investment-account states. Keep financial calculation changes in separately reviewed work.

| Order | Task | Acceptance point |
|---|---|---|
| 0 | Diagnose Overview/Birdview cash and investment split; define shared owned-position components and as-of date. | Both screens reconcile to the same breakdown, or a reproducible calculation fix is specified. |
| 1 | Remove Overview Add, fake trend, misleading investability/savings claims, and broken month arrows. | No generic entry or unsupported claim remains on Overview. |
| 2 | Condense account header and move maintenance controls. | One balance on normal cash accounts; ownership bridge only with custody; Add transaction is primary. |
| 3 | Replace inline register entry with an account-scoped Money out / Money in / Transfer flow. | A user can record all three without signed-amount instructions; ledger stays readable. |
| 4 | Rebuild Overview as a short period-aware status screen. | Shared All time/YTD/Monthly/Custom ranges; owned position, cash available, period flows, and current attention have clear drilldowns. |
| 5 | Separate Birdview's current position from selected-period activity. | Period filter no longer appears to change today's assets; full owned value leads; liquidation scenario is secondary. |
| 6 | Shorten reserve creation. | Purpose and amount suffice for a simple reserve; free-cash effect is visible. |
| 7 | Make import review exception-first. | Ready rows can be posted without scanning all fields; duplicates and unresolved rows are prominent. |
| 8 | Clean navigation and user-facing terminology. | Home, Budget, Birdview, Accounts are clear; advanced screens stay accessible; no L1/L2 jargon. |
| B.1 follow-up | Finish focused Budget adjustment and review its first-use flow. | One category can be changed without opening the full grid; parent/group effect is clear. |

After the base is coherent, prioritize import matching and a review inbox; then build the dated cash outlook. Do not turn current free cash into a future-balance prediction.

## Search experience milestone

The user may type an imperfect name, such as “overiveiw” for Overview, a mistyped account, or a merchant spelling absent from its saved aliases. Search should help them recover without changing financial identity or transaction meaning on their behalf.

**Current state:** Counterparties have up to ten confirmed aliases and close-name suggestions; categories also suggest similar names. Account lookup requires an exact name/label/code. Register and investment pickers mostly filter by substring, while transaction history uses literal word matches. People/custody and Counterparty management have no consistent page search. There is no site-wide search for destinations and records.

**Intended experience:** A site-wide search entry (keyboard shortcut and visible affordance) finds pages, accounts, people who own tracked money, counterparties, categories, holdings/instruments, reserves, and transactions. Results are grouped by type and labeled with enough context to choose safely: e.g. “CIB · bank account” versus “CIB · Counterparty,” or “Dad · money held for others.” Each existing picker uses the same ranking and typo fallback, scoped to valid choices for that task. A zero-result state offers close matches and a clear create action only where creation makes sense.

Rank exact name/code/ref first, then normalized spelling, confirmed alias, prefix/word/substring, and finally close spelling. Show why a close result appeared (“similar spelling” or “saved alias”). A mistaken spelling must **never** silently create or merge a Counterparty, choose a custody owner, turn an entry into a transfer, or post an imported transaction. Short account codes, amounts, dates, and transaction refs need exact or structured matching rather than fuzzy guesses.

Use the open-source [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) library for typo ranking rather than building a new string-matching algorithm. Keep the existing canonical-name/alias rules and SQLite search for exact filters; a shared application service composes them. Check Windows installation as part of the Windows milestone because RapidFuzz has a native component. If the corpus outgrows local candidate ranking, consider SQLite FTS5 as a later retrieval optimization, not a first feature.

### Search tasks for Luna

1. **Search contract and examples:** capture common misspellings, Arabic/English variants, aliases, duplicate names across entity types, short codes, and ambiguous account-versus-Counterparty cases. Agree on ranking and visible labels before changing pickers.
2. **Shared matching service:** normalize harmless case, spacing, punctuation, and script-specific marks; rank exact, alias, prefix, token, substring, and RapidFuzz suggestions. Return entity IDs, type, label, context, and match reason. Do not auto-select from fuzzy matches.
3. **Scoped pickers:** apply the shared service to account transfer selection, Counterparty and custody-owner selection, categories, and investment instruments. A chosen option carries its ID; typed text alone is not an identity decision when ambiguous.
4. **Search pages and global entry:** add a visible global search for destinations/records and compact search controls for Accounts, People, Counterparties, Reserves, and investment lists. Group and label results; support keyboard and screen-reader selection.
5. **Transaction history and import:** preserve exact date, amount, and ref filters; let name queries find transactions through matched Counterparty aliases, account IDs, and category IDs. Reuse suggestions in CSV review, requiring confirmation before linking. Keep import matching of duplicate transactions a separate later workflow.
6. **Verification:** test zero results, near ties, 1–2 character queries, Arabic and English text, large histories, archived records, custody exclusions, and transfer safety. Measure response time on a realistic local database. Windows installation is a required release check for the new dependency.

## Windows readiness milestone

Lightning is a Python/FastAPI/SQLite local web app, so the product code does not need a Windows rewrite. `run.bat` already creates a virtual environment and starts `python -m lightning`. That launcher and the full workflow have not been verified on a native Windows machine in this repository. Treat Windows as **provisional**, not as shipped support.

1. **Startup:** make `run.bat` choose Python 3.11+ deliberately, stop with a useful message if environment creation or dependency installation fails, and avoid reinstalling packages on every launch unless requirements changed. Preserve a visible terminal/error log when startup fails.
2. **Time zones:** include the `tzdata` dependency required for reliable `ZoneInfo("Africa/Cairo")` use on Windows, then verify quote dates and month-end valuation dates.
3. **Data and file paths:** test a fresh checkout in a normal user-writable folder, a path containing spaces, and a custom `--db` location. Confirm SQLite migrations, backups, CSV import/export, templates, fonts, and the local instrument catalogue. Decide on a per-user data directory before producing a machine-wide installer; the current default database is under the project folder.
4. **Native Windows smoke test:** use a clean Windows 10/11 environment with Python 3.11+; launch by double-click, complete setup, create accounts, post/edit/restore transactions, import a CSV, create a budget and reserve, record an investment, restart, and restore from a backup. Test another launch while the server is already running and an occupied port.
5. **Distribution:** after that test passes, publish a Windows setup guide and choose between a simple source checkout plus launcher or a packaged installer. Packaging is a later convenience, not a prerequisite for a usable Windows version.

Acceptance: a new Windows user can install prerequisites, double-click the launcher, open the local app, retain data across restarts, and complete core money workflows without using a shell. The same cross-platform test suite stays green, and Windows-specific results are recorded before claiming support.

## Working agreements

1. Check `git status` first and preserve existing user changes and personal data.
2. Keep business rules in Python services/workflows; cross-module writes belong in one DB transaction.
3. Schema changes require a new migration; never rewrite an applied migration.
4. Test the changed workflow and invariants; check import boundaries and `git diff --check`.
5. Log implementation changes under `Unreleased`; version/release headings change only when shipping.
6. Update this overview, architecture, or glossary when the owner asks, keeping all three consistent.
