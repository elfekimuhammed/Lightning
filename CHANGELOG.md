# Changelog

Every change to Lightning is recorded here — newest first. Dates are `yyyy-mm-dd`.

**How to log a change**

- Add it under `## [Unreleased]`.

## [Unreleased]

### Added
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
