# UI and UX audit · tab by tab · 2026-09-30

**Data:** Omar's household (see [Project Overview](PROJECT_OVERVIEW.md#reference-workflow-a-month-with-omar)) as of 2026-09-30. Checked at 1280 px and 390 px against the [App guideline 2.1 · Bloom](APPLICATION_BRAND_GUIDE.md) and the [main questions](PROJECT_OVERVIEW.md#main-questions-and-follow-up-questions).

**Lens:** a hurried user who reads one number and one sentence per card. A tab passes when its main question is answered at a glance, the follow-ups are one tap away, and nothing on it breaks a guideline rule.

## Rules broken on several tabs

| Rule (guideline) | Where it breaks today | Change |
|---|---|---|
| "The vivid Meadow gradient is not used on any card." The lead card is the soft gradient (#E0F5E9 → #D7ECF7) with ink text. | The lead cards on Expense analysis, Budget, Birdview, Investments and Reserves use the vivid green-teal-blue gradient with white text. On Investments the new formula line and toggle are dark on it and can't be read. | Every lead card uses the soft lead gradient and ink text; the vivid gradient stays for the logo bar only. |
| "Charts that add up": hand-drawn SVG, values on the marks, colours follow meaning, bars from zero, too little history says so. | Charts exist on only 3 tabs. The allocation bars use a blue-teal gradient instead of class colours; the investments trend draws zeros before the first holding; Expense analysis shows a one-row "trend". | One set of chart components (trend, spending bars, budget meters, donut, share bar, sparkline, breakdown), used the same way on every tab. |
| "One note, if it asks you to act." Sections pair a lead with a support card. | No tab says its answer in a sentence. Answers hide in numbers, tables or collapsed rows. | A **key notes** row under each page title: up to three one-sentence notes (the answer, what changed, what needs you), each with its number and one link. |
| "More than five table columns." | The holdings table has 8 columns and cuts off Horizon at 1280 px. | Holdings as two-line rows: name and account, then value, cost and unrealized gain. |

## Tab by tab

### Overview: "Where do I stand, and what needs me?"
- **Works:** net worth with its parts; free cash with its formula; needs-my-attention list; investments at a glance.
- **Missing:** no picture of change. Cash flow is two bars with no history; "Quick expense analysis" is a toggle list rather than the guide's bars.
- **Change:**
  - Key notes: net-worth change, what you kept this month, what needs you.
  - A six-month money in and out trend in Cash flow.
  - "Where it went" as soft-rose bars (largest first).
  - The investment allocation as a donut in class colours.

### Birdview: "Where is my wealth?"
- **Works:** How what you own adds up; If you sold today with sale factors.
- **Missing:**
  - composition is a list with no visual;
  - the "Deposit and holding mix" bars use the old gradient;
  - the lead card is vivid.
- **Change:**
  - A donut of What you own (cash, deposits, stocks, funds, gold, other) in class colours.
  - The "How it adds up" rows keep their result band.
  - Key notes: largest part of your wealth, cash share, how much selling would cost.

### Expense analysis: "Where did my money go?"
- **Works:** Money out and a comparison with last month.
- **Missing:**
  - Only one grey "Personal" bar is shown; the categories people ask about are hidden.
  - "When did it change?" is a one-row list for a monthly period.
  - The lead card is vivid.
- **Change:**
  - Category bars (level 2, soft rose, largest first, value at the end, links to transactions).
  - A six-month spending trend with the Personal plan as a dashed line; months over plan turn rose.
  - Key notes: the top category's share, and the change against last month.

### Budget: "Am I on plan?"
- **Works:** Left in plan, Spent, Planned; rules; carryover.
- **Missing:** every category sits inside one collapsed group, with no meters. You can't see which category is over without opening and scanning.
- **Change:**
  - Budget meters for each planned category, over plan first ("925.00 over · 2,300.00 of 1,375.00").
  - A share bar of the month's plan that is used.
  - Key notes: what's left per remaining day, the categories over plan.

### Investments: "What do I hold, and how did it do?"
- **Works:** Result with its parts; portfolio trend; per-class results.
- **Missing:**
  - the vivid lead card, where the formula can't be read;
  - three header actions wrapping onto two rows;
  - a trend drawn at zero before the first holding;
  - the 8-column table;
  - gradient allocation bars.
- **Change:**
  - Soft lead card.
  - The trend starts at the first month with holdings.
  - An allocation donut in class colours.
  - Holdings as rows.
  - Key notes: the best-performing class, and valuations at cost.

### Cash planning › Plan: "How much can I actually spend?"
- **Works:** Safe to spend and its parts; What you owe; next 30 days; forecast table.
- **Missing:** the forecast is a table only; the lowest point is one line of text.
- **Change:**
  - A forecast line (ends with per month) above the table, with the zero line and the lowest point marked.
  - Key notes: safe to spend until payday, the next payment, the lowest point.

### Cash planning › Recurring and Loans
- **Works:** clear two-line rows; suggestions; loan progress.
- **Change:**
  - Key notes: monthly bills against scheduled income.
  - The loan meter in meadow green, with "months left".

### Cash planning › Reserves: "Am I safe if something goes wrong?"
- **Missing:**
  - four equal tiles, where the vivid Free cash tile competes with the others;
  - the emergency fund has no progress against its target.
- **Change:**
  - Free cash as the soft lead.
  - An emergency-fund meter towards six months of income.
  - A key note with the months covered.

### Held for others
- **Change:** a key note with who you hold money for and the total.

## Demo readiness
- A fresh install opens on an empty welcome page, so there is nothing to show without typing a month of data.
- **Change:** a one-click **demo household** (Omar's month, dated relative to today) on the welcome page, and `python -m lightning --demo`, which opens it in a separate database so real data is never touched.

## What changed (demo pass · 2026-09-30)

Checked on the sample household at 1280 px and 390 px: no script errors, no server errors, no sideways scrolling on any tab.

**Across every tab**
- **Lead cards** use the soft lead gradient with ink text. The vivid gradient is gone from cards, so every formula line and toggle can be read.
- **Key notes:** up to three cards under the page title, on Overview, Budget, Birdview, Expense analysis, Investments, Plan, Recurring, Loans, Reserves and Held for others.
  - Each card has a tone (good, info, needs you), an icon, one sentence with its number, and at most one link.
  - A note only phrases figures a service already computed (`lightning/ui/keynotes.py`).
- **One set of charts:** `lightning/ui/charts.py` (geometry) and `templates/partials/charts.html` (markup).
  - Types: trend, bars, meter, donut, share bar and sparkline.
  - Colours follow meaning: money in green, spending soft rose, over plan strong rose, money held azure; asset classes cash, deposits, gold, equity and other.
  - Bars start at zero and values sit on the marks.
  - Every trend has a "Show the numbers" table.
  - With under two months of history, a trend says "Not enough history yet — check back next month."
- **Consistent links:** card header links share one colour.

**Tab by tab**

| Tab | Visuals | Key notes | Simplified |
|---|---|---|---|
| Overview | Money in and out by month; "Where it went" spending bars (largest first, each opens its transactions); "What you hold" donut | Safe to spend until payday, or what needs you; change in what you own; what you kept | "Needs my attention" is now **Needs you** and shows only when something does; the top-holdings table became the donut |
| Birdview | "What it is made of" donut: cash, deposits, gold, stocks, funds, other you own | Largest part of what you own; cash share; what selling everything would cost | The donut replaces the "Deposit and holding mix" bars |
| Expense analysis | Category bars (level 2, up to 8); spending trend with the month's plan as a dashed line, months over plan in rose | Top category's share; change against the month before | Category labels drop "Personal ›" |
| Budget | "Spent of plan" meters for every planned category, over plan first, in two columns | Categories over plan; left in plan per day left this month | The three summary cards fill one row |
| Investments | Portfolio trend from the first month with holdings; allocation donut | Best-performing class; holdings valued at cost | Holdings table cut from 8 columns to 5; "Update prices" moved into More actions |
| Cash planning › Plan | Forecast line (today, then how each month ends) above the table | The next payment going out (with Mark paid); the lowest point in the next three months | — |
| Cash planning › Recurring | Bills by monthly cost, largest first | Share of scheduled income that goes to bills; subscriptions per year | One bar card replaces three tiles |
| Cash planning › Loans | Payments-made meter on each loan | Payoff date, payments made, the next payment (or the payments due now) | — |
| Cash planning › Reserves | Emergency-fund meter towards six months of Average monthly income | Months covered; free cash | Free cash is the soft lead tile |
| Held for others | — | Who you hold money for, and the total | — |

**Demo:** `python -m lightning --demo`, or "See Lightning with a sample household" on an empty welcome page (`lightning/demo.py`).
- It holds Omar's last three months, dated up to today: salary, rent, groceries, eating out, bills, a gift, fees, interest, Amazon, 10,000 kept for Mom, THNDR stocks and a money market fund, gold, a budget, the emergency fund, five recurring items and a car loan.
- Everything is entered through the services, so it behaves like real data.
- Tests cover every tab opening with its key notes, and the demo's figures.

**Not done (next pass)**
- Budget: no share bar of the plan used. The meters and the left-in-plan note cover it.
- Plan: the lowest point is named in a key note but not marked on the forecast line.
- Transactions, account pages and Settings are unchanged. They answer no main question on their own.
- Dark mode: the app is light-only. The chart palette has dark steps chosen and validated, but they are not wired in.

## Crisp pass (2026-09-30)

The second UI run reported findings #134–#148. All of them are addressed except the one noted at the end.

| # | Finding | Change |
|---|---|---|
| 134–137 | Too many text sizes; headings and numbers varied by page | One scale in the stylesheet's "Crisp pass" layer. Text 12/13/14/15/17/20/28 px, numbers 40/30/24 px. 5–10 sizes per page, none under 12 px. |
| 138 | "EGP" shown four ways | Small, beside a card's main number only. Row amounts show only the number. |
| 139 | Lead cards not consistent | One soft lead card per page (`.lead-card`, or the lead tile in a row of tiles). |
| 140 | Cash planning tabs didn't show the open tab | Fixed: the tab macro compared against the wrong variable. |
| 141 | Button heights and the ⚙ emoji | 48 px in page headers and 36 px in cards; one primary action per header; a line icon for settings. |
| 142 | Four expander styles | One: title on the left, chevron on the right. "Show the numbers" under charts shares one quiet look. |
| 143 | Key notes repeated the page | Notes only for what isn't shown: what needs you (Overview), the cost of selling (Birdview), the top category and the change (Expense analysis), categories over plan (Budget), the best class (Investments), the lowest point (Plan), the bills' share of income (Recurring), the payoff date (Loans), months covered (Reserves). |
| 144 | Formulas said too often | Removed from pages. Names explain themselves (owner review, round 3). |
| 145 | Dates everywhere | The period lives in the page header. "As of" stays only where the period can move the date (Overview). |
| 146 | Navigation duplicated | Birdview sub-tabs removed; the sidebar has each page. |
| 147 | Phone | Tabs scroll on one line; dates and numbers never break. |
| 148 | Uneven card heights | Side-by-side cards stretch to the same height. |

**Still open:** on a phone, the transactions register scrolls sideways inside its card.

## Owner review, round 3 (2026-09-30)

| Ask | Change |
|---|---|
| Pick months instead of typing them; the year apart from the month | One month picker for every month box: a year row with ‹ ›, then 12 months, with future months disabled. |
| No opt-in explanations: rename what needs explaining | Every "How is this worked out?" toggle removed. "Result" became "Net gain or loss". |
| Savings rate cramped on the left | Beside Net flow on the right, behind a divider. |
| A colour for page-wide cards | A third gradient: soft green on the left, white on the right. |
| Month by month on Birdview; Needs you at the top as a toggle | Moved. Needs you is a closed row at the top of the Overview that opens into the list. |
