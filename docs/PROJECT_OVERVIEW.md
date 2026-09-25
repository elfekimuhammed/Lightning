# Lightning — Project Overview (hand-off brief)

> Read this first. It explains what Lightning is, how it is built, why, and how to extend it without breaking
> it — written so a developer or an AI assistant starting a fresh session can pick up immediately.
> **Version described: 0.3.0 (2026-09-25).** Companion docs: `CHANGELOG.md` (every change), `docs/GLOSSARY.md`
> (terms and codes), `docs/ARCHITECTURE.md` (short form), `docs/MILESTONES.md` (plan).

---

## 1. What Lightning is

A **local, single-user personal-finance app** in Python: accounts, money in/out, transfers, a monthly budget,
investments (stocks, funds, gold) and net worth — in one system, on one SQLite file.

**Owner and context.** Built for El Feki (GL architect / finance lead, Egypt). Base currency **EGP**. Typical
accounts: cash wallet, CIB current, QNB savings, bank CDs, a THNDR brokerage account, gold at home. Design borrows
accounting practice (document → journal lines, opening entries, receivables) but no accounting jargon is shown.

**The central idea — two separate questions, never merged:**

1. **Where is the wealth held?** → **Accounts** (Cash at hand, CIB Current, THNDR, Gold at home).
2. **What does it consist of?** → **Financial assets** (EGP cash, COMI shares, AZ Gold Fund units, 21K gold grams).

THNDR is a *brokerage account*; its **holdings** (cash, stocks, funds) are what it contains.

**Owner's priorities (they drive every decision):** (1) ease of use — anyone can use it, no debit/credit words;
(2) defined terminology; (3) good data structure and indexing, human-readable identifiers; (4) good code
structure; (5) workflows that cover normal cases.

**Standing rules:** dates are always `yyyy-mm-dd`; an **account code is always shown with its name**
(`CIB-CUR-EGP · CIB Current`); screens use plain names for categories and asset classes; **every change is logged
in `CHANGELOG.md`**; **no liabilities** (credit cards, loans, installments are out of scope by owner decision).

**Status:** 0.3.0 = M0 foundation, M1 cash & bank, account register, budgeting, architecture simplification,
M3 investments. Next: M4 market data (see §11).

---

## 2. Technology

| Concern | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.11 | `StrEnum`, modern typing |
| Storage | SQLite, one file `data/lightning.db` | Local, easy backup |
| DB access | Plain `sqlite3` + numbered `.sql` migrations | Readable schema, few dependencies |
| Money | `decimal.Decimal`; stored as integers × 1,000,000 (`_e6`) | Exact sums; floats forbidden |
| UI | FastAPI + Jinja2 server-rendered HTML + small vanilla JS | No build step, works offline |
| Server | uvicorn on `127.0.0.1` only | Never exposed to the network |
| Search | `LIKE` over transactions/accounts/categories at query time | Nothing derived to keep in sync |
| Tests | pytest — **151 tests** incl. two randomized reconciliation tests | |
| Architecture checks | import-linter, 4 contracts (`pyproject.toml`) | Module boundaries enforced |
| Launch | `run.bat` / `run.sh` → `python -m lightning` | Double-click; creates venv, installs, opens browser |
| Code hosting | Private GitHub repo `elfekimuhammed/Lightning`; `data/` git-ignored | Run on PC and laptop |

Runtime deps: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`. Dev: `pytest`, `httpx`, `import-linter`.

---

## 3. Terminology

| Term | Meaning | Example |
|---|---|---|
| **Account** | A place where value is held | `CIB-CUR-EGP · CIB Current` |
| **Financial asset** | A thing you own units of: a currency or an **investment** | `CASH:EGP`, `STK:COMI`, `GLD:21K` |
| **Asset class** | Editable tree of what wealth is | Liquid Cash › Bank Balance, Funds › Gold Fund |
| **Exposure** | What an investment really tracks, through its wrapper | a gold fund → Gold |
| **Holding / position** | Units of one asset in one account — always calculated | THNDR holds 150 COMI |
| **Category** | Editable tree of *why* money moved | Personal › Food & Groceries |
| **Transaction** | The document you see and edit | `OUT-2026-09-25-001` |
| **Ledger line** | One effect of a transaction on one account + asset | `OUT-2026-09-25-001/1` |
| **Money in / out** | Value entering / leaving your finances (needs a category) | Salary / groceries |
| **Transfer** | Money between two of your accounts; never income or spending | CIB → THNDR |
| **Buy / Sell** | Converting cash into units / units into cash; net worth unchanged at the moment of the trade | |
| **Dividend** | Cash paid by an investment (money in, investment income) | |
| **Revaluation** | Value change with no money moving (prices) | COMI 92 → 98 |
| **Cost basis / average cost** | What the units you hold cost (incl. buy fees) / per unit | |
| **Realized / unrealized gain** | Locked in by a sell / on paper for units still held | |
| **Opening balance** | Cash an account held when tracking started (`OPN`) | |
| **Holding I already own** | Units held when tracking started, with total cost (`OPN` per holding) | |
| **Budget** | Monthly amount for a money-out category or group | Food 6,000 |
| **Net worth** | Everything owned (no debts tracked) | |
| **Void** | Cancelled, kept for history, excluded from balances | |

"Category" (why money moved) and "asset class" (what wealth is) are deliberately different words.

---

## 4. Architecture — a modular monolith

### 4.1 Layers (top may import below, never the reverse — enforced)

```
lightning.main            entry: backup → migrate → seed → serve; opens the browser
lightning.ui              FastAPI routes, Jinja2 templates, static CSS/JS — calls services only
lightning.bootstrap       composition root: builds Database, wires services (Container)
lightning.workflows       multi-module actions in ONE db transaction (open account + opening balance, …)
lightning.budgeting       budgets per category × month; budget vs actual
lightning.investments     buy/sell/dividend/holdings → builds lines, posts via transactions; positions
lightning.reporting       read-only: net worth, bridge, cash flow, register, valuation; owns no tables
lightning.transactions    the ONLY writer of the ledger; register rows; search
lightning.accounts        where value is held
lightning.assets | lightning.categories    what value is (classes, assets, prices) | why money moved
lightning.database        connection, migrations, seed, backup, audit log, settings
lightning.core            money, dates, codes, refs, posting rules — depends on nothing
```

Each business module: `domain.py` (dataclasses/enums), `repository.py` (its own tables' SQL), `service.py`
(public API). Reporting also has `queries.py` (read-only SQL) and `valuation.py`.

### 4.2 Contracts (`lint-imports`, also run by `tests/test_architecture.py`)

1. Layers as above. 2. The UI never imports `database`, any `*.repository` or `reporting.queries`.
3. transactions / reporting / workflows / budgeting / investments never import other modules' repositories.
4. workflows / reporting / budgeting / investments never import `transactions.repository`.
Plus tests: no `float(` in financial modules; no SQL text in UI Python files.

### 4.3 File map

```
Lightning/
├─ run.bat · run.sh · requirements*.txt · pyproject.toml · .gitignore · .gitattributes
├─ README.md · CHANGELOG.md · docs/ (PROJECT_OVERVIEW, ARCHITECTURE, GLOSSARY, MILESTONES)
├─ data/                   runtime only, git-ignored: lightning.db + backups/
├─ lightning/
│  ├─ core/          errors money dates codes refs ledger
│  ├─ database/      connection migrator seed backup audit settings · migrations/0001…0006
│  ├─ assets/ categories/ accounts/ transactions/ budgeting/   domain · repository · service
│  ├─ investments/   domain · service
│  ├─ reporting/     queries · valuation · service
│  ├─ workflows/     accounts
│  ├─ ui/            web.py · routes/{dashboard,accounts,register,transactions,budget,investments,categories,settings}
│  │                 templates/{base,register,budget,not_found}.html + accounts/ categories/ dashboard/
│  │                 investments/ settings/ transactions/ partials/ · static/{style.css,app.js}
│  ├─ bootstrap.py · main.py · __main__.py · __init__.py (__version__)
└─ tests/            core, database, accounts_categories, transactions, reporting, budgeting, investments,
                     ui, architecture, changelog
```

---

## 5. The financial core (`lightning/core/`)

| File | Responsibility |
|---|---|
| `errors.py` | `LightningError(message, field)` → `ValidationError`, `NotFoundError`, `ConflictError` — plain-language, UI-safe |
| `money.py` | `to_decimal` (accepts `1,250.50`, rejects floats), `check_places`, `to_e6`/`from_e6`, `fmt` |
| `dates.py` | strict `parse_date`, `parse_month`, `today()` (tests pin it with env `LIGHTNING_TODAY`) |
| `codes.py` | code validation; `slug()` keeps whole words (`Cash at hand` → `CASH-AT-HAND`) |
| `refs.py` | `DocType` (`OPN IN OUT TRF CNV BUY SEL DIV VAL ADJ`), `format_ref`, `line_ref` |
| `ledger.py` | `Effect`, `PostingLine` (`.cash()`, `.units()`), **`validate_posting()`** |

**Posting rules:** ≥ 1 line; no zero-quantity line; ≤ 6 decimals; `amount_base = amount × fx`;
**cash lines**: amount = quantity, unit price 1; **investment lines**: quantity = units, unit price = trade price,
amount = cost (buy, incl. fees) or proceeds (sell, net of fees), sign of amount = sign of units;
INFLOW/OUTFLOW need a category, OPENING none; **INTERNAL lines net to zero**.

| Effect | Meaning | Cash flow? | Net worth? |
|---|---|---|---|
| INFLOW | value enters | yes | yes |
| OUTFLOW | value leaves | yes | yes |
| INTERNAL | moves inside (transfers, buys, sells) | no | no (nets to zero) |
| OPENING | pre-existing cash or holding | no | yes ("new balances added") |

---

## 6. Data model

**Conventions:** internal integer ids; readable **codes** for master data (editable); **refs**
`TYPE-yyyy-mm-dd-NNN` for documents (never change, even if the date is edited); dates TEXT `yyyy-mm-dd`;
money/quantities/prices INTEGER `_e6`; only `amount_base_e6` (FX fixed at the date) is a stored derivation;
deactivate/void instead of delete; `PRAGMA foreign_keys = ON`.

| Table | Purpose | Key columns |
|---|---|---|
| `settings` | key/value | `base_currency = EGP` |
| `asset_classes` | tree of what wealth is | `code`, `name`, `parent_id`, `sort_order`, `active` |
| `financial_assets` | currencies and investments | `code`, `name`, `asset_class_id`, `currency`, `unit`, `quantity_decimals`, `is_cash`, `exposure`, `liquidity`, `purity_e6`, `isin`, `price_source`, `external_symbol`, `active`, `notes` |
| `accounts` | where value is held | `code`, `name`, `institution`, `account_type`, `currency`, `cash_class_id` (always from type), `opening_date`, `last4`, `active`, `sort_order`, `notes` |
| `categories` | why money moved | `code`, `name`, `parent_id`, `movement`, `scope` (PERSONAL/WORK), `income_class` (HOUSEHOLD/INVESTMENT), `default_reimbursable`, `is_system`, `active` |
| `transactions` | documents | `ref`, `type`, `date`, `description`, `counterparty` (the "To"), `status` (POSTED/VOID), `source`, `notes` |
| `ledger_entries` | **source of truth** | `transaction_id`, `line_no`, `date`, `account_id`, `asset_id`, `quantity_e6`, `unit_price_e6`, `amount_e6`, `fx_rate_e6`, `amount_base_e6`, `effect`, `category_id`, `memo` |
| `price_history` | prices | `asset_id`, `date`, `price_e6`, `currency`, `source` (MANUAL now); unique (asset, date, source) |
| `fx_rates` | FX (M4) | `date`, `base`, `quote`, `rate_e6`, `source` |
| `budgets` | budget amounts | `category_id`, `month`, `one_off`, `amount_e6` (NULL = no budget) |
| `audit_log` | before/after of edits, voids, restores | `entity`, `entity_id`, `action`, `summary`, JSON |

**Indexes:** ledger `(account_id,date)`, `(asset_id,date)`, `(category_id,date)`, `(transaction_id)`;
transactions `(date)`, `(type,date)`, `(status)`; prices `(asset_id,date)`; budgets `(category_id,month)`.
**Views:** `v_ledger`, `v_balances`, `v_budgets` (readable decimals and `code · name`).
**Migrations:** `0001` schema · `0002` full-text index (later removed) · `0003` views · `0004` bank = savings,
no liabilities · `0005` budgets · `0006` simplification. Never edit an applied migration — add a new one.

**Account types** (offered): Cash wallet (CSH, → Liquid Cash › Physical Cash) · Bank account, current or savings
(CUR, → Bank Balance) · Certificate / time deposit (CD, → Deposits › CDs) · Brokerage (BRK, cash → Brokerage Cash)
· Physical asset e.g. gold at home (PHY) · Money owed to me (RCV) · Other (OTH). Brokerage, physical-asset and
other accounts can hold investments. Cash is classified by the account; investments by their own class.

**Seed data** (idempotent, never overwrites edits): asset classes (Liquid Cash › Physical/Bank/Brokerage;
Deposits › CDs; Stocks; Funds › Equity/Money Market/Gold/Other; Gold; Other Investments; Money Owed to You),
cash assets EGP USD EUR GBP SAR AED, and a category tree (Income incl. Investment Income › Interest/Dividends;
Expenses › Personal, Work (reimbursable by default), Fees & Charges, Taxes; system "Unaccounted" categories).

---

## 7. Ledger, valuation and the net-worth equation

| What happens | Doc | Lines |
|---|---|---|
| Open CIB with 50,000 | `OPN` | CIB CASH:EGP +50,000 OPENING |
| Groceries −450 | `OUT` | CIB −450 OUTFLOW · Personal › Food |
| Salary +42,000 | `IN` | CIB +42,000 INFLOW · Salary |
| CIB → THNDR 30,000 | `TRF` | CIB −30,000 INTERNAL · THNDR +30,000 INTERNAL |
| Buy 150 COMI @ 92.40, fee 45 | `BUY` | THNDR CASH −13,905 INTERNAL · THNDR STK:COMI +150 (cost 13,905, price 92.40) INTERNAL |
| Sell 50 COMI @ 110, fee 25 | `SEL` | THNDR STK:COMI −50 (proceeds 5,475) INTERNAL · THNDR CASH +5,475 INTERNAL |
| Dividend 180 | `DIV` | THNDR CASH +180 INFLOW · Investment Income › Dividends (memo `STK:COMI`) |
| Gold 12.5 g @ 3,950 + 1,800 from CIB | `BUY` | CIB CASH −51,175 · Gold at home GLD:21K +12.5 g (cost 51,175) |
| Fund units already owned | `OPN` | THNDR FND:AZ-MM +3,000 units (cost 3,150) OPENING |

**Valuation** (`reporting/valuation.py`): value = units × price × FX. Price = the newest of a **typed price** and
the **last buy/sell price** (typed wins the same day); holdings entered as already owned fall back to **cost**
until priced. Cash = its amount. Anything unpriced is listed as "unvalued", never silently zero.

**Positions** (`investments.service.portfolio`) walk each holding's lines oldest-first: units in add cost; units
out remove average cost × units; a sell's realized gain = proceeds − cost removed. Unrealized = value − cost.
Total return = unrealized + realized + dividends. Nothing is stored.

**Net-worth equation** (per period):
`closing = opening + money in − money out + revaluation + new balances added`.
Revaluation is computed per holding: value change − net flows into it (base cash is always 0). Trades net to
zero, so their gains show as revaluation. `difference` must be 0.00 — it equals the net of INTERNAL lines, so it
checks the ledger for real (shown on the Overview, asserted by tests).

**Invariants enforced:** INTERNAL lines net to zero; a holding never below zero units at any date (sell, edit,
void, restore); no dates after today; nothing before an account's start date; start date can't move past the
first transaction; opening balances ≥ 0; an account deactivates only with zero cash and no holdings.

---

## 8. Services (public APIs)

- **AssetService** — classes (`list_classes`, `display_name`, `root_of`), assets (`get_asset`, `cash_asset`,
  `investments`, `investment_classes`), **`create_investment(name, class_code, symbol, karat, isin, notes)`**,
  `update_investment`, **`set_price(asset, date, price)`**, `set_prices(date, {asset: price})`, `price_history`.
- **CategoryService** — `tree`, `pickable`, `groups`, `display_name`, **`find_by_text(text)`** (full name, short
  name, unique part or code; asks "Which one?" when ambiguous), `require`, `create`, `update` (code change cascades).
- **AccountService** — `list`, `get`, `get_by_code`, **`find_by_text`**, `require_usable`, `create`, `update`,
  `set_active`, `reporting_group`. Only EGP until M4 (`allow_foreign`).
- **TransactionService** — `record_inflow/outflow/transfer`, **`record_in_account(account, date, amount±,
  category | other_account, to, notes)`** and `update_in_account` (register rows; a kind change voids and
  re-records so the ref prefix stays true), **`post()` / `repost()`** for documents built by other modules,
  `set_opening_balance` (cash), `opening_txn_id(account, asset?)`, `update_money`, `update_transfer`, `void`,
  `restore`, `get`, `get_by_ref`, `find(TxnFilter)`, `search_ids`, `payee_suggestions`, `summarize`, `history`.
- **InvestmentService** — **`buy`, `sell`** (account, asset, units, price, fees, cash account — default the
  broker itself), **`dividend`**, **`add_holding`** (units + total cost), `update(txn, …)`, `values_of(txn)`
  (prefill), **`portfolio(as_of, account?)`** → positions and totals, `holding`, `investment_accounts`.
- **ReportingService** — `net_worth`, `holdings`, `account_balance` (cash), `account_value` (cash + holdings),
  `bridge`, `bridge_for_month`, `cash_flow`, `spending_by_category`, `money_out_by_category`, `monthly_trend`,
  `statement`, **`register(account?, from, to, txn_ids?)`** (cash lines, newest first), `sidebar`,
  `investment_lines`, `value_of`.
- **BudgetService** — `month_view(month)` (Personal and Work sections; direct / effective budget, actual, remaining,
  unbudgeted, warnings), `save_month`, `set_budget`, `amounts_for`. Repeat until changed; "this month only".
- **AccountWorkflows** — `open_account`, `update_account` (guards the start date), `deactivate`, `reactivate`.

**Search:** every typed word must appear in the ref, date, To, description, notes, or a line's account
code/name, category code/name or amount; thousands separators ignored; `%`/`_` literal.

---

## 9. The HTML UI

**Layout:** sidebar with Overview · Budget · Investments · Categories · Settings, then **All accounts** total and
accounts grouped by kind (Cash & bank · Deposits · Investments · Other) with values (name + code).

**Account page = register** (`/accounts/{id}`), Lightning's own design:
- header: name + code; **Cash · Holdings · Total**; Buy / Sell / Dividend for investment accounts; Holdings strip.
- **quick-add row**: Date · **To** · **Category** · Notes · **Amount** → Enter saves.
  - **Amount is signed**: `-450` money out, `1200` money in.
  - **To**: who the money went to or came from. Typing or picking **one of your accounts makes it a transfer**
    (Category is disabled). A To used before fills in its last category.
  - **Category**: type to search a list (HTML datalist), not a dropdown.
- rows newest first, coloured edge by kind, date shown once per day, running balance; click a row to edit in place
  (Save · Cancel/Esc · Void · Details & history). Buys/sells/dividends open the investment form.
- `/transactions` = all accounts in one register (extra Account column).

**Other pages:** Overview (`/`: net worth, money in/out, left over, wealth by asset class, bridge with 0.00 check,
budget card, spending, 6-month trend, recent) · Budget (`/budget`) · **Investments** (`/investments`: totals,
holdings with avg cost, price source "last trade"/"at cost", unrealized; allocation by class and exposure; sold-out
positions) · `/investments/new?kind=buy|sell|dividend|holding` · `/investments/{txn}/edit` ·
`/investments/assets/new|{id}/edit` · `/investments/prices` · Categories (groups with chips) · Settings
(backups) · `/transactions/{id}` detail with ledger lines and history · `/t/{ref}`.

Errors re-render forms (HTTP 400) with the message, the field highlighted and typed values kept.
`app.js` only fills dates, opens rows, and links To ↔ Category — no financial logic in the browser.

---

## 10. Running, data, sync

- `.\run.bat` (PowerShell needs `.\`) → `http://127.0.0.1:8765`. Options `--db PATH --port N --no-browser`.
- Backups on every start (`data/backups/lightning_yyyy-mm-dd_HHMM.db`, newest 30) and "Back up now".
- **PC ↔ laptop:** code via GitHub (`git pull` before, `git add/commit/push` after). Data is **not** in Git; each
  computer has its own `data/lightning.db` unless both start with `--db` pointing at a synced file (e.g. OneDrive),
  used on one computer at a time.
- When Claude edits the PC folder, commit and push from the PC; the laptop only pulls. Files Claude removes must be
  removed with `git rm` (Claude cannot delete files in the folder).

---

## 11. Roadmap

| # | Milestone | Status |
|---|---|---|
| M0 · M1 | Foundation · cash & bank | ✅ 0.1.0 |
| B | Budgeting | ✅ 0.2.0 |
| M3 | Investments (manual) | ✅ 0.3.0 |
| **M4** | **Market data & FX** — daily prices (Yahoo `.CA` symbols, e.g. `COMI.CA`), gold parity (24K/g = XAU/USD × USD/EGP ÷ 31.1035; 21K = 24K × 21/24) and local Egyptian gold prices, USD/EGP, multi-currency accounts, `CNV` conversions, FX revaluation; price_source + external_symbol already on assets | next |
| M2 | Reconciliation (`ADJ` to Unaccounted), split transactions, refunds (negative money out in the original category), report pages | |
| M5 | Reimbursements: "employer pays me back" → receivable, claims with partial settlement; money lent to friends | |
| M6 | CD lifecycle and interest, gold workmanship fee and buyback price, bonus shares and splits | |
| M7 | Imports (CSV/Excel/broker statements), recurring transactions, target allocation | |
| M8 | Charts, packaging | |

---

## 12. Decisions log

| Decision | Reason |
|---|---|
| Accounts ≠ financial assets | Where vs what; a brokerage holds many assets |
| One ledger under documents; balances, holdings, gains, search all derived | One source of truth |
| Readable codes + refs that never change; no mutable data in ids | Human-readable, safe edits |
| `_e6` integers, `Decimal` everywhere | Exact money |
| Cash class follows the account type; no manual picker | Owner found the picker unreadable |
| No liabilities; savings = bank account | Owner decisions |
| Edit in place + audit log; void instead of delete | Ease of use with a trail |
| No future dates | One meaning for every balance |
| LIKE search at query time, no index | Nothing stale; instant at personal scale |
| Register: signed Amount, "To" (an account = transfer), typed categories, own design | Owner feedback |
| Budget vs actual, either level, repeat until changed, Personal/Work sections | Owner choices |
| Average cost; buy fees into cost; sell fees reduce proceeds | THNDR style (owner) |
| Trades net to zero at cost/proceeds; gains appear as revaluation | Keeps the net-worth equation exact |
| Valuation: typed price → last trade price → cost | Always a value, source shown |
| Register lists cash only; holdings shown separately | Balances never mix units and money |
| Plain `sqlite3`, FastAPI + Jinja2 HTML | Simple, readable, logic stays in Python |

---

## 13. Rules for every change

1. **Log it in `CHANGELOG.md`** under `## [Unreleased]`; on release rename to `## [x.y.z] — yyyy-mm-dd — …` and
   bump `lightning/__init__.py`. `tests/test_changelog.py` fails if a version or migration is missing.
2. Schema change = a new migration file + a Schema line in the changelog.
3. Money is `Decimal` (`to_e6`/`from_e6` only); dates `yyyy-mm-dd` via `core.dates`.
4. Show account codes with names; screens use plain names for categories and asset classes.
5. Only `TransactionService` writes the ledger, always through `validate_posting` (other modules use `post()`).
6. UI calls services/workflows only — no SQL, no financial math. Run `lint-imports`.
7. Multi-module action → a workflow (or a module above the ones it uses) inside `db.transaction()`.
8. Add tests; keep both randomized reconciliation tests green (`bridge.difference == 0`).
9. Plain language in the UI; errors say what to do next.

```
.\run.bat                     # start
python -m pytest              # 151 tests
lint-imports                  # 4 contracts
```
