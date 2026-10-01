# Lightning — Project Overview

**Last updated 2026-10-02 · app 0.4.0b1.**

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
- **Certain obligations count; forecasts never do.** Bills due and loans still to pay make up *What you owe*. Bills due come off Free cash, and What you owe comes off Net worth. Loans are payment schedules, not debt accounts. A loan payment counts as spending when it is paid. Credit cards, loan-interest accounting and money owed to you are out of scope; CD interest schedules are in scope as estimates.
- **Reserves are not budgets.** A reserve sets aside cash you already own and lowers Free cash. A budget limit changes only the spending plan. The two are never added together. The emergency fund is shown in months of *Average monthly income*, the same average the budget and the forecast use.
- **Categories describe the activity, not the direction of money.** Level 1 is Personal / Work / Investment / System (money held for others and loan payments), level 2 is broad, and level 3 is optional detail under an L2. Each category is + income, − expense or ± both; income is recurring (counted in the average and the forecast) or irregular, and an expense can be one-off (in cash flow, out of the budget). A category that has been used is archived, never deleted.
- **Names are canonical.** Similar spellings are suggestions the user must pick. Lightning never silently merges or creates a counterparty.
- **Physical gold** is tracked piece by piece: net gold weight per piece, karat and cost. It is valued at a price per gram for the same karat, and purity is never applied twice.
- **People see names, not codes.** Summaries round to whole pounds; inputs keep cents. Dates are ISO. Entry also accepts `31/1` and `31/1/2026`, and Arabic-Indic digits.
- **Each visual says its time frame: the period you chose, or a fixed horizon.** Most charts and cards follow the period picker. Some keep a fixed horizon on purpose, because their question does not change with the period. Every section header names its frame. See *Period and fixed-horizon visuals* below.
- **Local only.** Data lives on the user's computer and is never committed to Git. The desktop app keeps each profile encrypted under Documents/Lightning, opened by a password, with a recovery key the user keeps elsewhere.

## What you can do today

- **Accounts and ledger:** open an account with a starting balance; record money in, money out and transfers; edit, void and restore, bulk select, search, and reconcile against a statement.
- **CSV import:** stage a bank CSV with one signed column or separate in/out columns. Only rows that need a decision need attention; a new name typed on several rows is created once; duplicates are flagged.
- **Budget:** Planned, Spent, then Left in plan. Each category takes one *Amount or %* field (`1,500`, or `12%` of average monthly income), or the average of recent months, with optional carryover. Views cover All time, YTD, Monthly and Custom. A loan's scheduled payments are planned automatically until you set your own amount.
- **Cash planning (Plan · Recurring · Loans · Reserves):** *Safe to spend* until the next income, What you owe, the next 30 days and a three-month forecast. It also holds recurring bills, subscriptions and income (suggested from history, never created on their own), loans with progress and payoff date, and reserves with the emergency fund. A strict unique payment match settles automatically; an early or changed-amount payment is suggested for confirmation. The forecast separately shows estimated CD interest and maturity cash without calling returned principal income.
- **Certificates and time deposits:** enter a CD's funded principal and terms on its deposit account: rate, simple versus compounding, payout or capitalization frequency, earliest withdrawal and maturity. Simple interest can pay monthly, quarterly, yearly or at maturity; compounded interest is paid at maturity. Terms never post money. Actual interest is recorded as income and returned principal as a transfer. The CD is outside Free cash while held.
- **Investments:** buy, sell and dividends inside the brokerage account; prices typed in or fetched; the period's *Net gain or loss* (Gain from sales + Price change on what you hold + Dividends and interest) alongside current holdings and *Holdings after sale (estimate)*.
- **Overview:** Needs you at the top (a closed row that opens into the list), then your position: Net worth, Free cash, *What it is made of* and *If you sold today (estimate)* with a sale factor per class. Below that come Cash flow with the savings rate, Where it went, Investments at a glance, and Month by month as a closed row. Birdview was folded in on 2026-09-30, and `/birdview` redirects here.
- **Held for others:** money and units you hold for someone else. Account headers show *In this account · What you own · Held for others*.
- **Every page:** months are picked from a month picker, never typed. Up to three key notes under the title give the page's answer in one sentence, and one set of charts follows the brand guideline.
- **Desktop preview:** `Lightning.exe` on Windows (no Python needed), or `python -m lightning --profiles` on Linux. You get named profiles, each encrypted and opened with a password, with a recovery key shown once at setup. Use dummy data until the beta: legacy import and backup restore aren't in the UI yet.
- **Demo:** `python -m lightning --demo`, or "See Lightning with a sample household" on an empty welcome page, opens Omar's last three months in a separate database.

## Period and fixed-horizon visuals

The period picker (All time · YTD · Monthly · Custom) changes what most visuals show. A few keep a fixed horizon, because their question is about a set stretch of time, or about today. Each section header says which applies (for example "2026-09-01 to 2026-09-30", "Last 6 months", "Year to date" or "Today").

| Follows the period you chose | Keeps a fixed horizon |
|---|---|
| **Overview:** the four stat cards; Cash flow (net flow, column waterfall, Sankey); the Investments section | **Overview:** Net worth over time (the last 12 month ends); the position cards (as of the period's last day) |
| **Budget:** the savings waffle, the plan bar and Spent of plan | **Budget:** plans are monthly, so a longer period adds up its months |
| **Investments:** the saved-and-invested waffle; Net gain or loss with Growth; the allocation donut and biggest holdings (as of the period's end); money and value by class | **Investments:** the Portfolio value sparkline (always the last six months); Dividends collected (year to date); XIRR (since the first investment, shown after a full year); the horizon bar (today) |
| **Expense analysis:** the four KPI cards; the treemap; now against usual; the months of the period in the heatmap | **Expense analysis:** "usual" is the six whole months before the period; the usual range, small multiples and heatmap history use the 12 whole months before it |
| — | **Holding page:** the holding's whole history, up to 24 month ends; sparklines for the last six |

A sparkline never follows the period. It is a quick "where is this heading" beside a number, so it always covers the last six months. A comparison ("against your usual month", "usual range") always looks at whole months *before* the period, so the period never compares with itself.

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
| How has it moved over the year? | Overview › Net worth over time (last 12 month ends) | Answered; wealth-change bridge is still partial (M3.2) |

**2. How much can I spend?**

| Follow-up | Answered by | Status |
|---|---|---|
| Why is it lower than my bank balance? | Free cash = Cash you own − Reserves − Bills due, each part expandable | Answered |
| How much until payday? | Cash planning › Safe to spend | Answered |
| What is due next? | Overview › Needs you; Cash planning › Next 30 days | Answered |
| Will I run short? | Cash forecast with its lowest point; Overview warns | Answered (3 months fixed) |
| Is my salary late? | — | Left out by decision |
| Can I afford this purchase now? | Safe to spend, before and after a new reserve | Partial: no "what if I buy it" check |
| Does an early payday count twice? | Recurring shows a plausible early payment; once Omar confirms it, the January plan is settled and the average attributes it to January, while the bank-date cash-flow report stays unchanged | Answered with confirmation (Omar step 18) |
| I have no salary this month: how long until the next one? | Safe to spend until the next scheduled income | Answered (Omar step 27) |

**3. Where did my money go?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which categories, and which transactions? | Overview › Where it went; Expense analysis bars drill down to transactions | Answered |
| More or less than last month? | Expense analysis › change from the comparable period | Answered |
| How much did I keep? | Savings rate (Net flow ÷ Money in) | Answered |
| What do subscriptions cost a year? | Cash planning › Recurring | Answered |
| A merchant or a few categories I care about? | No saved watchlist | Missing |
| A refund came back: did my spending go down? | It reduces the category in the month the refund arrives, not the month of the purchase | Partial (Omar step 13) |
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
| Rent went up, or I got a raise: does the plan follow? | A changed amount prompts Omar to confirm the payment, choose the future planned amount and review any reserve target; neither plan nor reserve changes silently | Answered with confirmation (Omar steps 20, 24) |
| What should I set aside for yearly bills (car licence, insurance, school fees)? | A reserve with a due date; Saving for goals spreads it over the months left | Answered (Omar step 19) |
| Have I actually set it aside? | The goal's assigned cash, which moves only when he assigns it | Partial: nothing asks him to assign the monthly amount |

**5. How are my investments doing?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which class or holding did best? | Net gain or loss by asset class; biggest movers | Answered |
| How much did I put in? | Money added | Answered |
| What would I get if I sold? | Investments › Holdings after sale; Overview › If you sold today | Answered |
| Am I on my target mix? | Investments › Set target allocation | Answered |
| Why does a holding show no gain? | No price yet: valued at cost and flagged | Answered |
| What did I make when I sold? | Gain from sales, after fees | Answered |
| When does my certificate mature, and what then? | Its terms page shows lock-up, maturity and estimated payouts; Cash planning projects spendable proceeds, while the real transfer remains a ledger action | Partial: no automated bank reconciliation or early-redemption transaction flow |
| How are my dollar savings doing? | — | Missing (M4, multi-currency) |

**6. Am I safe if something goes wrong?** The emergency fund shows months covered. Saving for goals shows what to set aside each month. Loans show payments made, what is left and the last payment; a skipped payment moves to the end of the loan.

| Follow-up | Answered by | Status |
|---|---|---|
| How long could I live if I lost my job? | Emergency fund in months of Average monthly income | Partial: it should be months of *spending*, since spending is what continues when the salary stops |
| I paid for a repair from the emergency fund: what now? | The fund shows what is left; Free cash is unchanged | Partial: nothing reminds him to refill it (Omar step 14) |
| When is the car loan paid off? | Loans › last payment | Answered |
| Can I pay the loan off early? | — | Missing: no early payoff or lump-sum payment |


**7. Is my data right?** Reconcile against the bank, review imports for gaps and duplicates, and run Checks. There is no stale-price warning yet (partial).

**8. What changes when my pay changes?** A salaried user's pay is not one flat number: raises, a yearly bonus or profit share, a 13th month, Ramadan and Eid grants, and paydays moved early for holidays.

| Follow-up | Answered by | Status |
|---|---|---|
| Where did my bonus go? | Money in › Bonus; Expense analysis for the same period | Answered |
| Does a bonus change my budget? | `BudgetService.income_average` excludes `EXP.WORK.BONUS` by default; a bonus does not lift Average monthly income | Answered; Omar step 17's average is instead affected by January salary booked in December (step 18) |
| I changed jobs: what happens to my income figures? | Stop the old salary (its history stays) and add the new one | End-of-service pay is irregular and excluded by default; the no-pay-month average still skips zero-income months (Omar step 27) |
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

**The rest of Omar's year.** Steps 1–10 are one ordinary month. Steps 11–28 carry the same household from October 2026 to September 2027 through what a salaried year brings: fees, a refund, a repair, a bonus, an early payday, a raise, Eid, installments, a share sale, a rent rise, a holiday, and a job change with a month between jobs. Every month also has the routine: salary on the 1st, rent on the 3rd, the car loan on the 5th, groceries, phone, internet and electricity.

`tests/test_omar_year.py` runs these steps through the services, one test per step. A step that is wrong today is a strict expected failure. When its fix lands, the test fails as an unexpected pass, and its marker and the **Today** column below must change together. Steps 1–10 are still driven in a browser.

| # | When | Step | What must be true afterwards | Today |
|---|---|---|---|---|
| 11 | Oct | An ordinary month | Every recurring payment and the loan settle themselves; nothing is due at month end | Answered |
| 12 | 10 Oct | Withdraws 2,000 at a CIB ATM, with a 25 fee | Net worth moves by −25 only; the fee is in Fees & Charges | Answered |
| 13 | 15 Oct | Returns August's 1,299 Amazon purchase | Shopping goes down by 1,299 | Partial: it goes down in October (October reads −1,299) and August keeps the purchase |
| 14 | 18 Oct | Pays a 6,500 car repair from the emergency fund | The fund drops to 13,500; Free cash is unchanged; cash drops by 6,500 | Answered; nothing reminds him to refill the fund |
| 15 | 20 Nov | Gets a 300 COMI dividend | Money in shows Dividends next to Salary; pay is unchanged | Answered |
| 16 | 10–22 Dec | Pays a 1,200 work Uber; ACME pays it back | Work spending for December is 0; the refund is not income | Answered |
| 17 | 20 Dec | ACME pays a 90,000 year-end bonus | Net worth +90,000; Average monthly income stays 45,000 | Answered after Omar confirms the separately suggested early January salary; Bonus itself stays excluded |
| 18 | 24 Dec | January's salary comes before the holidays | It settles January's payment; January's forecast expects no more pay | Answered after Omar confirms the early-pay suggestion; cash-flow reporting still uses 24 December |
| 19 | Jan–Apr | Plans 9,000 car insurance due 30 April, pays it from the goal | Saving for goals shows 2,250 a month | Answered; but no cash moves into the goal until he assigns it, and it cannot pay the bill until he does |
| 20 | 1 Feb | Raise to 50,000 | February settles after Omar confirms the changed-amount suggestion; later payments are planned at 50,000 only after he chooses it; December stays paid at 45,000 | Answered with confirmation, not automatic plan changes |
| 21 | 9–10 Mar | Eid: gives 3,000 in cash, receives 1,000 | Gifts & Donations and Gifts Received; gifts do not change the salary average | Answered; the rolling January–March salary average is 48,333.33 after January's 45,000 pay and two 50,000 pays |
| 22 | Mar | Buys a phone on 12 installments of 2,000 from 15 April | What you owe +24,000; each installment settles itself | Answered (as a loan; credit cards are out of scope) |
| 23 | 20 Apr | Sells 75 of 150 COMI for 7,100 after a 25 fee; moves it to CIB | 75 left; Gain from sales after fees; April's Money in is only the salary | Answered |
| 24 | 3 Jun | Rent rises 10% to 13,200 | June settles; July onwards is planned at 13,200 after Omar accepts the prompt; reserve target is reviewed separately | Answered with confirmation; neither future plan nor reserve changes silently |
| 25 | Jul–Aug | Sets aside 15,000 for a Sahel trip; spends 14,200 | 800 left in the goal | Answered |
| 26 | 31 Aug | Leaves ACME with 30,000 end of service; adds Valeo at 55,000 from 1 October | The old salary stops with its history; Average monthly income stays 50,000 | Right since Categories marks Bonus irregular |
| 27 | Sep | Between jobs, no pay | Next income is Valeo on 1 October; the average does not rise | Known gap: zero-income months are skipped by the average; the test checks non-increase, not zero-month inclusion |
| 28 | 30 Sep | Reads the year | Money in 651,300 and Money out 295,186; Change in what you own 357,364; loans still to pay 34,500; Checks pass; nothing is due | Answered, except *why* net worth changed (M3.2) |

**Not scripted, because Lightning cannot record them yet:**

- **A gam'eya.** Example: 10 months of 5,000, with the 50,000 pot in month 4. The payments are commitments, and the pot is his own money back, not income. Lightning has no gam'eya type, and an inflow needs an income category.
- **The NBE certificate maturing.** Terms and a projected maturity receipt now exist; Omar still needs to record the actual principal transfer from NBE to CIB and any interest credit. Automatic bank reconciliation is not built.
- **Dollar savings.** This waits for M4.
- **Paying the car loan off early.** There is no lump-sum payment.
- **A payslip's deductions** (income tax, social insurance). These are left out: record net pay.

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
| 7 | Spending history | Monarch | Answers "am I improving?" |
| 8 | Give every pound a job | YNAB "Ready to assign" | Closes question 4's last follow-up |
| 9 | Watchlists | Simplifi | Track one habit without a full budget |
| 10 | Shared household | Monarch partner access | Couples manage money together |
| 11 | Guided first setup | Monarch, YNAB onboarding | Omar's first run needed six account forms before seeing anything |
| 12 | Receipts and attachments | Monarch, Lunch Money | Warranty and gold purchase receipts |

**Known finance gaps** (the early-pay, raise and rent paths now require explicit confirmation; no-pay-month averaging in step 27 only has a non-increase assertion):

- **Unconfirmed early salary** remains in the bank-posting month of the income average and may leave a future salary payment due. The Recurring tab suggests the plausible match; Omar must confirm the specific transaction before the scheduled-month average and forecast adjust.
- **A changed recurring amount** prompts a future-plan update and a reserve review, but the user must choose them. A reserve is named only when the payment is explicitly linked to it; a name or category match does not silently change cash assignments.
- **CD projections** use an actual/365 day-count estimate, not a bank guarantee. Missing or partial funding suppresses the projection, and earlier simple-interest payouts are not reconciled against bank statements automatically.
- **The emergency fund** should count months of spending, not of income.

Bank sync and bill negotiation are not adopted. Any sync first needs a provider and regional coverage; local CSV stays the foundation. A "safe to spend" figure must always say which obligations and income it includes. Simplifi's projection, which leaves out planned spending, shows why.

## Roadmap

### Pre-ZIP release readiness

Verified UI fixes: Budget overlap at about 941px, the Cash planning tab strip and shared period pill at 390px, Settings data-card overflow, and account/all-transactions registers scrolling inside their cards. Holdings now uses five columns with expandable details, and the reviewed own-data fields have type-and-pick controls. Omar's early salary, raise and rent scenarios pass with explicit confirmations; the CD terms and forecast mechanism is covered by focused tests. A full interactive click-through of every control and acceptance on an ordinary Windows PC remain outstanding before the ZIP release. No new ZIP is implied by these source changes.

| Milestone | State | Next |
|---|---|---|
| M0–M1 Foundation and cash accounts | Shipped | — |
| B Budget, B.1 Budget flow | Shipped / in progress | Change one category without the full grid; first-use flow |
| M2 Reports and corrections | Partial | Balance adjustments, month close |
| M3 Manual investments | Shipped | — |
| M3.1 Instrument catalogue | Partial | Coverage and identifier quality |
| M3.2 Wealth history | Partial | Wealth-change bridge; owned-only XIRR (net-worth trend is shipped) |
| M4 Market data and FX | Planned | Wider prices, multi-currency accounts, FX revaluation |
| M6 Deposits and gold details | Partial | CD terms, interest projections and maturity forecast built; next: bank reconciliation, early redemption posting, local gold costs and buyback |
| Physical gold items | In progress | Item purchase/sale and report integration |
| M7 Planning and imports | Partial | Shipped: CSV import and Cash planning. Next: review inbox, matching manual entries with imports, reminders |
| Search | Planned | One typo-tolerant search across pages and records (contract in Architecture) |
| Desktop app (v0.4.0b1) | Development preview | Shipped: `Lightning.exe` for Windows and `--profiles` on Linux, with password-protected encrypted profiles in Documents/Lightning. Next: legacy import, backup restore, native file pickers, ordinary-PC testing, then a Windows-first beta for a few testers, hosted on the owner's website (design in Architecture) |

**Next up:** matching manual entries with imports, then one review inbox.
