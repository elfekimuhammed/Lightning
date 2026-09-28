# Task-focused product architecture

## Screen ownership

| Screen | Primary job | Sections, in order | Follow-up destination |
|---|---|---|---|
| Overview | Decide what needs attention now | Total owned wealth; available cash after reserves; selected-period cash flow; actions; quick expense analysis; investment summary | Wealth breakdown, Budget, Reserves, account activity |
| Birdview | Understand what wealth consists of | Owned composition; liquidity assumptions; allocation against target | Class holdings, reserves, investment planning |
| Budget | Identify and adjust spending limits | Remaining/over-plan; categories requiring action; category progress and edit | Filtered spending and one-category limit edit |
| Expense Analysis | Explain spending | Selected-scope total and comparison; ranked category bars; dated trend | Subcategory drilldown and exact transactions |
| Investments | Explain portfolio results | Period result; holdings and allocation; supporting flows/reconciliation | Holding details, trade entry, price correction |
| Account | Record and inspect activity | Balance; add/import/export actions; filters and ledger | Transaction edit, reconciliation, maintenance |
| Reserves | Fund goals and meet obligations | Funding status; due/unfunded goals; creation/edit on demand | Allocation and payment matching |
| Counterparties / Categories | Find and maintain reusable names | Search/list; focused item actions; creation on demand | Aliases, category assignment, review |
| Money from others | Explain custody balances | Current owner balances; supporting history on demand | Account and transaction records |
| Settings / Integrity | Configure or resolve problems | Relevant settings or actionable check results | Specific repair/detail workflow |

## Shared component contract

- Sidebar destinations have distinct semantic SVG icons. There is no Management disclosure. Settings owns Counterparties, Categories and Data checks, with a consistent subsection navigation even where existing route URLs are retained. Reserves and Money from others remain directly accessible.
- The sidebar account list has a clear Accounts heading, subdued account-type group labels, aligned balances, and one selected-account marker. Avoid repeating owned/held/gross summary metrics before the list. Put Add account and Manage accounts in a stable footer.
- `metric-grid` / `metric-card`: short label, one value, unit, short scope/date note, and a relevant next action. Four columns only when width permits; two then one on smaller screens.
- `workspace-grid` / `data-panel`: paired related tasks on wide screens; stack on small screens. No fixed height to artificially fill the screen.
- `section-head`: one task-oriented heading and at most one primary section action.
- `compact-list` / `compact-row`: label, value/status, and direct detail link; line wrapping must preserve the value.
- Shared period control: retains custom dates and filters across submissions and supported drilldowns. Position uses period end; flows use the entire interval.
- Ordinary surfaces are restrained, with consistent borders, spacing and type hierarchy. Colour indicates meaning; text also conveys the state.

## Visualization rules

Rank categories with horizontal bars on one common scale. Compare actual spending with a limit using labelled progress bars and an explicit over-limit amount. Plot time series only when the values represent comparable dates and units; show missing data as missing. Use tables for exact holdings and editable financial values. Do not draw charts for empty states or present a decorative 100% bar as insight. Negative/refund values must never produce negative CSS dimensions or silently disappear.

## Functional and accounting boundaries

Every visible action must lead to a working workflow. An income/spending drilldown must either apply that scope or be labelled honestly as general activity. Category and date context must survive drilldowns. Empty states offer the next useful action. Invalid edits preserve values and keep errors visible, including when a form usually lives inside a disclosure.

Owned wealth, account balances including custody, free cash after reserves, budget room and estimated liquidation value remain distinct. Investment transfers are not expenses. Do not replace an unavailable valuation with zero. Read-only UI code calls services; database queries belong below the UI layer. No new financial models or forecasts are introduced as incidental presentation changes.

## Review gates

1. Resolve the recorded baseline failures: 17 failing, 217 passing, one skipped before this pass.
2. Retain meaningful business assertions when updating outdated tests; fix actual broken workflows separately.
3. Check primary screens with populated and empty data, plus a narrow viewport, through the browser.
4. Confirm copied/imported/exported data contracts and keyboard-accessible disclosures.
5. Leave a concrete review note of verified behavior and remaining limits; professional presentation alone is not a claim of international compliance or full localization.

## Overview hub contract

The Overview follows a vertical reading order, not a grid of unrelated metrics. Each of its six sections has a heading, a scope/date, a clear divider, and one financial question. Owned wealth leads; available cash follows; net cash flow belongs with money in and out. Actions precede short spending and investment summaries. Detailed analysis remains available from each relevant section.

An expandable amount reveals the actual contributing rows in place. Owned liquid cash reveals wallet, bank and brokerage cash balances; reserves reveal assignments. Account and reserve links are secondary to this quick explanation. Brokerage holdings must never be counted as brokerage cash. Rows reconcile to their parent amount or explicitly state why a breakdown is unavailable.

Position values use the selected period end. Flow, expenses and investment performance use its start and end. Current unresolved alerts state that they are current. Do not truncate alerts without a way to reveal the remainder. Missing valuation or historical assignment data stays visibly unavailable. “Available cash” is a stock after reserves; “net cash flow” is income minus expenses over time.
