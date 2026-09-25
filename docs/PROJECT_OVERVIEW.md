# Lightning — Project Overview (hand-off brief)

> Status: version 0.2.0 (register, budgeting, simplification) — see CHANGELOG.

> Read this first. It is written so that a developer — or an AI assistant starting a fresh session —
> can understand what Lightning is, how it is built, why it is built that way, and how to extend it
> without breaking it. Version described: **0.2.0, 2026-09-25**.
> Companion docs: `docs/ARCHITECTURE.md` (short form), `docs/GLOSSARY.md` (terms and codes),
> `docs/MILESTONES.md` (plan), `CHANGELOG.md` (every change).

---

## 1. What Lightning is

Lightning is a **local, single-user personal-finance application** written in Python. It combines, in one
system: account tracking, money in/out (budgeting base), transfers, investment tracking, reimbursements,
asset allocation and net-worth tracking. Only the first two milestones are built so far (see §11).

**The owner and context.** Built for El Feki (a GL architect / finance lead in Egypt). The base currency is
**EGP**. Typical accounts: a cash wallet, CIB current account, QNB savings, bank CDs, a THNDR brokerage
account and physical gold. **Debts (credit cards, loans, installments) are out of scope** by owner decision. Design choices borrow from
accounting practice (Odoo-style document → journal lines, opening-balance entries, receivables), but none of
that jargon is shown to the person using the app.

**The central idea — two separate questions:**

1. **Where is the wealth held?** → **Accounts** (wallet, CIB Current, THNDR, gold at home).
2. **What does the wealth consist of?** → **Financial assets** (EGP cash, COMI shares, a gold fund, 21K gold grams).

They are never merged. THNDR is a *brokerage account*; what is inside it (cash, stocks, funds) are its
*holdings*. "THNDR = Stocks" is always wrong.

**The owner's stated priorities (they drive every decision):**

1. **Ease of use** — anyone can use it; no debits/credits, no accounting words on screen.
2. **Defined terminology** — every term (account, financial asset, category, …) has one meaning (§3).
3. **Good data structure and indexing** — human-readable identifiers, fast search, clean storage (§6).
4. **Good code structure** — modular monolith with enforced boundaries (§4).
5. **Workflows that cover normal cases** — salary, groceries, ATM, investing, reimbursements… (§8, §11).

Other standing rules: dates are always **`yyyy-mm-dd`**; an account (or any) **code is always shown with its
name** (`CIB-CUR-EGP · CIB Current`); **every change is logged in `CHANGELOG.md`**.

---

## 2. Technology

| Concern | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.11 (uses `StrEnum`) | Owner's choice |
| Storage | SQLite, one file `data/lightning.db` | Simple local deployment, easy backup |
| DB access | Plain `sqlite3` + numbered `.sql` migration files | Readable schema, few dependencies (SQLAlchemy/Alembic rejected) |
| Money | `decimal.Decimal`; stored as integers × 1,000,000 | Exact sums in SQL; floats forbidden |
| Web UI | FastAPI + Jinja2 server-rendered HTML + ~40 lines of vanilla JS | "HTML first", no build step, works offline |
| Server | uvicorn bound to `127.0.0.1` only | Never exposed to the network |
| Search | Plain `LIKE` over transactions, accounts and categories at query time | Nothing derived to keep in sync; instant at personal scale |
| Tests | pytest (102 tests), FastAPI TestClient | |
| Architecture checks | import-linter (4 contracts in `pyproject.toml`) | Keeps module boundaries honest |
| Launch | `run.bat` (Windows) / `run.sh` → `python -m lightning` | Double-click start; auto venv + install |

Runtime dependencies: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`. Dev: `pytest`, `httpx`, `import-linter`.

---

## 3. Terminology (the vocabulary used in code, DB and UI)

| Term | Meaning | Example |
|---|---|---|
| **Account** | A place where value is held | `CIB-CUR-EGP · CIB Current` |
| **Financial asset** | A specific thing you own a quantity of | `CASH:EGP`, `STK:COMI`, `GLD:21K` |
| **Asset class** | Editable tree grouping financial assets (what wealth is made of) | `FUND.GOLD · Gold Fund` |
| **Holding** | Quantity of one asset in one account — *always calculated*, never stored | THNDR holds 100 COMI |
| **Category** | Editable tree of *why* money moved | `EXP.PERSONAL.FOOD · Food & Groceries` |
| **Transaction** | The document a person sees/edits (one transfer = one transaction) | `TRF-2026-09-26-001` |
| **Ledger line / entry** | One effect of a transaction on one account + asset | `TRF-2026-09-26-001/2` |
| **Money in (inflow)** | Value entering your finances from outside | Salary, interest |
| **Money out (outflow)** | Value leaving your finances | Groceries, fees, tax |
| **Transfer** | Money moving between two of your own accounts; never income/expense | CIB → THNDR |
| **Conversion** | Swapping one asset for another inside your finances (M3/M4) | cash → shares, EGP → USD |
| **Revaluation** | Value change with no money moving (M3/M4) | share price 50 → 55 |
| **Opening balance** | What an account held when tracking started (an `OPN` transaction) | |
| **New balances added** | Opening balances of accounts started inside a reporting period | |
| **Net worth** | Everything owned (debts are not tracked) | |
| **Register** | An account page: its transactions with an entry row on top (Actual-style) | |
| **Receivable** | Money owed to you (asset) | pending reimbursement (M5) |
| **Void** | Cancelled but kept; excluded from balances; can be restored | |

**"Category" vs "asset class"** — deliberately two words. *Category* = why money moved (income/expense tree).
*Asset class* = what the wealth is (Liquid Cash, Deposits, Stocks, Funds, Gold, …).

---

## 4. Architecture — a modular monolith

One process, one database file, modules with **hard, tested boundaries**.

### 4.1 Layers (top may import bottom, never the reverse)

```
lightning.main            entry point: backup → migrate → seed → serve; opens the browser
lightning.ui              FastAPI routes + Jinja2 templates + static CSS/JS
lightning.bootstrap       composition root: builds Database and wires every service (Container)
lightning.workflows       multi-module actions, each inside ONE database transaction
lightning.budgeting       budget amounts per category × month; budget vs actual (actuals read via reporting)
lightning.reporting       read-only reports; owns no tables
lightning.transactions    records/edits/voids/finds transactions; the ONLY writer of the ledger
lightning.accounts        where value is held
lightning.assets | lightning.categories    (independent siblings) what value is | why money moved
lightning.database        connection, migrations, seed, backup, audit log, settings
lightning.core            money, dates, codes, refs, posting rules — depends on NOTHING
```

### 4.2 Inside each business module

```
<module>/domain.py       plain dataclasses + enums (no DB, no UI)
<module>/repository.py   the module's SQL — touches only the module's own tables
<module>/service.py      the module's public API (what other modules and the UI call)
```

### 4.3 Enforced contracts (`pyproject.toml` → `lint-imports`, also run by `tests/test_architecture.py`)

1. **Layers** as listed in 4.1.
2. **UI never touches SQL or repositories** (forbids `lightning.database`, every `*.repository`, `reporting.queries`).
3. **Modules use each other's services, never each other's repositories.**
4. **Workflows and reporting never write through the transactions repository.**

Plus tests: no `float(` in financial modules; no `SELECT/INSERT/UPDATE` text in UI Python files.

### 4.4 File map

```
Lightning/
├─ run.bat · run.sh                 launchers (venv + pip install + start)
├─ requirements.txt · requirements-dev.txt · pyproject.toml (pytest + import-linter config)
├─ README.md · CHANGELOG.md
├─ docs/ ARCHITECTURE.md · GLOSSARY.md · MILESTONES.md · PROJECT_OVERVIEW.md (this file)
├─ data/                            created at runtime: lightning.db + backups/ (git-ignored)
├─ lightning/
│  ├─ __init__.py (__version__)  __main__.py  main.py  bootstrap.py
│  ├─ core/        errors.py money.py dates.py codes.py refs.py ledger.py
│  ├─ database/    connection.py migrator.py seed.py backup.py audit.py settings.py
│  │               migrations/0001_initial.sql 0002_search.sql 0003_readable_views.sql
│  ├─ assets/      domain.py repository.py service.py
│  ├─ categories/  domain.py repository.py service.py
│  ├─ accounts/    domain.py repository.py service.py
│  ├─ transactions/domain.py repository.py service.py
│  ├─ reporting/   queries.py valuation.py service.py
│  ├─ workflows/   accounts.py categories.py
│  ├─ budgeting/   domain.py repository.py service.py
│  └─ ui/          web.py · routes/{dashboard,accounts,transactions,categories,settings}.py
│                  templates/{base,not_found}.html + dashboard/ accounts/ transactions/ categories/
│                  settings/ partials/macros.html · static/style.css app.js
└─ tests/          conftest.py + test_core, test_database, test_accounts_categories,
                   test_transactions, test_reporting, test_ui, test_architecture, test_changelog
```

---

## 5. The financial core (`lightning/core/`)

| File | Responsibility |
|---|---|
| `errors.py` | `LightningError(message, field)` → `ValidationError`, `NotFoundError`, `ConflictError`. Messages are plain language, safe to show on screen; `field` lets the form highlight the input. |
| `money.py` | `to_decimal` (accepts `"1,250.50"`, rejects floats/NaN), `check_places`, `quantize`, `to_e6`/`from_e6` (the only storage conversions; refuse precision loss), `fmt` (`1,234.50`, `-…`, `+…`). |
| `dates.py` | `parse_date` (strict `yyyy-mm-dd`, real dates only), `parse_month` (`yyyy-mm` → first/last day), `now_iso` (local time with offset), `today`, `previous_day`. |
| `codes.py` | Code validation/normalisation: account `A-B-C`, asset `CLASS:SYMBOL`, dotted path `A.B.C`; `slug()` for suggestions. |
| `refs.py` | `DocType` enum (`OPN IN OUT TRF CNV BUY SEL DIV VAL ADJ`), labels, `format_ref`/`parse_ref`, `line_ref`. |
| `ledger.py` | `Effect` enum, `PostingLine` value object (`PostingLine.cash(...)` helper) and **`validate_posting()`** — the rules below. |

### 5.1 Posting rules (`validate_posting`)

- At least one line; no zero-quantity line; ≤ 6 decimal places everywhere.
- `amount == quantity × unit_price` and `amount_base == amount × fx_rate` (rounded to 6 dp).
- **INFLOW / OUTFLOW lines must have a category.** OPENING lines must not.
- **All INTERNAL lines of a transaction must net to zero in base currency.**

### 5.2 Effects

| Effect | Meaning | Counts in cash flow? | Changes net worth? |
|---|---|---|---|
| `INFLOW` | value enters | yes (money in) | yes |
| `OUTFLOW` | value leaves | yes (money out) | yes |
| `INTERNAL` | moves inside your finances | no | no (nets to zero) |
| `OPENING` | pre-existing balance | no | yes (as "new balances added") |

---

## 6. Data model

### 6.1 Storage conventions

- **Identity has three layers:**
  1. internal integer `id` — relationships only, never shown;
  2. human **codes** for master data — editable because relationships use ids;
  3. **document refs** for transactions — `TYPE-yyyy-mm-dd-NNN`, assigned once, **never change**
     (even if the date is edited), counter restarts daily per type; lines are `<ref>/<n>`.
- IDs never encode mutable data (amount/account/asset) — that was an explicit decision.
- Dates `TEXT 'yyyy-mm-dd'` (CHECK-constrained with GLOB); timestamps ISO-8601 with offset.
- Money/quantities/prices/rates are `INTEGER` ×1,000,000 in columns ending **`_e6`** (exact `SUM()`,
  numeric range filters). The `v_*` views show normal decimals for humans.
- Only two calculated values are stored: `amount_base_e6` (FX fixed at transaction date) and
  nothing else — everything is derived, including search.
- Booleans are `INTEGER 0/1` with CHECKs; enums are TEXT with CHECK lists.
- `PRAGMA foreign_keys = ON`. Deletes are avoided: accounts/categories are deactivated, transactions voided.

### 6.2 Tables (`0001_initial.sql`)

| Table | Purpose | Key columns |
|---|---|---|
| `settings` | key/value | `base_currency = EGP` |
| `asset_classes` | tree of what wealth is | `code` (dotted), `name`, `parent_id`, `sort_order`, `active` |
| `financial_assets` | things you own a quantity of | `code`, `name`, `asset_class_id`, `currency`, `unit`, `quantity_decimals`, `is_cash`, `exposure` (CASH/EQUITY/GOLD/FIXED_INCOME/REAL_ESTATE/OTHER), `liquidity` (IMMEDIATE/DAYS/LOCKED), `purity_e6`, `isin`, `price_source` (YAHOO/GOLD_CALC/GOLD_LOCAL/MANUAL/NONE), `external_symbol`. Unique cash asset per currency. |
| `accounts` | where value is held | `code`, `name`, `institution`, `account_type`, `currency`, **`cash_class_id`**, `opening_date`, `is_system`, `last4`, `active`, `sort_order`, `notes`. *No `opening_balance` column. No `nature` column (derived from type).* |
| `categories` | tree of why money moved | `code`, `name`, `parent_id`, `movement` (INFLOW/OUTFLOW), `scope` (PERSONAL/WORK, outflows), `income_class` (HOUSEHOLD/INVESTMENT, inflows), `default_reimbursable`, `is_system`, `active` |
| `transactions` | the documents | `ref` (unique), `type`, `date`, `description`, `counterparty`, `status` (POSTED/VOID), `source` (MANUAL/IMPORT/MARKET_DATA/SYSTEM), `notes` |
| `ledger_entries` | the effects — **source of truth** | `transaction_id`, `line_no`, `date` (copied for indexing), `account_id`, `asset_id`, `quantity_e6`, `unit_price_e6`, `amount_e6`, `fx_rate_e6`, `amount_base_e6`, `effect`, `category_id`, `memo`. CHECK: INFLOW/OUTFLOW ⇒ category. |
| `budgets` | budget amounts (0005) | `category_id`, `month` (yyyy-mm), `one_off`, `amount_e6` (NULL = no budget); unique (category, month, one_off) |
| `price_history` | prices (filled from M3/M4) | `asset_id`, `date`, `price_e6`, `currency`, `source`; unique (asset, date, source) |
| `fx_rates` | FX (M4) | `date`, `base`, `quote`, `rate_e6`, `source`; unique (date, base, quote, source) |
| `audit_log` | before/after of every edit, void, restore | `entity`, `entity_id`, `action`, `summary`, `before_json`, `after_json` |
| `schema_migrations` | applied migrations | `version`, `name`, `status` (APPLIED/SKIPPED) |

**Indexes:** `ledger_entries(account_id,date)`, `(asset_id,date)`, `(category_id,date)`, `(transaction_id)`;
`transactions(date)`, `(type,date)`, `(status)`; `accounts(account_type)`; `categories(parent_id)`;
`financial_assets(asset_class_id)`; `price_history(asset_id,date)`; `audit_log(entity,entity_id)`.

**Search:** no index table. Migration `0002_search.sql` once added a full-text index; `0006_simplify.sql`
removed it together with the stored `search_text`. Migrations are never edited, so both stay in history.

**Readable views (`0003_readable_views.sql`):** `v_ledger` (line ref, date, type, status, `code · name`
account, asset, decimals, effect, category, description) and `v_balances` (posted balances per account/asset).

### 6.3 Why cash has an account-level class (important subtlety)

EGP in a wallet and EGP in a bank are the **same financial asset** (`CASH:EGP`), but reports must show
"Physical Cash" vs "Bank Balance". So each account has `cash_class_id`, **always set from its type** (there is no manual picker):

| Account type | Label on screen | Code abbr. | Default cash class | Nature |
|---|---|---|---|---|
| CASH | Cash wallet | CSH | `CASH.PHYSICAL` | asset |
| BANK | Bank account (current or savings) | CUR | `CASH.BANK` | asset |
| DEPOSIT | Certificate / time deposit (CD) | CD | `DEPOSIT.CD` | asset |
| BROKERAGE | Brokerage / investment | BRK | `CASH.BROKERAGE` | asset |
| PHYSICAL_ASSET | Physical asset (e.g. gold at home) — *hidden until M3* | PHY | `OTHER` | asset |
| RECEIVABLE | Money owed to me | RCV | `RECEIVABLE` | asset |
| OTHER_ASSET | Other asset | OTH | `OTHER` | asset |

Rule: **cash is classified by the account holding it; non-cash assets by the asset's own class.**
A CD can be tracked in M1 as a DEPOSIT account with cash class `DEPOSIT.CD`; in M6 each CD becomes its own asset.

### 6.4 Seed data (`database/seed.py`, idempotent — inserts only missing codes, never overwrites edits)

- **Asset classes:** CASH (Liquid Cash) › PHYSICAL, BANK, BROKERAGE · DEPOSIT › CD · STOCK · FUND ›
  EQUITY, MONEY_MARKET, GOLD, OTHER · GOLD · OTHER · RECEIVABLE.
- **Cash assets:** `CASH:EGP USD EUR GBP SAR AED` (2 decimals).
- **Categories:** `INC` › SALARY, BONUS, BUSINESS, GIFT, OTHER, `INC.INVEST` (INVESTMENT income) › INTEREST,
  DIVIDEND, `INC.UNACCOUNTED` (system) · `EXP` › `EXP.PERSONAL` (FOOD, DINING, TRANSPORT, HOUSING, UTILITIES,
  HEALTH, SHOPPING, ENTERTAINMENT, EDUCATION, TRAVEL, GIFTS, OTHER), `EXP.WORK` (reimbursable by default:
  TRANSPORT, SOFTWARE, MEALS, OFFICE, TRAVEL, OTHER), `EXP.FEES` (BANK, INTEREST), `EXP.TAX`,
  `EXP.UNACCOUNTED` (system). Children inherit movement/scope/income class from the parent.

---

## 7. The ledger and the net-worth equation

### 7.1 Documents → lines

Every user action creates a **transaction** (header) and one or more **ledger lines**. All balances,
holdings and reports are computed from **posted** lines only.

| What the person does | Transaction | Lines |
|---|---|---|
| Opens CIB with 50,000 | `OPN-…` | CIB `CASH:EGP` +50,000 OPENING |
| Groceries 450 from CIB | `OUT-…` | CIB −450 OUTFLOW `EXP.PERSONAL.FOOD` |
| Salary 42,000 | `IN-…` | CIB +42,000 INFLOW `INC.SALARY` |
| ATM 3,000 | `TRF-…` | CIB −3,000 INTERNAL · Wallet +3,000 INTERNAL |
| CIB → THNDR 10,000 | `TRF-…` | CIB −10,000 INTERNAL · THNDR +10,000 INTERNAL |
| *(M3)* Buy 100 COMI @ 95 | `BUY-…` | THNDR `CASH:EGP` −9,500 INTERNAL · THNDR `STK:COMI` +100 @ 95 INTERNAL |
| *(M5)* Reimbursable taxi 300 | `OUT-…` | CIB −300 INTERNAL · `SYS-RMB-EGP` +300 INTERNAL, category `EXP.WORK.TRANSPORT` |

Opening balances cannot be negative; net worth is the plain sum of all account values.

### 7.2 The equation

```
closing net worth = opening net worth + money in − money out + revaluation + new balances added
```

- `opening` = net worth on the day before the period; `closing` = net worth on the last day.
- `money in` = Σ INFLOW `amount_base`; `money out` = −Σ OUTFLOW `amount_base` (refunds reduce it).
- `new balances added` = Σ OPENING lines in the period (accounts started mid-period).
- `revaluation` is computed **per holding**: value at end − value at start − net flows into that holding.
  Base-currency cash always gives exactly 0; from M3/M4 prices and FX make it non-zero.
- `difference = closing − expected closing` must be **0.00**. Mathematically it equals the net of INTERNAL
  lines in the period, so it is a real integrity check of the ledger (shown on the dashboard; asserted in tests).

### 7.3 Valuation (`reporting/valuation.py`)

`value = quantity × price(on or before date) × FX(asset currency → base, on or before date)`.
Base cash = quantity. Manual prices win over automatic ones for the same date. Anything missing a price or
rate is returned as **unvalued** and listed on the dashboard — never silently counted as zero.

---

## 8. Workflows and service APIs

### 8.1 Services (public API of each module)

- **AssetService** — `list_classes()` (tree order), `get_class`, `get_class_by_code`, `root_of`, `list_assets`,
  `get_asset`, `get_asset_by_code`, `cash_asset(currency)`, `cash_currencies()`. Read-only in M1.
- **CategoryService** — `tree(movement?, active_only?)`, `pickable(movement)` (active, non-root, non-system,
  ancestors active), `get`, `get_by_code`, `descendants`, `require(id, movement)` (validates direction/active/not
  root), `create(parent_id, name, code?, default_reimbursable?)` (code = parent + slug of name; Arabic names need
  a typed code), `update(...)` → ids changed (code change cascades to descendants; roots/system protected).
- **AccountService** — `list`, `get`, `get_by_code`, `require_usable` (exists + active), `unique_code`
  (suggests `INSTITUTION-ABBR-CUR`, appends `-2`…), `create(...)`, `update(...)` → `(account, renamed)`
  (reporting group follows the type; only offered types accepted; currency immutable), `set_active`. `allow_foreign=False` blocks non-EGP until M4.
- **TransactionService** — `record_inflow`, `record_outflow`, `record_transfer`, `record_in_account` (one register row: Payment or Deposit + category or other account), `payee_suggestions`, `earliest_activity`, `set_opening_balance(account, signed,
  date)` (create/update/void the single OPN), `opening_balance`, `update_money`, `update_transfer` (edit in
  place, ref kept, audit logged), `void`, `restore` (re-validates accounts; one OPN per account), `get`,
  `get_by_ref`, `find(TxnFilter)` → `(summaries, total)`, `summarize`, `history`, `count_for_account`,
  `search_ids(text)`, `update_in_account`.
  Validation: account active; amount > 0 with ≤ asset decimals; category direction matches; transfer accounts
  differ and share currency; **date not before the account's opening date**; FX only for base currency (M1).
- **ReportingService** — `holdings(as_of)`, `net_worth(as_of)` (total, by account, by
  asset-class root with children, unvalued), `account_balance(id, as_of?)`, `bridge(from, to)`,
  `bridge_for_month(yyyy-mm)`, `cash_flow(from, to)` (household vs investment inflows; personal vs work
  outflows), `spending_by_category(from, to, depth)`, `monthly_trend(end_month, months)`,
  `statement(account, from, to)` (running balance), `first_date`.

`TxnFilter` (in `transactions/domain.py`): `search, account_id, category_ids, types, date_from, date_to,
include_void, limit, offset`.

- **BudgetService** — `month_view(yyyy-mm)` → sections (Personal, Work) of lines with direct amount, effective
  budget (direct, else sum of children), actual (rolled up from the ledger), remaining, % used, over; plus
  unbudgeted spending, money in and warnings. `save_month(month, {category_id: amount}, only_this_month)`,
  `set_budget(...)`, `amounts_for(month)`. Rules: money-out categories only, amounts ≥ 0 with ≤ 2 decimals,
  "" = no budget; repeating rows apply until a later row; one-off rows win for their month.

### 8.2 Workflows (`lightning/workflows/`) — cross-module actions in one DB transaction

- `AccountWorkflows.open_account(...)` — create account + opening balance (never negative).
- `update_account(...)` refuses a start date after the account's first transaction.
- `update_account(...)` — update fields and re-post the opening balance (ref kept, date follows `opening_date`).
- `deactivate(id)` — refused unless the balance is exactly zero ("no hidden money"); `reactivate(id)`.

Why this layer exists: accounts can't import transactions (transactions depend on accounts), so actions that
need both live one layer up. Database transactions nest via savepoints (`Database.transaction()`), so a
workflow calling several services commits or rolls back as a unit.

### 8.3 Search

Every word typed must appear somewhere in the transaction: ref, date, payee, description, notes, or on one
of its lines — account code or name, category code or name, or the amount (`450.00`). Numbers ignore
thousands separators (`10,000` = `10000`); `%` and `_` match literally. Nothing is stored for search, so a
renamed account or category is found under its new name immediately. So `carre`, `2026-09`, `10,000`,
`OUT-2026-09-25-001`, `groceries`, `طعمية` all work.

---

## 9. The HTML UI (`lightning/ui/`)

- `web.py` — `create_app(container)`, Jinja2 filters `money` / `tone` (neg/pos colouring), `render()` helper
  (injects base currency, today, flash `msg`, `error`, `error_field`), `redirect(url, msg)` (POST → 303 → GET).
- Errors: `LightningError` in a POST re-renders the form (HTTP 400) with the message, the offending field
  highlighted and the typed values kept. `NotFoundError` → 404 page.

| Route | Page |
|---|---|
| every page | Sidebar (Actual-style): Overview, Categories, Settings; **All accounts** total; accounts grouped by where they report (Liquid Cash, Deposits…) with balances (name + code); "+ Add account". |
| `GET /` | Overview: net worth, money in, money out, left over; what your wealth is made of; net-worth bridge with the 0.00 check; spending by category; 6-month trend; recent transactions. `?month=yyyy-mm`. |
| `GET /accounts/{id}` | **Register** for one account: name + balance, toolbar (+ Add New, search `q`, `month`), entry row (Date · Payee · Notes · Category · Payment · Deposit), rows newest first with running balance. `?edit=TXN&acct=ID` turns that row into an edit row. |
| `POST /accounts/{id}/register` · `POST /accounts/{id}/register/{txn}` | Save a new row / an edited row (`record_in_account` / `update_in_account`). |
| `GET /transactions` · `POST /transactions/register[/{txn}]` | **All accounts** register (extra Account column; one row per account a transaction touches). |
| `GET /transactions/{id}` · `POST …/void?back=` · `POST …/restore` · `GET /t/{ref}` | Detail with ledger lines and history; void/restore return to the register. |
| `GET /accounts` · `GET/POST /accounts/new` · `GET/POST /accounts/{id}/edit` · `POST …/deactivate` · `…/reactivate` | Account list and form (type decides the reporting group; opening balance; code, last 4, notes). |
| `GET /categories` · `GET/POST /categories/new?parent=` · `GET/POST /categories/{id}/edit` | Groups with category chips; rename, re-code, hide. |
| `GET /budget?month=` · `POST /budget?month=` | Budget vs actual: Personal and Work sections, editable budget per group/category, "this month only" option, progress bars, warnings. |
| `GET /settings` · `POST /settings/backup` | Base currency, DB path, search mode, backups, asset classes and assets. |

Register mechanics: inputs use the HTML `form=` attribute so every input sits in its own table column;
Enter saves; Esc cancels an edit; a known payee pre-fills its last category (`payee_suggestions`).

Styling: `static/style.css` — CSS variables, light + dark (`prefers-color-scheme`), responsive (sidebar
becomes a top bar under 900 px), tabular numbers, no external fonts/scripts. `static/app.js` only fills dates
and adjusts the account form wording; **no financial logic in the browser**.

---

## 10. Operational behaviour

- **Start:** `python -m lightning [--db PATH] [--port 8765] [--no-browser]` → backup existing DB → migrate →
  seed → serve on `127.0.0.1` → open browser.
- **Backups:** `data/backups/lightning_yyyy-mm-dd_HHMM.db` via SQLite's backup API on every start and on
  demand; newest 30 kept.
- **Migrations:** `database/migrations/NNNN_name.sql`, applied in order once, each in its own transaction.
  **Never edit an applied migration — add a new numbered file** (and log it in the changelog).
- **Audit:** `audit_log` rows for every transaction edit/void/restore (before/after JSON), shown as "History".

---

## 11. Status and roadmap

| # | Milestone | Status | Scope / design notes already agreed |
|---|---|---|---|
| M0 | Foundation | ✅ 0.1.0 | Everything in §2–§7 |
| M1 | Cash & bank basics | ✅ 0.1.0 | Accounts, opening balances, money in/out, transfers, account register, edit/void/restore, search, dashboard, statements |
| M2 | Reports & corrections | next | `ADJ` reconciliation ("wallet has 1,200, app says 1,450" → 250 to `EXP.UNACCOUNTED`); split transactions (multiple lines/categories); refunds = negative outflow in the original category; report pages; possibly month close |
| M3 | Investments (manual) | | Create financial assets (`STK:`, `FND:`, `GLD:`); `BUY`/`SEL`/`DIV`/fees; holdings from lines; **average cost** (as THNDR shows), **buy fees capitalised into cost**; manual prices in `price_history`; `VAL` entries; realized vs unrealized gains (a cost-basis view, separate from the net-worth view); allocation by asset class and by `exposure` (a gold fund counts as gold exposure) |
| M4 | Market data & FX | | `PriceProvider` adapters: Yahoo (EGX tickers with `.CA`, e.g. `COMI.CA`), gold parity (24K/gram = XAU/USD × USD/EGP ÷ 31.1035; 21K = 24K × 21/24), local Egyptian gold sites, manual, CSV; USD/EGP (`EGP=X`); daily pull on app start (+ optional Windows scheduled task ~16:00); store every source, manual wins; staleness shown; investing.com excluded (no API). Multi-currency accounts, `CNV` conversions, FX revaluation. Turn on `allow_foreign`. |
| M5 | Reimbursements | | System account `SYS-RMB-EGP · Reimbursements Receivable`; "my employer will pay me back" tick → INTERNAL lines to the receivable (net worth unchanged, gross work spending still reported); claims with partial settlement and one payment covering several claims (a `claim_id` column added in M5); money lent to friends (receivable) |
| M6 | Deposits & gold details | | Each CD its own asset with `deposit_terms` (rate, start, maturity, payout); interest accrual vs payout; early break; gold workmanship fee (المصنعية) and buyback price; bonus shares, splits |
| M7 | Imports & planning | | CSV/Excel/broker-statement importers calling services with `source=IMPORT` + an import batch id (added then); budgets (category × period); recurring transactions; target allocation and drift |
| M8 | Polish | | Charts, settings, packaging/desktop wrapper (e.g. pywebview) |

**Known limits in 0.1.0:** EGP-only accounts; one category per transaction; `PHYSICAL_ASSET` type hidden;
dates after today are refused (transactions and account start dates);
no delete of master data (deactivate instead).

---

## 12. Decisions log (with reasons)

| Decision | Reason | Rejected alternative |
|---|---|---|
| Accounts ≠ financial assets | Where vs what; brokerage holds many assets | Account type = asset type |
| Single ledger table under documents | One source of truth; balances never drift | Separate balance fields / 3 tables summed at report time |
| No `opening_balance` field | Opening is an `OPN` transaction, so it's in the ledger and works per asset | Field on Account |
| Holdings/positions derived, not stored | "Don't store calculated values" | Stored quantity/average_cost |
| Revaluation derived from prices, not stored rows | Stored rows would disagree with price history | Revaluation table |
| Cash class on the account, set by type | Same EGP asset must report as wallet/bank/CD | Separate asset per location |
| `_e6` integers | SQLite has no decimal; SUM on text becomes float | TEXT decimals summed in Python |
| Readable refs that never change; no mutable data in IDs | Edits would make IDs lie; duplicates collide | `asset_date_account_amount` IDs |
| Edit in place + audit log | Easier to use than reversal entries | Reversal/correction entries |
| No `include_in_net_worth` | Transfers to an excluded account break the equation | Per-account exclusion flag |
| Reimbursable spend = receivable; no liabilities at all | Avoid inflating income/expense and fake net-worth swings | Plain inflow/outflow |
| Workflows layer | Avoid circular service calls; atomic multi-module actions | Services calling each other both ways |
| Plain sqlite3 + SQL files | Readable schema, fewer moving parts | SQLAlchemy + Alembic |
| FastAPI + Jinja2 server-rendered HTML | "HTML first", logic stays in Python | Standalone JS app (would move logic to JS) |
| Edit/void moved into M1 | App unusable without corrections | Keep in M2 |
| No future dates | Every balance has one meaning (today); scheduled payments come as recurring transactions (M7) | Allowing future dates with a second "after today" balance |

---

## 13. Rules for every future change

1. **Log it in `CHANGELOG.md`** under `## [Unreleased]` (Added / Changed / Fixed / Removed / Decisions /
   Schema). When a milestone ships, rename to `## [x.y.z] — yyyy-mm-dd — Milestone` and bump
   `lightning/__init__.py:__version__`. `tests/test_changelog.py` fails if the version or any migration file is missing.
2. **Schema changes = a new migration file** (never edit old ones) + a Schema line in the changelog.
3. **Money is `Decimal`**; convert only with `to_e6`/`from_e6`; never `float`.
4. **Dates are `yyyy-mm-dd`**; parse with `core.dates`.
5. **Show codes with names** (`label` properties exist on Account, Category, AssetClass, FinancialAsset).
6. **Only `TransactionService` writes the ledger**, and always through `validate_posting`.
7. **UI calls services/workflows only** — no SQL, no financial calculations. Run `lint-imports`.
8. **New multi-module action → a workflow**, inside `db.transaction()`.
9. **Add tests**, keep the randomized reconciliation test green (`bridge.difference == 0`).
10. **Plain language in the UI** — no debit/credit wording; errors say what to do next.

## 14. How to run and verify

```
run.bat                                  # Windows: set up venv, install, start, open browser
python -m lightning --no-browser         # manual start
pip install -r requirements-dev.txt
python -m pytest                         # 102 tests
lint-imports                             # 4 architecture contracts
```
