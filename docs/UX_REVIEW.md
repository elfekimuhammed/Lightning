# Product review · 28 September 2026

The application now uses a quiet, number-led visual system. Primary results use a compact key card with aligned expandable rows. Supporting information uses neutral panels; charts repeat the same comparison, progress and time-series structures. The user's preference for minimalism overrides the supplied marketing guide's vivid gradients.

| Screen | Main question | Result of this pass |
|---|---|---|
| Overview | Where do I stand? | Six sequential sections: total owned wealth, available cash, period cash flow, actions, expense snapshot and investments. Expandable balances show their contributing rows in place. Brokerage cash caveat stays visible. |
| Birdview | Where is my wealth? | Composition includes cash, investments and other owned assets; allocation and liquidity details have focused drilldowns rather than repeating the spending dashboard. |
| Budget | Am I within my plan? | Full monthly plan in monthly mode; partial custom-range estimates labelled; outside-group spending reconciles headline totals and links to supporting records. |
| Expense Analysis | Where did my money go? | Ranked bars, plain-language prior-period comparison, consistent time trend and transaction links. Category selection applies to totals, comparisons and monthly data. |
| Investments | What explains my result? | Result card with expandable components, portfolio-value trend, holdings and supporting details. Missing prices remain visible. |
| Account register | What happened here? | Guided transaction entry is primary; advanced inline entry is secondary; search, import/export, history and maintenance have distinct roles. |
| Reserves | What is funded or due? | Cash status and funding/payment progress lead; creation and secondary details open on demand. |
| Money from others | Who owns the money I hold? | Current balances lead, with supporting history available below. |
| Settings | What do I need to configure or correct? | General, Budget, Valuations, Counterparties, Categories and Data checks share subsection navigation. Existing URLs remain usable. |
| Navigation | Where do I go next? | Unique semantic icons; no Management toggle; distinct Accounts hierarchy, right-aligned balances, currency context and consistent selected states. |

## Functional changes verified

- Custom-date Apply retains the custom mode and dates.
- Saved CSV mappings can proceed to staging; reviewed custody imports can use an already selected active owner.
- Counterparty deletion checks the correct reserve table.
- Empty investment portfolios render correctly; trade tests use the actual Buy/Sell form contract and verify resulting balances.
- UI SQL moved into services, preserving financial calculations and transaction boundaries.
- Filtered CSV exports and AI preparation helpers remain available.

## Review evidence

The baseline had 17 failing tests, 217 passing and one skipped. The final integrated regression run passed: 242 tests passed and one skipped. Mobile browser checks at 390px found no page-level horizontal overflow in the app or component guide. The optional import-linter contract check is skipped because that tool is not installed; the no-SQL-in-UI and no-float-money tests run normally.

Browser review uses an isolated SQLite snapshot, not the live database. Checks cover populated Overview, Budget, Birdview, Spending, Investments, account actions, Settings and the component guide, including key-card expansion, custom-date submission and narrow layouts. This is a reviewable implementation; forecasts, bank synchronization, debt modelling and full language/RTL localization were not added.

Design references: [Application brand guide](APPLICATION_BRAND_GUIDE.md), [visual component reference](application-brand-guide.html), and [task architecture](PRODUCT_UX_ARCHITECTURE.md). Font families in the brand specification use the app's existing offline font fallbacks until the new brand fonts are bundled.

## Overview follow-up · 29 September 2026

Desktop browser review confirmed the six-section order, clear dividers, and actual cash-account and reserve rows inside disclosures. The original mixed metric grid is removed. Expense previews use the more useful second-level categories; heavy analysis remains linked separately.

Sixteen focused Overview, reporting and reserve checks passed. The full shared-workspace run produced 244 passed, one skipped and two failures from concurrent changes outside this Overview work: the unlogged `0033_reserve_account_matching.sql` migration and the changed account-entry control expected by `test_product_shell.py`. Those changes were preserved, not rewritten as part of this request.
