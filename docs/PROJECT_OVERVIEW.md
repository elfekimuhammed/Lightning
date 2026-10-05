# Lightning — Project Overview

**Last updated 2026-10-04 · app 0.5.0b1.**

This file tells the story: what Lightning is, who it is for, what it answers and where it goes next. [Architecture](ARCHITECTURE.md) holds the technical side. The [Brand guideline](BRAND_GUIDELINE.html) holds the visual side. The [Glossary](GLOSSARY.md) defines every term and figure. Shipped changes go in `CHANGELOG.md`; the hand-off is in `NOW.md`.

## Contents

Read only the section your task needs (`grep -n '^## ' docs/PROJECT_OVERVIEW.md`, then read from that line). The hand-off between the AIs is in [`NOW.md`](../NOW.md), not here.

| Section | Read it when |
|---|---|
| What Lightning is | You are new to the product |
| Product decisions that must hold | You change any figure, rule or flow |
| What you can do today | You need the current feature list |
| Period and fixed-horizon visuals | You change a chart, card or the period picker |
| The questions Lightning answers | You change what a screen answers, or a known gap |
| Reference workflow: a month with Mohab | You change Mohab's test or a screen he uses |
| Compared with the best budgeting apps | You plan a feature |
| UX plan (guideline 3.6) | You take a UX item, or answer the owner's open UX questions |
| Roadmap | You plan or finish a milestone |

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
- **Holdings value and Portfolio value are one figure** (2026-10-04): everything you own that is not cash, certificates and deposits included, on every tab and chart.
- **Every release stays downloadable** (2026-10-03): keep at least the three latest versioned downloads permanently. Each release gets its own immutable download and its own entry on the website. Never replace an older version's file or entry, and never remove an older release without the owner's say.
- **Free for 7 days, then a reminder, never a lock** (2026-10-04, the WinRAR route): the whole app works from the first minute with no card and no account. After 7 days it asks for a licence; it never blocks, hides or locks the user's data. Price not yet set. Why: a paywall before any try is Say's most repeated complaint ([Competition](COMPETITION.md)).
- **Local only.** Data lives on the user's computer and is never committed to Git. The desktop app keeps each profile encrypted under Documents/Lightning, opened by a password, with a recovery key the user keeps elsewhere.
- **Planned multiple devices · phone as home.** One Lightning codebase will run on PC and Android. The phone holds the accepted encrypted ledger and edits it at home; one paired PC or laptop at a time may borrow a local working copy and keep editing if the phone goes quiet. Pair once, then use a short local handoff. Prefetch while the PC password is typed. The target is seconds, to be measured on a real phone. A future server or cloud copy is outside version 1.
- **Planned lend safety.** While a PC borrows, it saves locally and sends the phone an encrypted recovery copy about every three minutes when reachable and changed. Closing near the phone hands back; closing away saves a sealed copy and keeps the lend for later hand-back. The phone runs a user-started service during the lend and later reminders, never silently takes writing rights back. Copies stay local; cloud backup may be an explicit later opt-in.
- **Planned hand-back acceptance.** A locked phone may receive an encrypted return; it accepts it only after unlock, full verification and durable promotion. Until then the PC remains read-only. The integrated [implementation plan](proposals/multiple_devices.md#15-implementation-work-packages) divides the full cycle into 24 work packages with explicit dependencies, smaller subtasks, reading guides and exit checks; no sync implementation is claimed.
- **Planned multiple devices, what you will see.**
  - Open Lightning on the phone, then on the PC. While you type the PC password, the copy arrives, and the PC opens ready to edit.
  - The phone shows "Lent to Office PC · read only".
  - Work on the PC with or without the phone nearby.
  - Close the PC near the phone and the ledger goes home. Close it away from the phone and it waits, safely saved, for the next meeting; the phone reminds you.
  - Next time you unlock the phone, it checks the returned copy, then reads the bank SMS that arrived meanwhile.
  - Without the phone, the PC can still show a dated, read-only saved copy for analysis.
  - Sometimes, for example after Android closed the app, the phone asks for its password before lending, and says why.
- **Planned bank SMS.** The phone reads bank SMS only after the ledger has been accepted home and unlocked, including messages received during a lend. Known formats follow the import and category rules; unclear ones wait for review and later bank CSVs must not duplicate them. Learn formats bank by bank from sanitized examples. The full design and its limits are in [Multiple devices](proposals/multiple_devices.md).

## What you can do today

- **Accounts and ledger:** open an account with a starting balance; record money in, money out and transfers; edit, void and restore, bulk select, search, and check an account against the balance the bank shows: a small difference (up to 1% or 100, whichever is larger) becomes one balance adjustment counted as Other spending or Other income; a bigger one is reviewed row by row or reimported.
- **CSV import:** stage a bank CSV with one signed column or separate in/out columns. Only rows that need a decision need attention; a new name typed on several rows is created once; duplicates are flagged.
- **Budget:** Planned, Spent, then Left in plan. Each category takes one *Amount or %* field (`1,500`, or `12%` of average monthly income), or the average of recent months, with optional carryover. Views cover All time, YTD, Monthly and Custom. A loan's scheduled payments are planned automatically until you set your own amount.
- **Cash planning (Plan · Recurring · Loans · Reserves):** *Safe to spend* until the next income, What you owe, the next 30 days and a three-month forecast. It also holds recurring bills, subscriptions and income (suggested from history, never created on their own), loans with progress and payoff date, and reserves with the emergency fund. A strict unique payment match settles automatically; an early or changed-amount payment is suggested for confirmation. The forecast separately shows estimated CD interest and maturity cash without calling returned principal income.
- **Certificates and time deposits:** a bank's `DEPOSIT` account is its CD portfolio; its Institution field identifies the bank and the portfolio cannot hold cash. Each CD is a separate non-cash `DEPOSIT.CD` asset with its own name, principal, rate, simple/compound method, payout/capitalization frequency, earliest withdrawal date, and maturity date. Enter maturity directly or enter a term in years; the date is calculated from the purchase date. Buying it creates a `BUY` transaction funded from a bank/cash account the user chooses, with sufficient owned cash checked on the purchase date. Interest and maturity proceeds are forecast estimates only: Lightning never posts interest automatically. Record actual interest manually from the bank statement; enter actual principal proceeds when redeeming. Old account-level CD terms are preserved and shown as legacy, not automatically converted, and cash in old `DEPOSIT` accounts must be moved out.
- **Investments:** buy, sell and dividends inside the brokerage account; prices typed in or fetched; the period's *Net gain or loss* (Gain from sales + Price change on what you hold + Dividends and interest) alongside current holdings and *Holdings after sale (estimate)*.
- **Overview:** Needs you at the top (a closed row that opens into the list): the one review inbox, with every statement waiting for review and every transaction still without a category beside bills due, prices and plans, then your position: Net worth, Free cash, *What it is made of* and *If you sold today (estimate)* with a sale factor per class. Below that come Cash flow with the savings rate, Where it went, Investments at a glance, and Month by month as a closed row. Birdview was folded in on 2026-09-30, and `/birdview` redirects here.
- **Held for others:** money and units you hold for someone else. Account headers show *In this account · What you own · Held for others*.
- **Cash ownership:** from an account register, reassign cash between yourself and a saved person without changing gross account cash, or record an expense paid externally on your behalf. The latter remains an owned expense for budget and spending reports while attributing the same cash share to the payer.
- **Every page:** months are picked from a month picker, never typed. Up to three key notes under the title give the page's answer in one sentence, and one set of charts follows the brand guideline.
- **Desktop preview:** `Lightning.exe` on Windows (no Python needed), or `python -m lightning --profiles` on Linux. You get named profiles, each encrypted and opened with a password, with a recovery key shown once at setup. A locked profile can choose and confirm restoration from one of its encrypted backups; a password-gated check can resume a matching interrupted restore. This early path still needs ordinary Windows recovery/fault acceptance, and ambiguous evidence remains blocked. Use dummy data until the beta; legacy import is absent.
- **Demo:** `python -m lightning --demo`, or "See Lightning with a sample household" on an empty welcome page, opens Mohab's last three months in a separate database.

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

**What Mohab's test should do.** `tests/test_mohab_year.py` is the acceptance check for every question here. Mohab (below) is a real Egyptian salaried user, and the test judges Lightning the way he would, in the Windows WebView2 app:

- **Right answers:** every figure reconciles across tabs and stays right after a year of real life.
- **Usability:** each question is answered by starting at the Overview and clicking through. The route is checked; a dead end, a missing way back or a lost half-done task fails.
- **Efficiency:** it counts his effort. One typed bank balance, not clearing lines one by one; one fix, not one per row; nothing typed twice.
- **Speed:** pages must feel instant on an ordinary, encrypted PC. Long periods stay summarised (months, not 365 days) and pages stay light.
- **Simplicity:** the fewest controls that do the job; no placeholder text to delete; nothing that needs a manual.
- **Clarity:** plain words and readable numbers (no "System", no −1,351.7%), the date or period of every figure, and a warning when a plan cannot work.
- **UI:** compact rows, readable messages, and layouts that fit the app window and a phone.

User feedback becomes steps Mohab takes: fixed points are checked as answers, open ones are strict expected failures. Speed and look are also judged on a real PC, because the test sees only what the screens show.

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
| Does an early payday count twice? | Recurring shows a plausible early payment; once Mohab confirms it, the January plan is settled and the average attributes it to January, while the bank-date cash-flow report stays unchanged | Answered with confirmation (Mohab step 18) |
| I have no salary this month: how long until the next one? | Safe to spend until the next scheduled income | Answered (Mohab step 27) |

**3. Where did my money go?**

| Follow-up | Answered by | Status |
|---|---|---|
| Which categories, and which transactions? | Overview › Where it went; Expense analysis bars drill down to transactions | Answered |
| More or less than last month? | Expense analysis › change from the comparable period | Answered |
| How much did I keep? | Savings rate (Net flow ÷ Money in) | Answered |
| What do subscriptions cost a year? | Cash planning › Recurring | Answered |
| A merchant or a few categories I care about? | No saved watchlist | Missing |
| A refund came back: did my spending go down? | It reduces the category in the month the refund arrives, not the month of the purchase | Partial (Mohab step 13) |
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
| Rent went up, or I got a raise: does the plan follow? | A changed amount prompts Mohab to confirm the payment, choose the future planned amount and review any reserve target; neither plan nor reserve changes silently | Answered with confirmation (Mohab steps 20, 24) |
| What should I set aside for yearly bills (car licence, insurance, school fees)? | A reserve with a due date; Saving for goals spreads it over the months left | Answered (Mohab step 19) |
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
| When does my certificate mature, and what then? | The bank's CD portfolio lists each certificate's terms and maturity; Cash planning shows estimated interest and principal proceeds. The user records statement interest and actual redemption proceeds | Partial: legacy account-level terms are not converted, and no automated bank reconciliation |
| How are my dollar savings doing? | — | Missing (M4, multi-currency) |

**6. Am I safe if something goes wrong?** The emergency fund shows months covered. Saving for goals shows what to set aside each month. Loans show payments made, what is left and the last payment; a skipped payment moves to the end of the loan.

| Follow-up | Answered by | Status |
|---|---|---|
| How long could I live if I lost my job? | Emergency fund in months of Average monthly income | Partial: it should be months of *spending*, since spending is what continues when the salary stops |
| I paid for a repair from the emergency fund: what now? | The fund shows what is left; Free cash is unchanged | Partial: nothing reminds him to refill it (Mohab step 14) |
| When is the car loan paid off? | Loans › last payment | Answered |
| Can I pay the loan off early? | — | Missing: no early payoff or lump-sum payment |


**7. Is my data right?** Type the balance the bank shows and settle a small difference with one adjustment, review imports for gaps and duplicates, and run Checks. There is no stale-price warning yet (partial).

**8. What changes when my pay changes?** A salaried user's pay is not one flat number: raises, a yearly bonus or profit share, a 13th month, Ramadan and Eid grants, and paydays moved early for holidays.

| Follow-up | Answered by | Status |
|---|---|---|
| Where did my bonus go? | Money in › Bonus; Expense analysis for the same period | Answered |
| Does a bonus change my budget? | `BudgetService.income_average` excludes `EXP.WORK.BONUS` by default; a bonus does not lift Average monthly income | Answered; Mohab step 17's average is instead affected by January salary booked in December (step 18) |
| I changed jobs: what happens to my income figures? | Stop the old salary (its history stays) and add the new one | End-of-service pay is irregular and excluded by default; the no-pay-month average still skips zero-income months (Mohab step 27) |
| Was I paid my raise? | The account register shows the new amount; Cash planning › Recurring keeps the scheduled payment Due until he links it by hand | Partial |

Money held for others is left out of every owned, budget and performance view. Transfers are never income or spending. Refunds reduce spending in their original category.

## Reference workflow: a month with Mohab

The acceptance persona is **Mohab**, 31, salaried, in Cairo. He earns 45,000 EGP a month from ACME Egypt, paid into CIB. He has a CIB payroll account, a cash wallet and Vodafone Cash; an NBE 3-year certificate; and a THNDR account with COMI, Fawry and a money market fund. His gold is an L'Azurde ring bought by card and a gold pound from his grandmother. He holds 10,000 EGP of his mother's money in CIB. He pays rent, internet, phone and electricity monthly, and has a 24-month car loan.

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

**The rest of Mohab's year.** Steps 1–10 are one ordinary month. Steps 11–28 carry the same household from October 2026 to September 2027 through what a salaried year brings: fees, a refund, a repair, a bonus, an early payday, a raise, Eid, installments, a share sale, a rent rise, a holiday, and a job change with a month between jobs. Every month also has the routine: salary on the 1st, rent on the 3rd, the car loan on the 5th, groceries, phone, internet and electricity.

`tests/test_mohab_year.py` runs these steps through the services, one test per step. A step that is wrong today is a strict expected failure. When its fix lands, the test fails as an unexpected pass, and its marker and the **Today** column below must change together. Steps 1–10 are still driven in a browser.

| # | When | Step | What must be true afterwards | Today |
|---|---|---|---|---|
| 11 | Oct | An ordinary month | Every recurring payment and the loan settle themselves; nothing is due at month end | Answered |
| 12 | 10 Oct | Withdraws 2,000 at a CIB ATM, with a 25 fee | Net worth moves by −25 only; the fee is in Fees & Charges | Answered |
| 13 | 15 Oct | Returns August's 1,299 Amazon purchase | Shopping goes down by 1,299 | Partial: it goes down in October (October reads −1,299) and August keeps the purchase |
| 14 | 18 Oct | Pays a 6,500 car repair from the emergency fund | The fund drops to 13,500; Free cash is unchanged; cash drops by 6,500 | Answered; nothing reminds him to refill the fund |
| 15 | 20 Nov | Gets a 300 COMI dividend | Money in shows Dividends next to Salary; pay is unchanged | Answered |
| 16 | 10–22 Dec | Pays a 1,200 work Uber; ACME pays it back | Work spending for December is 0; the refund is not income | Answered |
| 17 | 20 Dec | ACME pays a 90,000 year-end bonus | Net worth +90,000; Average monthly income stays 45,000 | Answered after Mohab confirms the separately suggested early January salary; Bonus itself stays excluded |
| 18 | 24 Dec | January's salary comes before the holidays | It settles January's payment; January's forecast expects no more pay | Answered after Mohab confirms the early-pay suggestion; cash-flow reporting still uses 24 December |
| 19 | Jan–Apr | Plans 9,000 car insurance due 30 April, pays it from the goal | Saving for goals shows 2,250 a month | Answered; but no cash moves into the goal until he assigns it, and it cannot pay the bill until he does |
| 20 | 1 Feb | Raise to 50,000 | February settles after Mohab confirms the changed-amount suggestion; later payments are planned at 50,000 only after he chooses it; December stays paid at 45,000 | Answered with confirmation, not automatic plan changes |
| 21 | 9–10 Mar | Eid: gives 3,000 in cash, receives 1,000 | Gifts & Donations and Gifts Received; gifts do not change the salary average | Answered; the rolling January–March salary average is 48,333.33 after January's 45,000 pay and two 50,000 pays |
| 22 | Mar | Buys a phone on 12 installments of 2,000 from 15 April | What you owe +24,000; each installment settles itself | Answered (as a loan; credit cards are out of scope) |
| 23 | 20 Apr | Sells 75 of 150 COMI for 7,100 after a 25 fee; moves it to CIB | 75 left; Gain from sales after fees; April's Money in is only the salary | Answered |
| 24 | 3 Jun | Rent rises 10% to 13,200 | June settles; July onwards is planned at 13,200 after Mohab accepts the prompt; reserve target is reviewed separately | Answered with confirmation; neither future plan nor reserve changes silently |
| 25 | Jul–Aug | Sets aside 15,000 for a Sahel trip; spends 14,200 | 800 left in the goal | Answered |
| 26 | 31 Aug | Leaves ACME with 30,000 end of service; adds Valeo at 55,000 from 1 October | The old salary stops with its history; Average monthly income stays 50,000 | Right since Categories marks Bonus irregular |
| 27 | Sep | Between jobs, no pay | Next income is Valeo on 1 October; the average does not rise | Known gap: zero-income months are skipped by the average; the test checks non-increase, not zero-month inclusion |
| 28 | 30 Sep | Reads the year | Money in 651,300 and Money out 295,186; Change in what you own 357,364; loans still to pay 34,500; Checks pass; nothing is due | Answered, except *why* net worth changed (M3.2) |

**What users reported.** After the year's answers are read, Mohab walks through the pain points in `user feedback/user-feedback-batch-001.md`: leaving and resuming an import, a 300-row seven-column statement, a review with an error, transfer and category choices, the emergency target against his cash, All time and past-month reports, categories, a monthly investing goal, bulk editing, valuing a fund or his share of the family flat by its total. Fixed points are checked as answers. Open ones are strict expected failures: the waiting import is not offered back or discardable, one CSV at a time, categories start as "Uncategorized" and lack their group, no warning when the emergency target exceeds cash, Your position follows the period, a year of spending is drawn day by day, the Categories sign key, no monthly investing goal, no bulk edit, and no direct value for a fund or an asset like a flat. Loading speed, keeping the scroll position, compact review rows, chart colours and the register balance are not checked from the screens.

**Not scripted, because Lightning cannot record them yet:**

- **A gam'eya.** Example: 10 months of 5,000, with the 50,000 pot in month 4. The payments are commitments, and the pot is his own money back, not income. Lightning has no gam'eya type, and an inflow needs an income category.
- **The NBE certificate maturing.** Its portfolio forecasts interest and maturity proceeds; Mohab enters the actual principal redemption and statement interest manually. Forecasts never post ledger activity automatically.
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
| 4 | ~~One review inbox~~ Done 2026-10-05 | Monarch, Copilot "to review" | Needs you now lists every waiting statement and uncategorized activity; recurring suggestions wait for the owner's answer |
| 5 | Reminders | Monarch, Rocket Money, Simplifi | A user who doesn't open the app never sees a due bill |
| 6 | Multi-currency | Lunch Money, YNAB | Many Egyptians keep USD savings or earn USD |
| 7 | Spending history | Monarch | Answers "am I improving?" |
| 8 | Give every pound a job | YNAB "Ready to assign" | Closes question 4's last follow-up |
| 9 | Watchlists | Simplifi | Track one habit without a full budget |
| 10 | Shared household | Monarch partner access | Couples manage money together |
| 11 | Guided first setup | Monarch, YNAB onboarding | Mohab's first run needed six account forms before seeing anything |
| 12 | Receipts and attachments | Monarch, Lunch Money | Warranty and gold purchase receipts |

**Known finance gaps** (the early-pay, raise and rent paths now require explicit confirmation; no-pay-month averaging in step 27 only has a non-increase assertion):

- **Left open by the 2026-10-05 audit** (its other wrong numbers are fixed, `tests/test_audit_numbers.py`): a certificate's interest lands on the bank as Investment › Interest with no link to the certificate, so Net gain and the return leave it out; a payment scheduled on the 31st moves to the 30th after a shorter month and stays there; the Investments sparkline and the net worth chart show a recorded opening balance as a jump.
- **Unconfirmed early salary** remains in the bank-posting month of the income average and may leave a future salary payment due. The Recurring tab suggests the plausible match; Mohab must confirm the specific transaction before the scheduled-month average and forecast adjust.
- **A changed recurring amount** prompts a future-plan update and a reserve review, but the user must choose them. A reserve is named only when the payment is explicitly linked to it; a name or category match does not silently change cash assignments.
- **CD projections** use an actual/365 day-count estimate, not a bank guarantee. Interest is never posted automatically. Existing account-level `cd_terms` stay visible as legacy and are not automatically converted. Cash in old `DEPOSIT` accounts must be moved out; these legacy terms remain pending a safe conversion workflow. Actual bank interest entries are not yet linked to certificates to reconcile projections.
- **The emergency fund** should count months of spending, not of income.

Bank sync and bill negotiation are not adopted. Any sync first needs a provider and regional coverage; local CSV stays the foundation. A "safe to spend" figure must always say which obligations and income it includes. Simplifi's projection, which leaves out planned spending, shows why.

## UX plan (guideline 3.6)

From a full UX review on 2026-10-03: Mohab's year at a 1,366 × 768 window (the PC app), every screen checked against Brand guideline 3.6 Part A. The structure (Overview, Budget, Investments, Expense analysis, Cash planning, Held for others, Settings, accounts in the sidebar) stays. Batch 1 is done; the rest is ranked by what a real user meets first.

**The user's route.** A salaried user opens Lightning to answer, in order: *Where do I start?* → *Is my money in?* → *How much can I spend before payday?* → *What is due?* → *Am I on plan?* → *Where did it go?* → *How are my investments?* → *Is my data right?* Each tab answers one of these first; the Overview's Needs you is the to-do list across them.

**Done in batch 1:** KPI cards coloured by meaning with an icon tile; Needs you words ("Personal over plan", "Sahel trip is past its date"); an "Over plan" card instead of a negative "Left in plan"; no impossible savings rates (−1,375.2% becomes "—" with the gap in words); four, then Other in donuts, the Sankey, treemaps, bars and small multiples; section headers carry only the title and dates; trend month labels no longer overlap; money out in ink and transfers unsigned in registers; soft field wells; Nile sub-tabs; no all caps; the register's balance no longer clipped at 1,366px; budget spent in soft rose; a Back route on transaction, holding, planner and prices pages; Accounts calls its total What you own.

**Next, by impact:**

1. ~~**First run.**~~ Done 2026-10-03: a "Get set up" card on the Overview until five steps are done; the welcome lists certificates and uses real icons; a new bank account leads with Import a statement; Plan shows an empty state instead of a forecast from no income.
2. ~~**Import review, one decision per name.**~~ Done 2026-10-03: one choice per imported name with its rows collapsed under it (Mohab answers 17 names instead of 43 rows; the 300-row statement is 287 KB instead of 2.2 MB); "Discard this import"; Import CSV offers to continue or discard a waiting review. Still open: the button says "Post ready rows" while undecided rows post as Unaccounted.
3. ~~**The category picker.**~~ Done 2026-10-03: focus lists every choice under its L1 header and selects the current text; the import starts on an empty "Choose a category".
4. ~~**Bulk edit.**~~ Done 2026-10-03: Set category for selected rows; transfers, investments and splits are skipped and counted. Still open: bulk counterparty.
5. **One name, one number.** Keep the Free cash breakdown on the Overview and Plan only; Reserves shows one line. One "If sold" figure and name. Loans still to pay once per tab. Remove the Overview's second donut ("What you hold") and the column waterfall that repeats the Net flow list.
6. **Registers as two-line rows** (A11): counterparty and amount, then category · account · date with the balance under the amount; no Action column (row click and right-click already do it); header figures in whole EGP.
7. ~~**Honest prices.**~~ Done 2026-10-03: Needs you says "Prices are out of date" (older than about two months) and links to Update prices; the holding page flags its own price.
8. **Reserves table** as two-line rows with a meter; the emergency fund shows "13,500 left of 20,000 · 6,500 used · Refill"; paid reserves move to completed.
9. **Words and numbers sweep:** whole EGP on big figures everywhere; no jargon ("custody subledger", "M4", "5 MiB", internal codes on Prices); sentence-case "counterparty"; segments for 2–4 choices; the app's own dialog for Deactivate.

**Owner decisions (2026-10-03):**

- Budget's low-confidence background estimates count in Left in plan, with a small "!" beside them that says they are low confidence and why.
- The Overview's Investments section shrinks to one row of figures with a link to the Investments tab.

**Still open (asked again in plainer words):**

- *Recurring suggestions.* Cash planning › Recurring has a "Looks recurring" list that offers to track things that repeated. It offers Carrefour and Talabat (shopping that changes every month, which belongs in the budget) and the NBE certificate's interest (already in the forecast, so tracking it counts it twice). Stop offering those, and add a "Not recurring" button to hide a suggestion?
- *Menu.* The main menu has Overview, Budget, Investments, Expense analysis, Cash planning, Held for others and Settings. Your accounts list and "every transaction across all accounts" are reachable only from the account list in the left column. Add "Accounts" and "Transactions" to the main menu?

## Roadmap

### Pre-ZIP release readiness

Verified UI fixes: Budget overlap at about 941px, the Cash planning tab strip and shared period pill at 390px, Settings data-card overflow, and account/all-transactions registers scrolling inside their cards. Holdings now uses five columns with expandable details, and the reviewed own-data fields have type-and-pick controls. Mohab's early salary, raise and rent scenarios pass with explicit confirmations; the CD terms and forecast mechanism is covered by focused tests. A full interactive click-through of every control and acceptance on an ordinary Windows PC remain outstanding before the ZIP release. No new ZIP is implied by these source changes.

| Milestone | State | Next |
|---|---|---|
| M0–M1 Foundation and cash accounts | Shipped | — |
| B Budget, B.1 Budget flow | Shipped / in progress | Change one category without the full grid; first-use flow |
| M2 Reports and corrections | Partial | Balance adjustments, month close |
| M3 Manual investments | Shipped | — |
| M3.1 Instrument catalogue | Partial | Coverage and identifier quality |
| M3.2 Wealth history | Partial | Wealth-change bridge; owned-only XIRR (net-worth trend is shipped) |
| M4 Market data and FX | Planned | Wider prices, multi-currency accounts, FX revaluation |
| M6 Deposits and gold details | Partial | Bank-specific CD portfolios, per-certificate purchase/redemption ledger activity and forecast-only interest are built; next: ordinary-PC acceptance, legacy conversion, statement reconciliation, local gold costs and buyback |
| Physical gold items | In progress | Item purchase/sale and report integration |
| M7 Planning and imports | Partial | Shipped: CSV import, Cash planning, and linking statement rows to entries already recorded (no money counted twice). Next: reminders |
| Search | Planned | One typo-tolerant search across pages and records (contract in Architecture) |
| Multiple devices | Protocol foundation only; no device sync | Follow the [dependency roadmap and task reading guides](proposals/multiple_devices.md#15-implementation-work-packages). Restore has an early locked-profile UI, encrypted publication and forward P1–P4 resume; ambiguous repairs and ordinary Windows acceptance remain. CSV/manual matching (task 20) is delivered in the import review; run the Android trial alongside recovery work, then join protocol/transport tracks for phone-home acceptance. Include dated offline PC analysis. Fingerprint unlock and an interim PC-home release remain owner choices in NOW.md. |
| In-app updates (Windows) | Planned for later | An **Update** button: check `Lightning-downloads` for a newer version (on press, or an opt-in automatic check); download it, verify its signature (key kept outside GitHub), unpack beside the current app, then a small helper swaps folders and reopens, keeping the old one for rollback. Profiles in Documents/Lightning are never touched. Refuse while a lend or hand-back is unfinished. Evaluate Inno Setup or Velopack against a hand-made helper; a code-signing certificate is optional (it removes the unknown-publisher warning). Pairs with multiple devices task 19 (update compatibility). Android updates come from Google Play. |
| Desktop app (v0.5.0b1) | Development preview | `Lightning.exe` for Windows and `--profiles` on Linux, with password-protected encrypted profiles in Documents/Lightning. Encrypted backup restore and exact-journal forward resume are early previews; next: unresolved-evidence repair, Windows fault acceptance, legacy import, native file pickers and ordinary-PC testing before a Windows-first beta for a few testers, hosted on the owner's website (design in Architecture). |

**Next up:** reminders.
