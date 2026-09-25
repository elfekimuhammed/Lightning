# Milestones

| # | Milestone | Status | What you can do at the end |
|---|---|---|---|
| M0 | Foundation | ✅ 0.1.0 | Skeleton, money/date/code/ref types, SQL migrations, posting engine, invariant tests, glossary |
| M1 | Cash & bank basics | ✅ 0.1.0 | Accounts with opening balances, money in/out, transfers, account register (Actual-style), edit/void, search, dashboard |
| B | Budgeting (pulled forward) | ✅ 0.2.0 + update | Budget vs actual per month, Personal and Work sections, group or category budgets, manual amounts or a rolling 3/6-month spending average |
| M2 | Reports & corrections | | Reconciliation adjustments (wallet says 1,200, app says 1,450), split transactions, refunds, report pages, month close |
| M3 | Investments (manual) | ✅ 0.3.0 | Stocks, funds, gold as assets; buy/sell/dividend/fee in THNDR; holdings, average cost, manual prices, revaluation, gains, allocation by asset class |
| M3.1 | Investment catalogue | next | Search Egyptian stocks and funds by name, ticker, or ISIN; choose to prefill an investment; assess EGX, Investing.com, TradingView, Yahoo, and other sources for coverage and reliable identifiers |
| M3.2 | Daily wealth history | | Record daily account/asset valuations; show overall wealth change and drill down by asset, class, and period, separating new money, income, and investment return |
| M4 | Market data & FX | | Daily prices, USD/EGP, 24K/21K gold (parity and local), multi-currency accounts, FX revaluation |
| M5 | Reimbursements | deferred | Receivables and claims are not a priority for personal wealth management; revisit only if requested |
| M6 | Deposits & gold details | | CD lifecycle and interest, gold workmanship fees and buyback, bonus shares and splits |
| M7 | Imports & planning | | CSV/Excel and broker-statement imports, recurring transactions, target allocation |
| M8 | Polish | | Charts, settings, packaging |

Known limits: EGP accounts only (FX in M4); one category per transaction (splits in M2).
Out of scope by decision (2026-09-25): liabilities — credit cards, loans, installments. Money held for others may be
tracked as a narrow custody balance excluded from net worth; general receivables remain deferred.

## Delivery approach and model budget

- Use GPT-6 Luna (low/medium reasoning) for bounded UI changes, budget controls, catalogue search, ordinary forms,
  documentation, and focused implementation tasks.
- Use GPT-6 Sol (medium/high reasoning) for database migrations, external data adapters, historical valuation,
  financial calculations, and final review.
- Reserve GPT-6 Astra for genuinely ambiguous architecture choices or high-risk analysis; it is not the default.
- Catalogue refreshes, price collection, and wealth snapshots run as deterministic Python, not AI calls.
