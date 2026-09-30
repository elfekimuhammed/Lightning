# Lightning — persona walk-through · v6 · "Omar in Cairo"

**Version v6** · 2026-09-30 · code: `main` @ `246bcc6` · empty database, everything done through the browser (Playwright, real fonts) with `LIGHTNING_TODAY=2026-09-30`. Bug numbers (#) refer to `BUG_REPORT_v6.md`.

## Who Omar is
- 31, product manager in Cairo; salary **45,000 EGP** paid into **CIB** on the 1st.
- Pays rent of 12,000 to his landlord by **InstaPay**. Groceries at Carrefour/Seoudi by card; Talabat and Uber.
- Withdraws 3,000 cash at the ATM each month and tops up **Vodafone Cash** by 1,000.
- Sends Mom 2,000 a month, and is **holding 10,000 of Mom's money** in his CIB account.
- Has a **100,000 EGP NBE 3-year certificate** (monthly interest 1,833.33 paid into CIB).
- Invests through **THNDR**: COMI, Fawry and a money market fund.
- Owns gold: an **inherited 21K gold pound (8 g)**, and a **21K ring** bought at L'Azurde on 2026-09-14 for 18,450 (1,950 workmanship).

What he typically wants to know: *How much is really mine? How much can I spend before next salary? Where did September's money go? Is my gold up? How are my stocks doing after fees? How much of this is Mom's? When does my certificate mature? Am I saving enough? Do I owe zakat?*

---

## Part 1 · The workflow, step by step

| # | Step | Where | What happened | Felt awkward |
|---|---|---|---|---|
| 1 | First open | `/` | A welcome page asks "Where do you keep your money?" with Cash / Bank / Brokerage / Physical asset | Icons are text glyphs (▣ ▤ ↗ ◇). The "Bank" tile covers both bank and deposit accounts, but the **certificate** (the most common Egyptian saving product) has its own type, which only shows up in the dropdown. |
| 2 | Add 6 accounts with starting balances on `1/7` | `/accounts/new` | All created; `1/7` became 2026-07-01 | **Currency is locked to EGP** ("Other currencies arrive with exchange rates (**M4**)"), so his USD savings have nowhere to go. The certificate help says "include the term, annual return, and maturity date **in Notes**": nothing uses them afterwards. Vodafone Cash has to be a "Cash wallet". |
| 3 | Upload the CIB statement (40 rows, dd/mm/yyyy, Debit/Credit columns) | Account › More actions › Import CSV | Column matching was good: Date and Debit/Credit were detected automatically | **Description was mapped to Notes, not Counterparty.** Every CIB line carries its payee there, so he had to change it himself. |
| 4 | Review the rows | `/accounts/1/import/1` | **All 40 rows are open and marked "Needs a decision"**: a 19,871 px-tall page | Each row has 10 inputs, and counterparty needs **three controls** (typed name, a "Search saved Counterparty" box and a "Choose explicitly / leave unlinked" dropdown). Nothing cleans up "POS PURCHASE CARREFOUR CITY STARS 4587" into "Carrefour", or suggests a category from "SALARY", "TALABAT" or "UBER". Nothing recognises "ATM WITHDRAWAL" as a transfer to cash, "VODAFONE CASH TOP UP" as a transfer to Vodafone Cash, or "TRF TO THNDR" as a transfer to THNDR. It took **104 interactions for 40 rows**. |
| 5 | Post | "Post ready rows" | **500 error** (#85). After working around it: "Nothing was imported", because Carrefour, Uber, Mom… "already match a saved counterparty" (#86) | The workaround is "Create" on the first row of each merchant and "Leave unlinked" on every repeat, which leaves most rows showing "—" in the register. The error view listed all rows, with the real problem (Mom's row) buried (#88). |
| 6 | Mom's 10,000 | Import row → owner | The owner picker was empty, because Mom had never been an owner before (#102) | He had to skip the row and add it in the register (Category "Money Held for Others", Whom "Mom"). That worked, and Money from others shows "Mom · CIB Payroll · 10,000". |
| 7 | Move 20,000 to THNDR | Import row → "Internal transfer to THNDR" | Worked; both sides are correct | — |
| 8 | Buy COMI (150 @ 81) and Fawry (500 @ 8.9) with fees | THNDR › "Record an investment transaction" (collapsed) | Saved; cash left 3,347 is correct | The form is collapsed under a 26 px link. **Fees can only be typed after ticking "Fees are excluded from the total"** (#108). A THNDR confirmation shows the all-in total, so he'd enter it as "included" and the fees would be lost. |
| 9 | Buy a money market fund for 3,000 | same | "Enter the number of units." | Egyptian money market funds are bought **by amount**, and units are only known the next day. He had to guess 25 units. |
| 10 | Buy the ring with his CIB card (the same purchase appears in the statement) | Gold at home › Add item → "Purchase, sale, or add an existing holding" | Item created (21K, 4.3 g); purchase saved against CIB; the imported POS row had to be **skipped by hand** to avoid counting it twice | Two steps (create the item, then find the right collapsed form under the right item). The gold price reference must be chosen even though the karat already says 21K. The karat list offers **22K with no price reference**. Nothing links the imported "L'AZURDE" POS line to the purchase, so the user must know to skip it. |
| 11 | Add the inherited gold pound | same → "Add existing holding" | Requires a **cash account** even though no cash moves (#100) | It also requires a cost. For an inheritance he doesn't know one, so he typed today's value. When he added it to the wrong item by mistake, there was **no way to delete it** (#95). |
| 12 | Record cash and Vodafone Cash spending | Account register quick-add | Worked | **Every new name needs a second confirmation** ("Create … as a new Counterparty") even when the app says "No close match found". Every save adds noise such as "Budget · Eating Out: no covering limit". The category picker shows "Transportation" and "Travel" twice (Personal and Work) with no group. |
| 13 | Month-end prices (COMI, Fawry, fund, 21K gold per gram) | Investments › Update prices | Saved | Typing "30/9" on the 29th silently became **2025-09-30** (#94), and the gold was valued with that "current" price with nothing flagged (#106). The page also lists the ring and the pound with their own price inputs next to the 21K reference, so it isn't clear which one to fill. |
| 14 | Emergency fund 20,000; create the budget plan | Reserves; Budget › Create plan | Both saved | The Reserves page shows two "allocated" boxes (the emergency fund and a new reserve) with no Save button; the emergency one autosaves. |

---

## Part 2 · Omar's questions: where the answers were, and what would work better

### Q1. "How much of this is really mine?"
- **Found:** Overview › Your position › **What you own 255,090.24**, "Excludes money held for others"; the sidebar shows All accounts 265,090.24.
- **Good:** one clear number and the right exclusion.
- **Better:** the guideline's "In your accounts 265,090 − Held for others 10,000 = What you own 255,090" breakdown, shown right on the card. Today the card's parts are Cash / Bank / Deposits / Brokerage / Physical assets, and the Mom deduction only lives in the sidebar and on Money from others.

### Q2. "How much can I spend until the next salary?"
- **Found:** Overview › **Free cash 58,295.24** (cash you own 78,295 − reserves 20,000); Budget › **Left in plan 2,324.62**.
- **Confusing:** two answers on two tabs, 25× apart, and the note "Plan room is not free cash" doesn't say which one to use. Free cash also counts 12,680 in the cash wallet that Omar has mostly spent without recording it.
- **Better:** one "Safe to spend until 2026-10-01" figure on the Budget tab (plan left, capped by free cash), with the days left and the daily pace. Also a quick "count my cash" action on cash wallets to reset the balance.

### Q3. "Where did September's money go?"
- **Found:** Overview › Quick expense analysis (Personal 21,550.50, top categories) and Expense analysis.
- **Confusing:**
  - Expense analysis shows only **"Personal · 100.0%"**; you must click to see categories.
  - "When did it change?" shows a single row for a monthly view.
  - Rent (12,000) dominates, and money sent to Mom ("Gifts & Donations 2,000") is mixed into spending.
- **Better:** open with the category bars (the largest first, in soft rose), the rent shown as "fixed" versus "flexible" spending, and a 3–6 month trend line on the monthly view (the guideline's trend card).

### Q4. "Did I spend more than last month?"
- **Found:** Expense analysis › "Change from comparable period **922.90 more** · Previously 20,627.60".
- **Confusing:** on YTD it says "65,801.75 more · Previously 0.00", comparing against an empty period, which the guideline forbids.
- **Better:** compare **month with month** only; say "No earlier spending to compare" for a first period; show per-category deltas (Food +1,000, Transport −140).

### Q5. "Did I save this month?"
- **Found:** Overview › Cashflow › **"You saved 54.0% of money in"**, net +25,282.83.
- **Confusing:** the big green number collides with the ring (#97).
- **Better:** fine as a concept. Add the 3-month average savings rate beside it.

### Q6. "What is my gold worth today, and did the ring gain or lose?"
- **Found:** Gold at home › items (pound 37,200, ring 19,995); Investments › holdings "Up / down +8,200 / +1,545".
- **Confusing:**
  - The ring shows a **gain of +1,545** three weeks after buying it, but Omar paid 1,950 workmanship that he'd never get back when selling.
  - The price that drives it is a per-gram reference he typed himself (no automatic Egyptian 21K price), and its age isn't flagged.
  - "Physical assets 57,195" (Overview) and "Gold 57,195" (Investments) are the same thing under two names.
- **Better:**
  - A gold card: grams by karat (8 g + 4.3 g 21K), today's 21K price with its date, and the buy-back estimate after the dealer's cut.
  - Workmanship shown as a sunk cost ("value at gram price 19,995; you paid 1,950 for workmanship").
  - A stale-price badge.

### Q7. "How are my THNDR stocks doing after fees?"
- **Found:** Investments › Every holding (8-column table): COMI 12,975 vs invested 12,185; Fawry 4,700 vs 4,468. The Overview investment card.
- **Confusing:**
  - The 8-column table has no percentage return.
  - "Returns by asset class" mixes the ring's gold price change (+1,545) with stock returns (+1,075), and "Biggest movers · financial assets" lists the gold ring first (#101).
  - "Since-inception **XIRR 155.91%**" annualises 3 months of history (#110); the guideline says never annualise under a year.
- **Better:** a two-line row per holding (the guideline's list): name and account on the first line; value and "+790.00 · +6.5%" on the right; fees paid under it. Return by class only for holdings owned all period, or labelled "since purchase".

### Q8. "How much did I pay in fees this year?"
- **Found:** nowhere. Search "fees" only finds categories. Bank fees are 45.00 in "Fees & Charges"; broker fees (35 + 18) are folded into cost basis, or lost (#108).
- **Better:** a "Costs" line on Expense analysis combining bank fees, broker fees and workmanship.

### Q9. "How much of Mom's money do I hold, and where?"
- **Found:** Money from others › "Mom · CIB Payroll · 10,000.00"; CIB account header "Held for others 10,000".
- **Good:** clear.
- **Better:** a running history per person (+10,000 on 2026-08-12), and a "give back" button that records the return transfer. The page title "Money from others" and the table "Cash held for others" are two names for one thing (the guideline says "Held for others").

### Q10. "When does my certificate mature and how much interest will I get?"
- **Found:** nowhere. The certificate account only shows its opening balance. Interest appears as "Investment › Interest" income in CIB each month, not linked to the certificate. The term, rate and maturity can only be typed into Notes.
- **Better:** certificate fields (rate, payout frequency, maturity date, payout account). Show "Next interest 1,833.33 on 2026-10-15 · matures 2029-01-15", and a "Needs you" item a month before maturity.

### Q11. "How many months could I live on my emergency fund?"
- **Found:** Reserves › "**1.3 months** of average salary (15,000)".
- **Wrong:** his salary is 45,000; the app divides by 6 months although only 2 have data (#87). The true figure is 0.44 months of salary, and it should really be measured against **spending** (21,550/month → 0.93 months).
- **Better:** "Covers 0.9 months of your spending (target 6 months = 129,300)", with a progress meter.

### Q12. "Is my net worth growing?"
- **Found:** Overview "Change during this period +26,827.83"; the Investments chart covers the portfolio only.
- **Confusing:** YTD says "**Change +255,090.24**", treating the whole starting balance as growth; there's no net-worth trend chart anywhere.
- **Better:** a monthly What-you-own line (Jul 225k → Sep 255k) on Overview, with starting balances excluded from "change".

### Q13. "Do I owe zakat?" (a very common question in Egypt)
- **Found:** nowhere.
- **Better:** a small zakat helper on Birdview: zakatable assets (cash you own + gold at 21K grams × price + fund/stock value) compared with the nisab (85 g of 24K); 2.5 % due; excluding Mom's money and personal-use jewellery if the user chooses.

### Q14. "How much is my USD worth in EGP?"
- **Found:** impossible. Accounts are locked to EGP.
- **Better:** multi-currency accounts with a daily EGP rate. This is a big need given the Egyptian pound's moves.

---

## Part 3 · How each tab could flow better (answer first, then detail)

| Tab | Its question | Today | Suggested flow |
|---|---|---|---|
| Overview | Where do I stand, what needs me? | Good new layout; position then cash flow | Add the "In your accounts − held for others" breakdown; a net-worth trend; "Needs you" items for stale prices, a maturing certificate, and unreviewed imports |
| Budget | Am I on plan? | Three vivid/plain tiles, then a long table of every category with Track / One-off chips | Lead: "Safe to spend until payday"; support: over-plan categories first (meters); fold untracked categories to "N more" |
| Birdview | What is my wealth made of? | Four tiles incl. two liquidity estimates, then composition | Lead: what you own by type (cash / deposits / gold / stocks) as one share bar; support: "If you sold today (estimate)" with the factors; add a zakat card |
| Investments | How are my investments doing? | Result card, a value chart with 0.00 months, an 8-column table, 4 folded sections | Holdings as 2-line rows with % return; a gold-by-grams card; certificates listed as holdings with rate and maturity; hide months before the first holding |
| Expense analysis | Where did it go, compared with last month? | Personal 100% bar; a one-row trend | Category bars first; month-over-month delta per category; a 6-month trend; fixed vs flexible split |
| Reserves | Can I cover emergencies and goals? | Three tiles (lead on the right), a text-heavy emergency card, an empty table | Coverage in months of **spending**; one meter per goal; no empty table |
| Money from others | Whose money do I hold? | Two tables + 3 folded sections | One card per person with balance, where it sits, history, and a "Give back" action |

### What felt most awkward, in one line each
1. The **bank import** is the main entry path and the weakest step: no description clean-up or auto-categories, recurring merchants break it, and a 500 on error.
2. Buying gold with a card needs **the item, the purchase and a manual skip** of the imported card line.
3. **Certificates** are just a balance; the app knows nothing about rate, interest or maturity.
4. **Fees and money market funds** don't fit how THNDR shows them.
5. **Two "spendable" numbers** (Free cash vs Left in plan) and **two "Investment holdings"** numbers.
6. **Mistakes can't be undone** for opening holdings; new names always need an extra confirmation.
