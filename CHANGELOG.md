# Changelog

Every change to Lightning is recorded here — newest first. Dates are `yyyy-mm-dd`.

**How to log a change**

- Add it under `## [Unreleased]`.

## [Unreleased]

### Fixes from the Omar v7.1 re-run · 2026-09-30
- Skipping a loan payment no longer forgives it: the payment moves to the end of the loan ("Move to the end of the loan"), and skipped payments show on Loans and Recurring with an undo.
- Amounts and dates accept Arabic-Indic digits (٦٠٠, ٥/١٠) and the Arabic decimal and thousands marks.
- Opening a budget month that hasn't started returns to this month with an explanation instead of an error.
- Popup actions (mark paid, skip, stop, undo) always show a confirmation.
- Plan items with paid history show **Stop** instead of Delete, with matching confirmation text. Editing a loan says First due date and Number of payments.
- The Budget summary shows the loan payments included in Planned. The Plan tab's loans link reads "See your loans".

### Cash planning fixes from the Omar re-run · 2026-09-30
- A loan adds its payments to the budget: while Personal › Loan payments (or the loan's category) has no budget rule, it is planned at the payments scheduled that month. It ends when the loan ends; setting an amount replaces it.
- Safe to spend and the cash forecast no longer count a due bill twice (once as a bill due, again as budget still to spend). Income that is due but not received stays in this month's forecast.
- "Left in plan this month" on the Plan tab is now **Left in plan after bills** (Left in plan − Bills inside the plan), so it no longer shares a name with the Budget's Left in plan.
- "Already in your transactions?" only suggests the same counterparty, the same category, or an amount within 10%.
- The pay and item forms list banks and wallets first, then brokerage, and no longer offer deposits.
- Account pages say **In this account · What you own · Held for others** instead of Total · Yours.

### One name and one calculation per figure · 2026-09-30
- Every reported figure now has one name, one meaning and one formula (`lightning/core/figures.py`, mirrored in the Glossary). Derived figures show their formula under them, e.g. "Free cash = Cash you own − Reserves − Bills due".
- One position calculation (`lightning/planning/position.py`) feeds the Overview, Birdview, Investments, Settings, Reserves and the cash forecast. The tabs no longer re-add balances their own way.
- One **Average monthly income** (`BudgetService.income_average`): the budget, emergency-fund coverage and the cash forecast use the same categories, months and manual override. Before, Reserves averaged salary over six months and the forecast averaged all income over three.
- Investments' after-sale estimate now applies the same sale factors as Birdview (95% when unset). It is now **Holdings after sale (estimate)**; before, it added holdings at full value. "Liquidation factor" is now **sale factor**.
- What you own adds up the same way everywhere: Cash you own + Deposits + Holdings value + Other you own. Birdview no longer groups deposits with investments.
- Renamed on screens (full list in the Glossary):
  - All accounts / Gross balances → In your accounts
  - Money from others → Held for others
  - Liquid cash / Owned liquid cash → Cash you own
  - Investment cash → Brokerage cash
  - Assigned reserves → Reserves
  - Estimated liquid investments → Deposits and holdings after sale (estimate)
  - Cashflow → Net flow
  - Invested capital → Cost
  - Period result / Investment result → Result
  - Cash added and withdrawn / New money added → New money in (net on every tab)
  - Budgeted / Current budget → Planned
  - Left → Left in plan
- Entry forms use the same field names:
  - Held for (was Whom, Owned by, Owner)
  - Amount (was Total paid, Each payment)
  - Units (was Pieces, Quantity, Units you hold)
  - Cost (was What you paid in total)
  - Account and Cash account (was Held in, Paid from, Paid into)
  - Counterparty (was Paid to, From)
  - As of (was Price date, Statement date)
  - Due date (was Next date)
  - Type (was Kind, Action)
  - Notes (was Details)
  - Fees (the checkbox is now "Fees are extra")

### Cash planning · 2026-09-30
- Reserves became **Cash planning** with four sub-tabs: **Plan** (safe to spend until the next income, what you owe, the next 30 days, a three-month cash forecast), **Recurring** (bills, subscriptions and income, with suggestions from payments that repeat in your history), **Loans** (loans and installment plans with progress and payoff date) and **Reserves** (the previous page). `/reserves` now opens `/plan/reserves`.
- Scheduled payments are marked paid automatically when exactly one posted transaction matches; otherwise pick the transaction, record the payment, or skip it. Voiding the transaction makes the payment due again.
- **What you owe** (bills due + loans still to pay) is shown as its own item: bills due come off free cash, and the Overview and Birdview show **Net worth** = what you own − what you owe. Forecasts never change either figure. The free-cash integrity check now includes bills due.
- Loan payments count as spending: a new loan defaults to **Personal › Loan payments** (migration `0035_loan_payments_category.sql`), so its payments show in the budget and cash flow; paying one also lowers loans still to pay, so net worth is unchanged.
- Migration `0034_cash_planning.sql` adds `planned_items` and `planned_payments`. Also recorded: `0033_reserve_account_matching.sql` links reserves to a payment account.

### Guideline 2.1 controls, month reports and report fixes · 2026-09-30
- Buttons follow the guideline: 48 px pills on pages and 36 px inside cards and rows; the date button and month arrows are 48 px circles. Textareas keep a 96 px minimum.
- Every date reads `yyyy-mm-dd` (hints, placeholders, period labels, the investments chart and Reserves use `yyyy-mm`). The period control is one `‹ yyyy-mm ›` stepper, and custom reports take a from/to month; Enter keeps the selected period.
- Screens use a true minus (−5,000.00); big figures shrink to their tile instead of breaking mid-number; the cash-flow figure no longer runs into the savings ring; the register's date and notes fields fit.
- CSV import: a merchant typed as new on several rows is created once; a row error no longer crashes the review (500), and the error view lists only the rows to fix.
- Emergency-fund coverage averages salary over the months that received it, instead of always dividing by six.
- "Returns by asset class" and "Biggest movers" include holdings sold out during the period.
- Revaluations replaced by the engine no longer appear in Deleted transactions and can't be restored into duplicates.
- "Add existing holding" on a physical item no longer asks for a cash account; the XIRR row waits for a year of holdings; a yearless date like 30/9 no longer jumps to last year; Birdview names deposits with investments ("Investments and deposits"); wording and favicon fixes.

### Uniform controls and date fields · 2026-09-29
- Buttons, text and number fields, dropdowns, month boxes and segmented toggles share one font, a 40 px height (30 px for small buttons), one border and an 8 px radius; checkboxes keep their natural 16 px size.
- Every date field is the same component: a typeable ISO box (`31/1`, `31/1/2026` or `2026-01-31`) with the same calendar button, including the register, CSV review, reconcile, data checks, custom periods, prices and physical items. Dates are normalised on submit as well as on blur.
- The register date column fits a full date; the settings carryover month uses the `yyyy-mm` box; the Birdview class popup keeps only the dialog's close button.

### Overview information flow · 2026-09-29
- Replaced the mixed card grid with six ordered, divided sections: wealth, available cash, period cash flow, attention, expenses and investments.
- Expanded cash and reserve amounts now reveal contributing balances inline; expense category links preserve dates, and investment results use the selected period.
- Removed the three-item attention limit and included spending above zero-value plans.

### Product workflow pass · 2026-09-28
- Reworked the main pages around focused questions, quiet number-led cards, consistent expandable category rows, and shared comparison/progress/time-series visuals. Added the application brand specification and live-styled component reference.
- Replaced Management navigation with a Settings hierarchy for counterparties, categories and data checks; added distinct sidebar icons and clearer account grouping.
- Corrected monthly Budget scope and exposed spending outside listed groups; preserved category scope in expense totals and trends; repaired saved CSV mapping, custody import and counterparty deletion workflows. Moved UI SQL behind services.
- Defined task ownership, follow-up paths, shared components, and visualization rules in `docs/PRODUCT_UX_ARCHITECTURE.md`.
- Recorded previously added migrations: `0029_birdview_class_factors.sql` stores liquidation factors by asset class; `0030_investment_targets_by_class.sql` links allocation targets to asset classes; `0031_dividend_asset_reference.sql` records the investment asset associated with dividends.
- Completed the prior migration log: `0024_reevaluation_ownership.sql` adds ownership-aware reevaluation entries; `0025_reserve_category_matching.sql` links reserves to categories; `0026_reserve_allocation_history.sql` records dated allocations; `0027_investment_planning.sql` adds allocation targets and asset planning metadata; `0028_budget_rules_and_resets.sql` adds income-percentage rules and carryover resets.

### UX review pass · 2026-09-28
- Main tabs share summary-first layouts and expandable calculation details; secondary account actions are grouped for review.
- Account CSV import includes a copyable AI preparation prompt, CSV template, and downloadable counterparty/category matching reference. Copy works in import popups with a manual fallback.
- Registers export their filtered posted cash activity for external analysis, with account, currency, type, linked-account and ownership context. Text fields are protected from spreadsheet formula interpretation.
- Added tab review notes and a prioritized comparison with YNAB, Monarch and Simplifi in `docs/UX_REVIEW.md` and `docs/BUDGET_APP_GAPS.md`.

### Changed
- Ledger lines can carry an optional owner. Linked legacy cash and investment custody entries migrate to owner-tagged lines, owner balances are checked across dated postings and edits, and brokerage buys must use cash from the brokerage account and the selected owner's balance.
- `0022_physical_items.sql` adds named physical items and dated item valuations; `0023_ledger_ownership.sql` adds ledger-line ownership.

### Fixed
- Counterparty management is now linked in the sidebar; canonical names and aliases can be edited, and delete removes unused records or archives records referenced by transaction history.
- Re-uploading a previously imported CSV creates a new review attempt; duplicate matches are warnings users may skip or explicitly approve, and voided/deleted transactions no longer count as active duplicates.
- Cross-account transfer matching now compares signs from the imported account's point of view, flagging the opposite statement leg as a likely duplicate.
- CSV uploads now pause at a prefilled field-mapping step before row review; review submissions scale Starlette's form-field limit to the staged rows, and Post rows is available above and below the list.
- Revaluation checkpoints are revisited after investment trades are voided, preserving fee details during trade edits, and record-level money values retain cents. Static asset versions are bumped with UI changes.
- Database migrations `0012_custody_transaction_links.sql`, `0013_reevaluation_ledger.sql`, `0014_preserve_category_codes.sql`, `0015_reevaluation_source_hash.sql`, `0016_reconciliation.sql`, `0017_cash_reserves.sql`, `0018_reserve_spending.sql`, `0019_recurring_reserves.sql`, `0020_reserve_counterparty.sql`, and `0021_budget_carryover.sql` are tracked here.
- Date fields now accept day/month input such as `31/1`, infer the current year, and normalize to ISO; CSV rows accept the same format.
- Account setup now records an optional starting balance as an opening entry on an explicit date, so it is not reported as income; the welcome steps explain this flow.
- The all-accounts register has a deleted-transactions page with direct restore actions, and changing a transaction's kind explains that the original reference remains in history.
- Investment quick entry now asks for Buy, Sell, or Dividend and takes positive units for both buys and sells.
- CSV review counts uncategorized rows before posting, and register labels clarify that the field is for who money went to or came from.

- Monthly investment checkpoints now detect changed historical trades and prices, void superseded system journals, and rebuild linked return entries; sale-day checkpoints value remaining units at the forced sale price.
- Counterparty default categories now resolve regardless of capitalization, and the all-accounts register reserves a separate, labeled action column for Add.
- Money entry rejects ambiguous decimal commas, exponent/underscore notation, and amounts too large for safe storage. New ledger money/base totals are limited to cents; app money displays round to whole currency units while entry fields retain cents.
- Invalid month, investment-price date, and category-parent URL values now receive safe validation instead of overflowing or raising a server error.
- Investment fee details stay hidden unless the user ticks “Fees are excluded from the total”; the select menu is removed.
- Account management is now directly reachable from the sidebar, including inactive accounts.

### Added
- Defined a consistent, typo-tolerant search workflow and identity-safety contract across Lightning in the three canonical docs, using an existing open-source matcher for candidate ranking.
- CSV imports are no longer capped by row count (the 5 MB file-size limit remains).
- Documented the native Windows readiness milestone and current launcher, time-zone, and data-location gaps in the three canonical docs; Windows support remains unverified.
- CSV import now supports either one signed amount column or separate inflow/outflow columns; mapped statement rows merge into a single signed Amount before review.
- Categories can be selected individually or in bulk for activate/archive/delete actions; deleting a category with history or references archives it instead.
- Consolidated the budget workflow, UI audit/tasks, user-question map, and milestone roadmap into the three canonical docs; added last-updated, document-revision, and app-version metadata to each.
- Split the UI workflow audit into ordered, bounded implementation tasks for Luna, with acceptance criteria and a separate check for the conflicting asset breakdowns.
- Budget now starts with a history-based plan preview or one broad limit, then opens on monthly status with attention items, free-cash context, transaction feedback, and optional spending-limit carryover.
- Added read-only integrity checks for gross versus owned/custody balances, account-level ownership splits, expense and budget totals, reserves, and the net-worth bridge; missing valuations are shown as incomplete.
- Corrected budget actuals so income categories no longer reduce reported money-out totals.
- Audited the customer workflow and UI hierarchy across Overview, Birdview, Accounts, Budget, Reserves, and import; documented which controls to remove, relocate, or keep and a phased UI redesign.
- Defined the budget customer-flow milestone: one-action plan setup, everyday status and transaction feedback, optional spending-limit carryover, and a month review; cash reserves remain separate from budget limits.
- Documented the user questions Lightning should answer, the follow-up drilldowns for each, and the next Birdview history/performance milestone, including the role and limits of XIRR.
- Birdview replaces Investments in the main navigation with current owned assets, a configurable investment liquidation factor, cash reserves/free cash, income and spending timelines, and capital/return breakdowns by investment type and holding.
- Cash reserves for emergency funds and planned projects, with recurring due dates, optional Counterparty matching, payment links, and free-cash calculations; custody transactions never auto-link.
- Statement reconciliation lets users mark cash transactions cleared and compare the cleared balance with a statement amount.
- Expense transactions can be split across categories, and refunds reduce spending in the original expense category instead of inflating income.
- Confirmed Counterparty aliases are manageable from the Counterparties page, capped at 10 per Counterparty, and offered in register and CSV search.
- CSV review can remember a confirmed category for future transactions from that Counterparty.
- Activity-ledger categories organized as Personal, Work, or Investment, with up to one user-defined detail level below each broad activity category; money direction no longer determines the category tree.
- Transaction multi-select and right-click delete actions, with audit-preserving deletion and restore.
- "Money from others" custody entries tied to an account and owner; outstanding balances are excluded from net worth and reconciled in the net-worth bridge.
- CSV import is available for all account types. Statement rows can be edited inline, and valid incomplete rows can post with safe uncategorized/optional-counterparty handling.
- Database migration `0011_money_from_others.sql` adds custody tracking and converts existing legacy receivable accounts to Other Assets.
- Database migration `0010_category_families.sql` stores category families and migrates income activities into the Personal/Work/Investment tree.
- Canonical Counterparty records with normalized names, confirmed aliases, reusable default categories, and ranked approximate suggestions that never auto-merge. Bank import staging retains original source rows for review.
- Database migration `0008_counterparties.sql` adds canonical counterparties, aliases, transaction links, and bank-import batch/row staging.
- Database migration `0009_import_column_maps.sql` remembers a confirmed CSV header/sign mapping per bank account.
- Best-effort investment quote refresh runs when Lightning starts, saving supported Yahoo Finance quotes to
  price history so portfolio values and unrealized gains recalculate from the newest quote. Stocks and funds
  use their ticker with Yahoo's CA suffix; unsupported symbols keep their prior saved valuation.
- Budget planning can use a rolling average of the previous 3 or 6 complete months of spending for a category
  or group. The method repeats until changed; this-month-only overrides still work. Existing manual budgets remain.
- Database migration `0007_budget_averages.sql` stores the selected calculation method.

### Changed
- Account opening dates no longer restrict historical transaction entry, editing, or restoration; valid past-dated activity can be added at any time.
- Removed "Money owed to me"/receivable accounts from the active account model and choices; the app has no receivables workflow.
- CSV import review no longer requires a separate Counterparties resolution screen; corrections are made on the transaction rows.
- Investment-account names now appear in the left sidebar without internal account codes.
- Account codes no longer appear beneath account names in the sidebar or account register heading, or beside
  account names in the account list and account edit heading. Account names are sufficient in these views.
- Roadmap places searchable Egyptian investment catalogue before daily wealth history and return breakdowns.

---

## [0.3.0] — 2026-09-25 — M3 Investments, new register

### Added — M3 Investments (manual)
- **Investments** you can hold: stocks, funds (equity, money market, gold, other), gold and other — created with a
  kind and symbol; codes `STK:COMI`, `FND:AZ-GOLD`, `GLD:21K`. Units follow the kind (shares whole, fund units
  4 decimals, gold grams 3 decimals, gold karat → purity).
- **Buy, Sell, Dividend** and **"Holding I already own"** (units + what you paid in total, for existing positions).
  Buy/sell use the broker's own cash (THNDR) or another account (e.g. wallet pays for gold at home).
- **Positions** from the ledger, average cost (as THNDR shows): cost basis incl. buy fees, realized gain on sells
  (after sell fees), unrealized gain, dividends per holding, total return; allocation by asset class and by
  exposure (a gold fund counts as gold).
- **Prices**: "Update prices" page (one date, a box per investment). Valuation uses the newest of a typed price
  and the last buy/sell price (a typed price wins on the same day); holdings entered as already owned are
  valued at cost until priced, marked "at cost". Price changes flow into the net-worth bridge as revaluation.
- **Investments page** (`/investments`): value, invested, unrealized, total return, holdings table, allocation,
  sold-out positions. Account pages of brokerage / gold-at-home accounts show a Holdings strip and
  Cash · Holdings · Total, with Buy / Sell / Dividend buttons.
- "Physical asset (e.g. gold at home)" account type is now offered.
- New `investments` module (builds lines, calls `TransactionService.post()`); `AssetService.create_investment`,
  `set_price(s)`; `TransactionService.post()/repost()` for documents built by other modules.
- Docs: `PROJECT_OVERVIEW.md` rewritten for 0.3.0; glossary and architecture notes updated.

### Changed — the register (owner feedback)
- Its own design (not Actual's): a quick-add row, coloured edge per kind (in, out, transfer, investment, opening),
  a date shown once per day.
- **One Amount column**: positive = money in, negative = money out (replaces Payment / Deposit).
- **"To"** replaces "Payee". Typing or picking one of your accounts in To makes the row a **transfer** automatically
  (the Category box is not needed and is disabled).
- **Category is a type-and-pick box** (a list of matches while you type), not a dropdown. It accepts the full name
  ("Personal › Food & Groceries"), the short name, a unique part of it, or the code; ambiguous names ask "Which one?".
- The account register lists **cash only**; investment lines appear in holdings. Buys show as money out with
  "Buy 150 × STK:COMI @ 92.4 + fee 45.00".
- Sidebar groups accounts by kind: Cash & bank · Deposits · Investments · Other (values include holdings).

### Fixed / rules
- A holding can never go below zero units at any date — enforced on sell, edit, void and restore.
- An account's cash opening balance and each holding's starting amount are separate (`OPN` per cash or per holding).
- Holding values are kept at full precision (rounded only on screen), so net worth = cash + Σ units × price exactly.

### Decisions
- 2026-09-25 — Average cost; buy fees go into cost; sell fees reduce what you receive (owner, THNDR style).
- 2026-09-25 — Buys and sells are conversions: their lines net to zero at cost/proceeds, so gains appear as
  revaluation in the net-worth bridge and as realized/unrealized in the portfolio view.
- 2026-09-25 — Register: one signed amount, "To" (an account there = transfer), typed categories (owner).
- Dividends link to their investment through the cash line's memo (the investment's code).

---

## [0.2.0] — 2026-09-25 — Register, budgeting, simplification

### Added
- GitHub-ready: `.gitattributes` (keeps `run.bat` in Windows line endings), README section on cloning to
  another computer; `data/` stays out of Git so finances are never uploaded.
- `docs/PROJECT_OVERVIEW.md` — detailed hand-off brief: purpose, terminology, architecture, data model,
  ledger rules, service APIs, UI routes, roadmap, decisions log and rules for future changes.
- **Account register (Actual-style):** each account page is now a register with an entry row on top —
  Date · Payee · Category · Notes · Payment · Deposit — press Enter to save and the row is ready for the next one.
  Transfers are picked from the same list ("Transfer ↔ another account"). Clicking a row opens it.
- Payee memory: typing a payee used before fills in the category used with it last time.
- `TransactionService.record_in_account()` turns one register row into money out, money in or a transfer.
- **Actual-style layout:** the sidebar lists every account with its balance, grouped like the dashboard
  (Liquid Cash, Deposits…), with an "All accounts" total and "+ Add account".
- **All accounts register** (`/transactions`): every account in one register, one row per account touched,
  with an Account column; new rows pick their account in the entry row.
- **Edit in place:** click a row and it becomes editable — Save, Cancel (Esc), Void, Details & history.
  If an edit changes the kind (e.g. a transfer becomes money out) the old one is voided and a new one recorded,
  so a ref's prefix always tells the truth. `TransactionService.update_in_account()`.
- Register toolbar: "+ Add New", search (payee, notes, category, amount, ref) and a month filter.
- **Budgeting** (new `budgeting` module, `/budget` page, "Budget" in the sidebar):
  - budget vs actual per month for money-out categories, in two sections: **Personal** and **Work**;
  - budgets on a group (Personal 20,000 — the ceiling) or on categories (Food 6,000 — part of it);
    a group without its own amount shows the total of its categories; a warning when categories exceed their group;
  - **repeat until changed**: an amount applies from its month onward; "Apply to this month only" for one-offs;
  - Budgeted · Spent · Remaining · Money in tiles, per-line progress bars, over-budget in red,
    "spent without a budget", and Spent links straight to those transactions;
  - Overview shows a Budget card (Personal / Work progress).

### Changed
- **Savings = bank account.** One type "Bank account (current or savings)". "Deposit" now means a
  certificate / time deposit (CD), reported under Deposits › CDs / Time Deposits.
- **Where an account appears on the dashboard now follows its type.** The "Report cash in this account as"
  picker is gone; the form shows the result in words (e.g. "Liquid Cash › Bank Balance").
- **Screens show plain names instead of codes** for categories and asset classes
  ("Personal › Food & Groceries", "Liquid Cash › Physical Cash"). Account codes still appear with names.
  Codes remain in search, the ledger detail and the database views.
- **Categories page redesigned:** one block per group, categories as clickable chips, one "+ Add" per group;
  codes moved into an optional field on the edit form; system categories hidden.
- Dashboard renamed **Overview**; tiles: Net worth · Money in · Money out · Left over.
- Register columns follow Actual: Date · Payee · Notes · Category · Payment · Deposit · Balance.
- Generated codes keep whole words ("Cash at hand" → `CASH-AT-HAND-CSH-EGP`, not `CASH-AT-HA-…`).
  Existing codes are not changed — rename them from the account's edit page if you like.
- Opening balances cannot be negative.

### Fixed
- An account's start date can no longer be moved after its first transaction (the review's gap #1).
- **No more future dates:** transactions and account start dates cannot be after today, so every balance has
  one meaning ("today"); the "including entries dated after today" note is gone. Scheduled payments will come
  as recurring transactions (M7).

### Removed (architecture simplification)
- **Stored search text and the full-text index.** Search now reads transactions, accounts and categories
  directly (ref, date, payee, description, notes, account, category, amount), so nothing derived is stored and
  nothing can go stale. This also removes the search rebuild on renames and the whole category workflow.
- `ledger_entries.claim_id` and `transactions.import_batch_id` (their milestones, M5 and M7, will add them),
  the unused `DRAFT` status, and the empty `integrations/` placeholders.

### Removed
- The separate Money out / Money in / Move money form pages and the old transactions list — the register replaces them.
- **Liabilities.** Credit card, loan / installments and "money held for others" account types, the
  Liabilities asset classes, and all "amount owed" logic. Lightning tracks what you own.
- The "Savings / Interest-bearing" asset class (savings accounts are bank accounts).

### Decisions
- 2026-09-25 — No liabilities (owner). Card or loan payments are recorded as money out from the paying account.
- 2026-09-25 — Savings and current accounts are the same type (owner).
- 2026-09-25 — Codes are for data; screens use names, except account codes which always travel with the name (owner).
- 2026-09-25 — Account pages work like Actual Budget: one ledger underneath, filtered per account (owner).
- 2026-09-25 — Screen structure follows Actual: accounts sidebar + register (owner). Schedules, import and the
  cleared tick come with their milestones (M7 recurring, M7 import, M2 reconciliation), not as placeholders.
- 2026-09-25 — Budgeting (owner): budget vs actual (no rollover), budgets at either level, repeat until changed,
  Personal and Work as separate sections. Actuals always come from the ledger; only budget amounts are stored.
- 2026-09-25 — Architecture review simplifications applied (owner). Kept on purpose: price and asset fields
  (M3 investments is next) and `sort_order` (keeps asset classes in a meaningful order, e.g. Liquid Cash first).

### Schema
- `0006_simplify.sql` — drops the full-text index, its triggers and `transactions.search_text`,
  `transactions.import_batch_id`, `ledger_entries.claim_id`. No financial data changes.
- `0005_budgets.sql` — `budgets` (category × month × amount, repeating or this-month-only) and a readable `v_budgets` view.
- `0004_bank_and_no_liabilities.sql` — savings accounts become BANK; every account's reporting group is reset
  from its type; unused Liabilities and Savings asset classes removed. Stops without changing anything if a
  credit-card, loan or held-for-others account exists.

---

## [0.1.0] — 2026-09-25 — M0 Foundation + M1 Cash & bank basics

### Added — M0 Foundation
- Project skeleton as a modular monolith: `core`, `database`, `assets`, `categories`, `accounts`,
  `transactions`, `reporting`, `workflows`, `integrations`, `ui`.
- Exact money handling: `Decimal` everywhere; stored as integers ×1,000,000 (`_e6` columns).
- ISO dates (`yyyy-mm-dd`) enforced on input, storage and display.
- Readable identities: account codes (`CIB-CUR-EGP`), asset codes (`CASH:EGP`), dotted category and
  asset-class codes (`EXP.WORK.SOFTWARE`), and fixed document refs (`OUT-2026-09-25-003`, lines `/1`).
- Posting engine (`core/ledger.py`): internal lines must net to zero; money in/out needs a category.
- Plain-SQL migrations with a `schema_migrations` table; optional FTS5 search migration with LIKE fallback.
- Seed data: asset-class tree, cash assets (EGP, USD, EUR, GBP, SAR, AED), category tree.
- Audit log for every edit, void and restore.
- Automatic backup on start (`data/backups/lightning_yyyy-mm-dd_HHMM.db`, newest 30 kept) and a
  "Back up now" button.
- Architecture rules enforced by `import-linter` (4 contracts) and tests.
- `CHANGELOG.md` (this file) — every change is logged here; a test checks each version and migration is listed.

### Added — M1 Cash & bank basics
- Accounts: cash wallet, bank, savings/deposit, brokerage, money owed to me, credit card, loan,
  money held for others. Codes suggested automatically; last 4 digits only.
- Opening balances recorded as `OPN` transactions; liabilities entered as "amount owed".
- Money in, money out and transfers, with edit (ref never changes), void and restore.
- Credit cards and loans work as balances: spending on a card is money out; paying it is a transfer.
- Search across ref, date, accounts, categories, amount, payee, description and notes (Arabic works).
- Reports: net worth (total, by account, by asset class), net-worth bridge, cash flow
  (household vs investment income, personal vs work spending), spending by category, 6-month trend,
  account statement with running balance.
- HTML app (FastAPI + Jinja2, no build step, works offline): dashboard, accounts, transactions,
  categories, settings. Light and dark mode, phone-friendly.
- Windows launcher `run.bat` (macOS/Linux `run.sh`).
- 100+ automated tests, including a randomized 300-step ledger test for the net-worth equation.

### Decisions
- Accounts (where) and financial assets (what) are separate; cash is classified by the account
  holding it (`cash_class`), investments by the asset.
- One ledger: transactions (documents) → ledger entries (lines). Every balance and report is derived.
- Net-worth equation: closing = opening + money in − money out + revaluation + new balances added.
- No `opening_balance` field on accounts and no `include_in_net_worth` flag (it would break the equation;
  pass-through money belongs in a "Money held for others" account instead).
- Edits happen in place with an audit trail, not by reversal entries.
- Plain `sqlite3` + SQL files instead of SQLAlchemy/Alembic.
- M1 is EGP-only; other currencies wait for FX rates in M4.
- Balances on screen are "as of today"; future-dated entries are shown separately.
- Edit and void moved from M2 into M1 (the app is not usable without them).

### Schema
- `0001_initial.sql` — settings, asset_classes, financial_assets, accounts, categories, transactions,
  ledger_entries, price_history, fx_rates, audit_log.
- `0002_search.sql` — FTS5 full-text index on transactions (optional).
- `0003_readable_views.sql` — `v_ledger`, `v_balances` for browsing the file.
