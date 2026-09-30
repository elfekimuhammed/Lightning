# Budget app patterns worth adopting

The current list of what is still missing compared with the best budgeting apps is in [Project Overview](PROJECT_OVERVIEW.md#compared-with-the-best-budgeting-apps-what-is-still-missing).

Reviewed 28 September 2026; updated 30 September 2026 when Cash planning shipped (rows 1, 3 and 5). The remaining rows are a prioritized follow-up brief, not a promise that they are implemented. Existing Lightning behavior was checked against templates, services, and PROJECT_OVERVIEW.md.

| Priority / question | Reference pattern | Lightning today and proposed next task | Model |
|---|---|---|---|
| 1 · Will my cash last until payday? | [Simplifi projected cash flow](https://support.simplifi.quicken.com/en/articles/3357429-using-projected-cash-flow) shows dated balances and upcoming events. | **Shipped:** Cash planning › Plan shows Safe to spend until the next income and a three-month forecast from Free cash, scheduled payments, Left in plan after bills and Saving for goals, with its lowest point. It never changes Free cash or Net worth. | GPT-6 Sol; domain changes need careful reconciliation tests. |
| 2 · What needs my attention? | [Monarch tracking](https://www.monarch.com/features/tracking) brings transaction review and upcoming bills into short workflows. | Import has review and duplicate handling, Overview has attention links, but there is no unified review inbox or reliable manual-entry/import matching. Start with one queue of unresolved items linking to existing editors, then add candidate matching with confirmation. | GPT-6 Sol for matching; Luna for the queue UI once the rules are specified. |
| 3 · What bills and subscriptions are coming? | [Monarch recurring](https://www.monarch.com/features/tracking) offers a calendar/list and reminders. | **Shipped:** Cash planning › Recurring and Loans, with suggestions from history that never create items on their own, automatic paid-matching and undo. A calendar view and reminders remain. | GPT-6 Sol. |
| 4 · Am I overspending on the few things I care about? | [Simplifi watchlists](https://support.simplifi.quicken.com/en/articles/3472367-using-watchlists-on-the-web-app) track selected merchants/categories with optional limits. | Category budgets and spending drilldowns exist; saved cross-category/merchant watchlists do not. First allow saving a filtered spending view. Reuse the same ranked bars and limit-progress component. | GPT-6 Luna for saved filters; Sol if changing budget calculations. |
| 5 · How much should I put aside each month? | [YNAB targets](https://www.ynab.com/features) connect goals with visible progress. | **Shipped:** the forecast's Saving for goals spreads what a dated reserve still needs over the months left. | GPT-6 Sol for contribution/date rules. |
| 6 · Am I improving over time? | [Monarch tracking](https://www.monarch.com/features/tracking) includes historical wealth charts and monthly review. | Point-in-time owned wealth and period activity exist; historical owned-wealth trend is still planned. Add a consistent line chart only after historical prices, ownership, and missing valuations are handled explicitly. | GPT-6 Sol. |

## Shared presentation rules

- Every tab answers one primary question, then offers a small number of useful follow-ups.
- Use the same page title, period selector, summary cards, section headers, and detail disclosures. Keep units and dates next to values.
- Compare categories with ranked horizontal bars; show progress against a target with one consistent progress bar; reserve line charts for real time series.
- Use consistent semantic colours and visible text labels. A red value means a shortfall or overspend, not simply a negative number in every context.
- Keep missing valuations, import errors, and required decisions visible. Details should reduce clutter without hiding problems.
- Lead with actions such as “Review 3 items,” not unexplained metrics or a wall of empty charts.

## Scope and concerns

The current pass simplifies presentation and adds AI CSV preparation plus activity export. The future tasks above are prioritized briefs, not dispatched implementation jobs. That keeps this review inexpensive and avoids introducing several new financial models at once.

Budget room, current unassigned cash, and projected spendable cash are different concepts. Do not label any of them “safe to spend” without clearly defining which future obligations and income are included. Simplifi itself documents that its cash projection excludes planned spending and savings goals; this is a useful example of why forecast scope must be explicit.

**Decision (2026-09-30):** certain obligations now count. Bills due and loans still to pay form *What you owe*, shown as a separate item: bills due come off free cash, the full loan balance comes off net worth, and the forecast changes neither. Loans are entered as payment schedules, not as ledger debt accounts, so credit-card accounts and interest accrual remain out of scope.

**Adopted from other apps (Cash planning):** recurring-payment suggestions from history that never create items on their own (Monarch, Rocket Money, Copilot); an upcoming-payments list with paid/due status and automatic "paid" matching that the user can undo (Monarch); a projected balance with its lowest point (Simplifi); the monthly amount a dated goal still needs (YNAB); subscriptions totalled per year (Rocket Money); loan progress and payoff date (Monarch, YNAB). Not adopted: bank sync and bill negotiation. Bank synchronization also needs a provider and regional coverage assessment; local CSV workflows remain the current foundation.

## External analysis contract

The register's Export CSV downloads filtered posted cash activity, one row per transaction/account, not a full ledger or holdings snapshot. Account IDs, currency, type, linked account, and “Money held for” help interpretation. Both sides of an internal transfer may appear; do not count these as income/spending. Split-category rows are summarized and cannot support precise category allocation from this file alone. Refunds reduce spending; opening balances, trades, and valuation changes are not ordinary income/spending. Do not aggregate currencies without conversion. Export text that starts like a spreadsheet formula is prefixed with an apostrophe. The export is for analysis, not re-import.

The import helper supplies exact CSV instructions and current matching names locally; it does not contact an AI provider. Users choose what to share externally and still review staged rows before posting. A richer ledger/holdings export and downloadable analysis prompt remain useful follow-ups.

Model assignments use [OpenAI's model guidance](https://developers.openai.com/api/docs/models): Sol for balanced coding/reasoning, Luna for focused economical work. These are task-fit choices, not measured cost guarantees.
