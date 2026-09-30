# Lightning — Project Overview

**Last updated 2026-09-30 · app 0.3.0** (`lightning/__init__.py`; `pyproject.toml` still says 0.1.0 until the next release).

This file tells the story: what Lightning is, who it is for, what it answers and where it goes next. [Architecture](ARCHITECTURE.md) holds the technical side. The [App brand guideline](APPLICATION_BRAND_GUIDE.md) holds the visual side. The [Glossary](GLOSSARY.md) defines every term and figure. Shipped changes go in `CHANGELOG.md`.

## What Lightning is

Lightning is a local-first personal wealth app for Egyptians. It shows where your money is held, what it is invested in, how spending compares with your plan, and how what you own changes over time. The loop is simple: record or import activity, sort out unclear counterparties and categories, then read the analysis to spot patterns and save towards goals.

It keeps two questions apart: **where** value is held (an account such as CIB, the cash wallet, THNDR, gold at home) and **what** is held (EGP cash, COMI shares, fund units, gold grams, deposits).

Every number comes from one of three layers, and each screen says which:

- **Ledger — real money.** Posted transactions: where money actually came from and went.
- **Plan — what-if.** Budgets, reserves, scheduled bills and loans, sale factors and the cash forecast. It moves no money.
- **Report — reads both.** The Overview (the quick glance) and the reports under it: Budget, Investments, Expense analysis and Cash planning. They store nothing.

**Who it is for:** a busy user who won't read help text. Every figure has one name and one calculation everywhere, and a name that needs explaining gets renamed rather than explained. Every action gives visible feedback. A wrong or silent result is worse than an extra click.

**Priorities:** the simplest useful workflow with the fewest clicks; the same words everywhere; durable, searchable data; broad coverage of normal personal-finance cases. Calculations, matching, price processing and categorization are ordinary code, never AI calls.

## Product decisions that must hold

- **One ledger.** Account registers, the all-accounts view, budget actuals, investments, the Overview and the reports are all views of one transaction ledger.
- **Other people's money** (*Held for others*) stays in the account balance but belongs to its owner. It is left out of *What you own*. It is not income, spending or money owed to you.
- **Certain obligations count; forecasts never do.** Bills due and loans still to pay make up *What you owe*. Bills due come off Free cash, and What you owe comes off Net worth. Loans are payment schedules, not debt accounts. A loan payment counts as spending when it is paid. Credit cards, interest and money owed to you are out of scope.
- **Reserves are not budgets.** A reserve sets aside cash you already own and lowers Free cash. A budget limit changes only the spending plan. The two are never added together. The emergency fund is shown in months of *Average monthly income*, the same average the budget and the forecast use.
- **Categories describe the activity, not the direction of money.** Level 1 is Personal / Work / Investment and level 2 is broad. Level 3 stays empty until a user wants detail. A category that has been used is archived, never deleted.
- **Names are canonical.** Similar spellings are suggestions the user must pick. Lightning never silently merges or creates a counterparty.
- **Physical gold** is tracked piece by piece: net gold weight per piece, karat and cost. It is valued at a price per gram for the same karat, and purity is never applied twice.
- **People see names, not codes.** Summaries round to whole pounds; inputs keep cents. Dates are ISO. Entry also accepts `31/1` and `31/1/2026`, and Arabic-Indic digits.
- **Local only.** Data lives in one SQLite file on the user's computer and is never committed to Git.

## What you can do today

- **Accounts and ledger:** open an account with a starting balance; record money in, money out and transfers; edit, void and restore, bulk select, search, and reconcile against a statement.
- **CSV import:** stage a bank CSV with one signed column or separate in/out columns. Only rows that need a decision need attention; a new name typed on several rows is created once; duplicates are flagged.
- **Budget:** Planned, Spent, then Left in plan. Each category takes one *Amount or %* field (`1,500`, or `12%` of average monthly income), or the average of recent months, with optional carryover. Views cover All time, YTD, Monthly and Custom. A loan's scheduled payments are planned automatically until you set your own amount.
- **Cash planning (Plan · Recurring · Loans · Reserves):** *Safe to spend* until the next income, What you owe, the next 30 days and a three-month forecast. It also holds recurring bills, subscriptions and income (suggested from history, never created on their own), loans with progress and payoff date, and reserves with the emergency fund. A payment is marked paid automatically when exactly one transaction matches, or by hand from a popup, with undo.
- **Investments:** buy, sell and dividends inside the brokerage account; prices typed in or fetched; the period's *Net gain or loss* (Gain from sales + Price change on what you hold + Dividends and interest) alongside current holdings and *Holdings after sale (estimate)*.
- **Overview:** Needs you at the top (a closed row that opens into the list), then your position: Net worth, Free cash, *What it is made of* and *If you sold today (estimate)* with a sale factor per class. Below that come Cash flow with the savings rate, Where it went, Investments at a glance, and Month by month as a closed row. Birdview was folded in on 2026-09-30, and `/birdview` redirects here.
- **Held for others:** money and units you hold for someone else. Account headers show *In this account · What you own · Held for others*.
- **Every page:** months are picked from a month picker, never typed. Up to three key notes under the title give the page's answer in one sentence, and one set of charts follows the brand guideline.
- **Demo:** `python -m lightning --demo`, or "See Lightning with a sample household" on an empty welcome page, opens Omar's last three months in a separate database.

## The questions Lightning answers

Each tab answers one main question first, then its natural follow-ups. **Partial** and **Missing** mark the gaps.

| Screen | Main question | Leads with |
|---|---|---|
| Overview | Where do I stand, and what needs me? | Needs you, Net worth (What you own when nothing is owed), Free cash, what it is made of, cash flow, investments |
| Expense analysis | Where did my money go? | Money out, ranked categories, change from last period |
| Budget | Am I on plan? | Left in plan, categories over plan |
| Investments | What do I hold, and how did it do? | Net gain or loss for the period, holdings, allocation |
| Cash planning | How much can I actually spend? | Safe to spend, What you owe, the forecast |
| Reserves | Am I safe if something goes wrong? | Emergency fund in months of income |
| Account | What happened here? | One balance, then add/import and the register |
| Held for others | Whose money am I holding? | Balances by person |
| Settings · Checks | Is my data right? | Configuration and integrity checks |

**1. Where do I stand?**

| Follow-up | Answered by | Status |
|---|---|---|
| How does it add up? | Overview › Net worth rows and What it is made of | Answered |
| What part is not mine? | Held for others; account headers | Answered |
| What do I owe? | Overview › What you owe; Cash planning › Plan, Loans | Answered |
| Did it grow this period? | Overview › Change in what you own | Answered |
| *Why* did it change: saving, prices or new money? | No wealth bridge yet | Partial (M3.2) |
| How has it moved over the year? | No net-worth history chart | Missing |

**2. How much can I spend?**

| Follow-up | Answered by | Status |
|---|---|---|
| Why is it lower than my bank balance? | Free cash = Cash you own − Reserves − Bills due, each part expandable | Answered |
| How much until payday? | Cash planning › Safe to spend | Answered |
| What is due next? | Overview › Needs you; Cash planning › Next 30 days | Answered |
| Will I run short? | Cash forecast with its lowest point; Overview warns | Answered (3 months fixed) |
| Is my salary late? | — | Left out by decision |
| Can I afford this purchase now? | Safe to spend, before and after a new reserve | Partial: no "what if I buy it" check |
| Does an early payday count twice? | Salary paid more than 7 days early is not matched to its scheduled payment, so the forecast adds it again | Wrong (see Omar step 12) |

**3. Where did my money go?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which categories, and which transactions? | Overview › Where it went; Expense analysis bars drill down to transactions | Answered |
| More or less than last month? | Expense analysis › change from the comparable period | Answered |
| How much did I keep? | Savings rate (Net flow ÷ Money in) | Answered |
| What do subscriptions cost a year? | Cash planning › Recurring | Answered |
| A merchant or a few categories I care about? | No saved watchlist | Missing |
| How much did I spend on work that my employer owes me back? | Work categories; the reimbursement is a refund in the same category | Partial: nothing lists what is still unreimbursed |
| How much went in fees and bank charges this year? | Expense analysis › Fees & Charges, YTD | Answered |

**4. Am I sticking to my plan?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which categories are over? | Budget meters, over plan first; Overview | Answered |
| How much of my income does the plan take? | Spent and Planned as % of Average monthly income | Answered |
| Is my loan in the plan? | "Includes … of loan payments scheduled this month" | Answered |
| What about next month? | Rules repeat; a future month cannot be opened yet | Partial |
| Where should the rest of my income go? | No "ready to assign" view | Missing |
| Rent went up, or I got a raise: does the plan follow? | Recurring › set a new amount for later payments; the popup offers it after a manual match | Partial: a change over 10% is never matched on its own |
| What should I set aside for yearly bills (car licence, insurance, school fees)? | A reserve with a due date; Saving for goals spreads it over the months left | Answered |

**5. How are my investments doing?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which class or holding did best? | Net gain or loss by asset class; biggest movers | Answered |
| How much did I put in? | Money added | Answered |
| What would I get if I sold? | Investments › Holdings after sale; Overview › If you sold today | Answered |
| Am I on my target mix? | Investments › Set target allocation | Answered |
| Why does a holding show no gain? | No price yet: valued at cost and flagged | Answered |
| What did I make when I sold? | Gain from sales, after fees | Answered |
| When does my certificate mature, and what then? | — | Missing (M6) |
| How are my dollar savings doing? | — | Missing (M4, multi-currency) |

**6. Am I safe if something goes wrong?** The emergency fund shows months covered. Saving for goals shows what to set aside each month. Loans show payments made, what is left and the last payment; a skipped payment moves to the end of the loan.

| Follow-up | Answered by | Status |
|---|---|---|
| How long could I live if I lost my job? | Emergency fund in months of Average monthly income | Partial: it should be months of *spending*, since spending is what continues when the salary stops |
| When is the car loan paid off? | Loans › last payment | Answered |
| Can I pay the loan off early? | — | Missing: no early payoff or lump-sum payment |


**7. Is my data right?** Reconcile against the bank, review imports for gaps and duplicates, and run Checks. There is no stale-price warning yet (partial).

**8. What changes when my pay changes?** A salaried user's pay is not one flat number: raises, a yearly bonus or profit share, a 13th month, Ramadan and Eid grants, and paydays moved early for holidays.

| Follow-up | Answered by | Status |
|---|---|---|
| Where did my bonus go? | Money in › Bonus; Expense analysis for the same period | Answered |
| Does a bonus change my budget? | Average monthly income counts Bonus by default, so one 90,000 bonus lifts it from 45,000 to 75,000 for three months, and every `%` budget line, the emergency fund target and the estimated forecast with it | Wrong: until the default changes, untick Bonus under Settings › Budget › Income categories to include, or set the average by hand |
| Was I paid my raise? | The account register shows the new amount; Cash planning › Recurring keeps the scheduled payment Due until he links it by hand | Partial |

Money held for others is left out of every owned, budget and performance view. Transfers are never income or spending. Refunds reduce spending in their original category.

## Reference workflow: a month with Omar

The acceptance persona is **Omar**, 31, salaried, in Cairo. He earns 45,000 EGP a month from ACME Egypt, paid into CIB. He has a CIB payroll account, a cash wallet and Vodafone Cash; an NBE 3-year certificate; and a THNDR account with COMI, Fawry and a money market fund. His gold is an L'Azurde ring bought by card and a gold pound from his grandmother. He holds 10,000 EGP of his mother's money in CIB. He pays rent, internet, phone and electricity monthly, and has a 24-month car loan.

Drive it in a browser through the screens only, and re-run it after any workflow change. The numbers must still reconcile. The demo household is the same month, dated to today.

| # | Step | Layer | What must be true afterwards |
|---|---|---|---|
| 1 | Open six accounts, typing dates as `1/7` | Ledger | Dates become `2026-07-01`; the sidebar shows **In your accounts** |
| 2 | Import three months of CIB (40 rows) | Ledger | 39 posted, 1 skipped; salary, rent, groceries and transfers categorized; Mom's 10,000 is **Held for others** |
| 3 | Move money to THNDR; buy COMI and Fawry with fees; buy a money market fund | Ledger | Holdings and brokerage cash show on Investments |
| 4 | Record the ring bought by card and the inherited gold pound | Ledger | Ring paid from CIB; the pound needs no cash account |
| 5 | Record cash and Vodafone Cash spending | Ledger | Each shows in Money out and in its category |
| 6 | Enter month-end prices | Ledger | Holdings value and Net gain or loss update |
| 7 | Set a 20,000 emergency fund and create the budget | Plan | Free cash = Cash you own − Reserves − Bills due |
| 8 | Track suggested recurring items; add electricity and the car loan | Plan | September's payments matched; What you owe = 60,000; the loan is in the budget |
| 9 | On 2026-10-06 mark salary, rent and a loan payment paid from the Overview | Plan → Ledger | Each posts a real transaction; Net worth moves only by the salary (+45,000); loans still to pay 57,500 |
| 10 | Read every tab | Report | Free cash and What you own read the same everywhere; Checks pass |

**The rest of Omar's year.** Steps 1–10 are one ordinary month. A salaried year also brings the events below; run them after step 10 on the same data. The last column says what happens today, so a re-run shows whether a gap has closed.

| # | Step | Layer | What must be true afterwards | Today |
|---|---|---|---|---|
| 11 | Omar gets a raise to 50,000 from January | Plan → Ledger | January's salary settles the scheduled payment; later payments are planned at 50,000 | Not matched on its own (11% is over the 10% tolerance); he links it in the popup and sets the new amount |
| 12 | January's salary arrives on 24 December, before the holidays | Ledger → Plan | It settles January's payment; the forecast does not count it again; December's income is not doubled in Average monthly income | Not matched (7-day window); the forecast adds 45,000 in January again, and the average for February reads 70,000 |
| 13 | ACME pays a 90,000 year-end bonus | Ledger | It is Money in under Bonus and raises Net worth by 90,000; Average monthly income, `%` budget lines and the emergency fund target stay based on 45,000 | Average monthly income jumps to 75,000 for three months |
| 14 | He pays a 1,200 Uber for work and ACME reimburses it | Ledger | Work spending for the month is 0 after the refund; the refund is not income | Answered (refund in Work › Transportation) |
| 15 | He plans the 9,000 car insurance due end of April and the yearly car licence | Plan | Saving for goals shows 2,250 a month; Safe to spend drops by it; the licence is a Yearly bill | Answered |
| 16 | He sells half the COMI shares and moves the cash back to CIB | Ledger | Gain from sales is net of fees; brokerage cash returns to CIB as a transfer, not income | Answered |
| 17 | The NBE certificate pays interest monthly and later matures | Ledger | Interest is investment income, not salary; at maturity the principal returns to CIB | Interest answered; maturity missing (M6) |
| 18 | Eid: he gives 3,000 in cash gifts and receives 1,000 | Ledger | Gifts & Donations and Gifts Received each show their side; neither is salary | Answered |
| 19 | He joins a 10-month gam'eya of 5,000 a month and receives the pot in month 4 | Plan → Ledger | Payments are commitments; the pot is his own money back, not income | Missing: no gam'eya type, and the pot can only be recorded under an income category |
| 20 | He buys a phone on 12 monthly installments (valU or a 0% card plan) | Plan | The installments are in What you owe and in the budget | Answered as a loan; credit cards themselves are out of scope |
| 21 | Year end: he reads the year | Report | YTD Money in, Money out and savings rate; change in What you own; the year's Net gain or loss on investments | Answered, except why net worth changed (M3.2) and a net-worth history (missing) |

## Compared with the best budgeting apps

The reference apps are YNAB, Monarch, Copilot, Simplifi, Rocket Money, Lunch Money and Actual Budget.

**Already on par or adopted:**

- Recurring detection that suggests but never creates (Monarch, Rocket Money, Copilot).
- Upcoming bills with automatic paid-matching and undo (Monarch).
- A projected balance with its lowest point (Simplifi).
- The monthly amount a dated goal still needs (YNAB).
- Subscriptions totalled per year (Rocket Money).
- Loan progress and payoff date.
- Rollover budgets.
- Transfers, splits and refunds.
- Real investment returns, local gold and money held for others, which most budgeting apps lack.

**Still missing, most valuable first:**

| # | Missing | Best example | Why it matters here |
|---|---|---|---|
| 1 | Capture on the phone in seconds | Copilot, Monarch mobile | Cash and Vodafone Cash spending is forgotten unless logged on the spot |
| 2 | Automatic transaction feed | Bank sync in Monarch, YNAB | Import is the heaviest step. There is no Egyptian aggregator, so parsing bank SMS or e-statement PDFs is the cheaper route |
| 3 | Learned categorization rules | Monarch, Copilot, Lunch Money | A first import still needs one decision per distinct name |
| 4 | One review inbox | Monarch, Copilot "to review" | Import review and Needs you are separate today |
| 5 | Reminders | Monarch, Rocket Money, Simplifi | A user who doesn't open the app never sees a due bill |
| 6 | Multi-currency | Lunch Money, YNAB | Many Egyptians keep USD savings or earn USD |
| 7 | Net-worth and spending history | Monarch | Answers "am I improving?" |
| 8 | Give every pound a job | YNAB "Ready to assign" | Closes question 4's last follow-up |
| 9 | Watchlists | Simplifi | Track one habit without a full budget |
| 10 | Shared household | Monarch partner access | Couples manage money together |
| 11 | Guided first setup | Monarch, YNAB onboarding | Omar's first run needed six account forms before seeing anything |
| 12 | Receipts and attachments | Monarch, Lunch Money | Warranty and gold purchase receipts |

**Wrong today for a salaried user** (Omar steps 11–13), to fix before any new feature: a bonus lifts Average monthly income as if it were monthly pay (Bonus should be left out of the default income categories); a raise over 10% or a payday more than 7 days early is never matched, so the forecast counts the salary twice (salary items need a wider window and a match by counterparty and category that ignores the amount); and income paid early lands in the wrong month of the average. The emergency fund should also count months of spending, not of income.

Bank sync and bill negotiation are not adopted. Any sync first needs a provider and regional coverage; local CSV stays the foundation. A "safe to spend" figure must always say which obligations and income it includes. Simplifi's projection, which leaves out planned spending, shows why.

## Roadmap

| Milestone | State | Next |
|---|---|---|
| M0–M1 Foundation and cash accounts | Shipped | — |
| B Budget, B.1 Budget flow | Shipped / in progress | Change one category without the full grid; first-use flow |
| M2 Reports and corrections | Partial | Balance adjustments, month close |
| M3 Manual investments | Shipped | — |
| M3.1 Instrument catalogue | Partial | Coverage and identifier quality |
| M3.2 Wealth history | Partial | Wealth-change bridge; owned-only XIRR; net-worth trend |
| M4 Market data and FX | Planned | Wider prices, multi-currency accounts, FX revaluation |
| M6 Deposits and gold details | Planned | CD lifecycle, local gold costs and buyback |
| Physical gold items | In progress | Item purchase/sale and report integration |
| M7 Planning and imports | Partial | Shipped: CSV import and Cash planning. Next: review inbox, matching manual entries with imports, reminders |
| Search | Planned | One typo-tolerant search across pages and records (contract in Architecture) |
| Windows readiness | Planned, launcher exists | Native verification; Windows stays provisional until it passes (checklist in Architecture) |

**Next up:** matching manual entries with imports, then one review inbox.
