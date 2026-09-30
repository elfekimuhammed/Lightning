# Lightning — Omar walk-through, re-run on the fixed branch · v6.1

**Version v6.1** · 2026-09-30 · code: `claude/ui-consistency` @ `f1aa9cd` (fixes from v6) · fresh empty database, the same Omar data and steps as `PERSONA_REPORT_v6_Omar.md`, driven through the browser (Playwright, 1280 px, real fonts). Where a fix changed the natural path, Omar took the natural path this time (typing a merchant as new on every row, keeping Mom's row in the import, typing "30/9"). **1 new finding (#111).**

**Run health:** all 8 steps finished; **0 JS errors, 0 server errors**; no page wider than the window.

## Before / after, step by step

| Step | First run (`main`) | Re-run (fixed branch) | Status |
|---|---|---|---|
| Accounts, date "1/7" | Hint "e.g. 31/1"; currency note "(M4)" | 2026-07-01; hint "yyyy-mm-dd"; "Accounts are kept in your base currency for now." | ✅ fixed |
| CIB import: new name on every row | **500 error**, then "Nothing was imported", because Carrefour, Uber… "already match" | **"Import complete: 39 posted, 1 skipped"**; each merchant created once and linked | ✅ fixed (#85, #86) |
| Mom's 10,000 in the import | Owner picker empty; row had to be skipped and re-entered in the register | Posted in the import; Money from others shows "Mom · CIB Payroll · 10,000.00" | ✅ fixed (follows from #86) |
| Register after import | Most rows showed "—" (unlinked workaround) | Counterparties linked (Carrefour, Uber, Talabat…) | ✅ fixed |
| Import review screen | 19,871 px, all 40 rows open, Description mapped to Notes, 104 interactions | Same | ❌ not changed (UX) |
| THNDR fees | Must tick "fees excluded" to type a fee | Same | ❌ open (#108) |
| Money market fund by amount | "Enter the number of units." | Same | ❌ open |
| Ring bought by card | Works; imported POS line must be skipped by hand | Same | ⚠️ unchanged |
| Inherited gold pound (existing holding) | Required a cash account | Cash account hidden; saved (`OPN-2026-07-01-004`) | ✅ fixed (#100) |
| New names in the register | Extra "Create … as a new Counterparty" confirmation | Same (5 confirmations for 5 new names) | ❌ open |
| Price date typed "30/9" | Became **2025-09-30**; a year-old gold price used as current | **2026-09-30** | ✅ fixed (#94) |
| Emergency fund 20,000 | "1.3 months" of a 15,000 "6-month average" | "**0.4 months** · average monthly salary **45,000.00** · 2026-03 to 2026-08 · 2 months with salary · 270,000 six-month target" | ✅ fixed (#87) |

## Omar's questions, re-checked
| Question | Answer now | vs first run |
|---|---|---|
| How much is mine? | What you own 256,197.74 (sidebar All accounts 266,197.74, Mom 10,000) | same logic; figures differ only because the prices were dated correctly |
| How much can I spend? | Free cash 58,295.24; Budget "Left in plan 2,324.62" | still two answers on two tabs (open) |
| Where did September go? | Quick expense analysis: Housing 12,000, Food 5,386.50… ; Expense analysis still opens on "Personal 100%" | unchanged (open) |
| More than last month? | "922.90 more · Previously 20,627.60"; YTD still says "65,801.75 more · Previously 0.00" | YTD comparison still open |
| Did I save? | "+25,282.83 · You saved 54.0%"; the ring no longer overlaps | ✅ layout fixed (#97) |
| Gold worth? | Pound 37,200 (+8,200), ring 19,995 (+1,545), priced 2026-09-30 | ✅ correct date; workmanship still not shown as sunk cost |
| Stocks after fees? | COMI 12,975 vs 12,185 (+790); Fawry 4,700 vs 4,468 (+232) | same; XIRR no longer shown (#110 ✅) |
| Fees this year? | nowhere | open |
| Mom's money? | Mom · CIB Payroll · 10,000.00; "Cash ownership history · 1 entry" | ✅ wording fixed |
| Certificate maturity/interest? | nowhere | open |
| Emergency months? | 0.4 months of salary | ✅ fixed (#87) |
| Net-worth trend? | YTD "Change +256,197.74" (the whole starting balance counted as change) | open |
| Zakat / USD | not supported | open |
| Dates and signs on all tabs | No "30 Sep 2026", "Mar 2026", "-455.00" or "− 5,000" left on Overview, Birdview, Investments, Budget, Reserves, Expense analysis | ✅ fixed (#93, #103) |

## New finding

### 111. First gold price makes the month "Unavailable", while the same card still shows gains — Medium
**Repro:** Omar's data: the gold pound was added 2026-07-01 at 29,000; the ring was bought 2026-09-14; the first 21K price (4,650/g) was entered for 2026-09-30.
- Overview › Investments at a glance: "Period result **Unavailable** — A required valuation is missing".
- Investments: "Investment result · monthly **Unavailable**"; the portfolio chart shows 2026-07 and 2026-08 as "Unavailable".
- On the same Overview card, "Returns by asset class" shows **Gold +9,745.00** and "Biggest movers" shows **Gold pound +8,200.00**, crediting all the gain since July to September.

The item page valued both items "At cost" before any price existed, so the app already has a fallback. It just isn't used for past month-ends.

**Cause:** the period report needs a dated market price at the period start (2026-08-31) and has none for the 21K reference. The asset-class loop (`ui/routes/dashboard.py`) treats a holding with no opening value as new in the period and books its whole unrealized gain there.

**Seen on `main` too** (same database on `246bcc6`): pre-existing, not caused by the v6 fixes. The first run didn't show it only because of the accidental 2025-dated price (#94).

## Still open after the re-run
- **Needs your decision:** deleting a mistaken existing holding (#95).
- **Workflow gaps:**
  - import review ergonomics: description clean-up, auto-categories and transfer detection, collapsed rows
  - fees included in the total (#108) and money market funds bought by amount
  - the extra confirmation for new names; category pickers with duplicate names (#107)
  - stale prices never flagged (#106)
- **Report logic:**
  - two "spendable" numbers
  - the YTD "change" and "Previously 0.00" comparisons
  - certificates, zakat, USD
