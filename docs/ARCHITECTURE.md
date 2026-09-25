# Architecture

Lightning is a **modular monolith**: one Python process, one SQLite file, modules with hard boundaries.

## Layers

```
ui/            FastAPI + Jinja2 HTML. Calls services/workflows only. No SQL, no financial math.
bootstrap.py   Composition root: builds the database and wires services together.
workflows/     Actions spanning modules, each in ONE database transaction
               (open account + opening balance, start-date guard, deactivate if zero).
reporting/     Read-only: net worth, bridge, cash flow, spending, statements. Owns no tables.
transactions/  Records, edits, voids, finds transactions (Counterparty register rows; post() for other modules); only ledger writer.
accounts/      Where value is held.
assets/ · categories/   What value is (asset classes, financial assets) · why money moved.
budgeting/     Budget amounts per category × month; budget vs actual (actuals via reporting).
investments/   Buy, sell, dividends, holdings already owned → lines posted via transactions; positions & gains.
database/      sqlite3 connection, SQL migrations, seed data, backup, audit, settings.
core/          money · dates · codes · refs · posting rules. Depends on nothing.
```

Each module has `domain.py` (plain dataclasses), `repository.py` (its SQL, its tables only) and
`service.py` (its public API). Modules call each other's **services**, never each other's repositories.
These rules are enforced by `import-linter` (see `pyproject.toml`) and run as a test.

## The ledger

```
transactions (the document a person sees)  ──1:n──▶  ledger_entries (the effect)
```

| Case | Lines |
|---|---|
| Groceries 450 | CIB −450 EGP · OUTFLOW · `EXP.PERSONAL.FOOD` |
| Transfer 10,000 CIB → THNDR | CIB −10,000 INTERNAL · THNDR +10,000 INTERNAL |
| ATM 3,000 | CIB −3,000 INTERNAL · Wallet +3,000 INTERNAL |
| Buy 150 COMI @ 92.40 + fee 45 | THNDR cash −13,905 INTERNAL · THNDR STK:COMI +150 (cost 13,905) INTERNAL |
| Opening balance | Account ±X · OPENING |

Rules (`core/ledger.py`): INTERNAL lines net to zero; INFLOW/OUTFLOW need a category of matching
direction; amounts are exact.

**Net-worth equation** — `closing = opening + money in − money out + revaluation + new balances added`.
Revaluation is computed per holding (value change not explained by money moving in or out), so the
difference is a real check of the ledger, not a plug. Base-currency cash always revalues by exactly 0;
from M3/M4 prices and FX move it.

## Storage conventions

- Internal integer ids for relationships; readable **codes** for master data; fixed **refs** for documents.
- Dates `TEXT 'yyyy-mm-dd'`; timestamps ISO with offset.
- Money and quantities `INTEGER` × 1,000,000 (`_e6`), so `SUM()` is exact. Views `v_*` show decimals.
- Nothing calculated is stored except `amount_base` (FX fixed at the transaction date) and
  nothing else — search reads the tables directly.
- Corrections edit in place and write `audit_log`; void keeps the record and excludes it from balances.

## Indexes

`ledger_entries(account_id, date)`, `(asset_id, date)`, `(category_id, date)`, `(transaction_id)`;
`transactions(date)`, `(type, date)`, `(status)`; unique `price_history(asset_id, date, source)`,
`fx_rates(date, base, quote, source)`.

## Adding things later without touching the core

- **Investments (M3):** new financial assets and BUY/SEL/DIV documents → the same ledger lines with
  quantity and unit price. Valuation already reads `price_history`.
- **Market data (M4):** add an `integrations/market_data` package of price adapters that write `price_history`.
- **Imports (M7):** parse a file → call `TransactionService.record_*` with `source=IMPORT`.
- **Another UI:** call the same services; nothing in `ui/` is needed by the core.
