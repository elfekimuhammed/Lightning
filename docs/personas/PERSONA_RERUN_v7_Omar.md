# Omar re-run · v7 · with Cash planning

**Version v7** · 2026-09-30 · code: `claude/cash-planning` (after "one name, one calculation") · fresh database, driven in Chromium through the screens only · pinned dates 2026-09-30, then 2026-10-06.

Omar is a 31-year-old Cairo salaried employee (ACME Egypt, 45,000 EGP/month). He has:
- **Cash:** a CIB payroll account, a cash wallet and Vodafone Cash.
- **Investments and deposits:** an NBE 3-year certificate, and a THNDR account holding COMI, Fawry and a money market fund.
- **Gold:** an L'Azurde ring bought by card and a gold pound from his grandmother.
- **Other people's money:** 10,000 EGP of his mother's money sits in his CIB account.
- **New this run:** his recurring bills and a 24-month car loan, managed in the new **Cash planning** tab.

## 1. Workflow and result

| # | Step | Result |
|---|---|---|
| 1 | Create 6 accounts (dates typed as `1/7`) | All ready; dates became 2026-07-01 |
| 2 | Import the CIB CSV (Jul–Sep, 40 rows) | 39 posted, 1 skipped, 0 errors; Mom's 10,000 shows under Held for others |
| 3 | THNDR: COMI and Fawry with fees, money market fund | Saved. To type a fee he still has to tick "Fees are extra". A fund bought *by amount* is still refused ("Enter the number of units") |
| 4 | Gold: ring by card, inherited pound as existing holding | Saved; no cash account asked for the inherited pound |
| 5 | Cash and Vodafone Cash spending (8 entries) | Saved; 5 extra "create new counterparty" confirmations |
| 6 | Month-end prices (typed `30/9`) | 4 prices saved |
| 7 | Emergency fund 20,000 and the budget plan | Done |
| 8 | **Cash planning › Recurring:** track 4 suggestions (salary, landlord, WE, Vodafone) | Pre-filled correctly (name, amount, day, category, account); September auto-matched to the posted transactions |
| 9 | Add Electricity (480, due 2026-09-25) and a car loan (24 × 2,500 from 2026-10-05, 60,000 borrowed) | Added. A loan with no payment count is refused with a clear message |
| 10 | Pay Electricity from the Plan tab popup | Recorded on CIB (preselected); counted as spending in Utilities & Bills |
| 11 | **Clock moved to 2026-10-06:** salary, rent and loan payment are due | Overview "Needs my attention" lists *Bill due: Landlord* and *Loan payment due: Car loan*, each with **Mark paid** |
| 12 | Mark salary received (Plan), rent and loan paid (Overview popups) | All settled; attention list clears |

No JavaScript errors and no server errors at desktop or phone width. Checks: 8 passed, 0 needing attention.

### The numbers hold together

| As of 2026-10-06 | Before paying | After paying | Change |
|---|---|---|---|
| Cash you own | 77,815.24 | 108,315.24 | +45,000 salary − 12,000 rent − 2,500 loan |
| What you owe | 72,000.00 (12,000 rent due + 60,000 loan) | 57,500.00 | −14,500 |
| Net worth | 183,717.74 | 228,717.74 | **+45,000: only the salary** |
| Free cash | 43,315.24 | 88,315.24 | Bills due 14,500 → 0 |
| Money out (October) | 0 | 14,500.00 | The loan payment counts as spending |
| Loans still to pay | 60,000 | 57,500 | 1 of 24 payments made |

Paying a bill that was already owed, or a loan payment, leaves net worth unchanged. Only new income moves it. Free cash and What you own read the same on the Overview, Birdview, Reserves and Plan.

## 2. Omar's questions and where he found the answers

| Question | Where | Answer found? |
|---|---|---|
| How much can I spend until payday? | Cash planning › Plan › **Safe to spend**, with its formula and parts | Yes. On 2026-10-06 it was 12,000 too low; see #115 (fixed) |
| What do I owe, and how long is the car loan? | Plan › **What you owe**; **Loans** (1 of 24, ends 2028-09-05, 57,500 left) | Yes |
| Did rent go out this month? | Recurring (statuses), Overview › Needs my attention | Yes |
| Will I run short before year end? | Plan › **Cash forecast** (3 months, lowest point) | Yes; the horizon is fixed at 3 months |
| How much are my subscriptions a year? | Recurring › **Subscriptions** 4,200 a year | Yes |
| Why is my free cash lower than my cash? | Overview › Free cash formula + Reserves + Bills due rows | Yes; the formula line answers it |
| Is my emergency fund enough? | Reserves › **0.4 months of average monthly income** | Yes, but see #119 |
| Why did net worth drop when rent became due? | Overview shows What you owe inside Net worth | Yes, the formula makes it readable |
| Is my salary late? | Nowhere | **No** (#117) |
| How is the loan showing in my budget? | Budget › Personal › *Background* (untracked) | Hard to find (#118) |
| What did my investments earn in September? | Overview/Investments › **Result** | **"Unavailable"** while Result by asset class shows gains (#111, open) |

## 3. Findings

Numbering continues from the earlier reports.

### Fixed in this run

| # | Finding | Fix |
|---|---|---|
| **112** | Account pages still said **Total · Yours · Held for others**, names the unification had retired. | Now **In this account · What you own · Held for others**, including the gold account and the asset-class breakdowns. "Yours" is on the retired list. |
| **113** | "Already in your transactions?" in the pay popup offered unrelated rows: **Talabat 540.25** for a 480 electricity bill, and **Seoudi 1,655.90** and **Mom 2,000** (a gift) for a 2,500 car loan payment. Loose matching accepted any amount within 50%. | Loose matching now needs the same counterparty, the same category, or an amount within 10%. |
| **114** | The account picker in the pay popup and the item form listed the **NBE certificate** and put the cash wallet first. | Banks and wallets first, then brokerage; deposits left out. |
| **115** | **Due bills were counted twice in Safe to spend and the forecast.** On 2026-10-06 the unpaid rent (12,000) came off free cash as a bill due, and again as Housing budget still to spend. Safe to spend showed 19,440.12 instead of 31,440.12. Income that was due but not received also vanished from the forecast. | A due bill in a budgeted category now comes off the budget room too. Due income stays in the current month's forecast. Regression test added. |
| **116** | "Left in plan this month" on the Plan tab (22,395.12) differed from the Budget tab's **Left in plan** (23,875.12): the same name with two numbers. | Renamed **Left in plan after bills** = Left in plan − Bills inside the plan. Both are in the figure table, and the formula shows under the forecast. |

### Open (for your decision)

| # | Finding | Suggestion |
|---|---|---|
| **117** | A salary that is due but not received raises nothing in *Needs my attention*. Safe to spend then measures "until 2026-11-01", as if October's salary were not coming. | Add "Income expected: ACME Egypt, due 2026-10-01, not received yet". Count it as the next income until it arrives or is skipped. |
| **118** | The car loan's category, **Loan payments**, sits untracked under *Background* in the Budget, so the 2,500 isn't planned. | When a loan exists, track Loan payments with a fixed amount equal to the monthly payment (like other apps' "fixed bills" budgets). |
| **119** | Emergency coverage now uses Average monthly income (as you asked), so the six-month target is **270,000 = 6 × income**. The usual rule of thumb is six months of *spending* (about 132,000 for Omar). | Keep income, or switch to average Money out, as a single named figure? |
| 111 | Result "Unavailable" for a period before the first price, while Result by asset class shows gains. | Carried over from v6.1. |
| — | The import review opens all 40 rows (104 interactions); a fee still needs the "Fees are extra" tick; a fund can't be bought by amount; new names need an extra confirmation (5 times). | Carried over; unchanged by this branch. |

## 4. What felt good this time
- **One vocabulary:** Omar never met two names for one number. Each derived figure shows its formula (Net worth = What you own − What you owe), so the jump from 255,717 to 195,717 explains itself.
- **Recurring suggestions** found his salary, rent, internet and phone from the CSV alone, and tracking them matched September automatically.
- **Paying from the Overview** is one click: the popup has the right amount, date and account, and the attention row disappears.
- A loan payment reduces cash, the budget and loans still to pay together, so net worth stays put, as a person would expect.
