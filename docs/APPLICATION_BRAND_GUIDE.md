# App guideline · 2.5 · Willow

**Last updated 2026-10-01.** This is the one guideline for how every screen looks, reads and adds up. It covers colour, type, cards, sections, controls, fields, lists, charts and words. It is built on the Meadow brand guidelines. The product story is in [Project Overview](PROJECT_OVERVIEW.md), code rules in [Architecture](ARCHITECTURE.md) and terms in the [Glossary](GLOSSARY.md).

**The guideline has two halves with the same sections and numbering:**

- this file, which holds the written rules;
- [`APPLICATION_BRAND_GUIDE.html`](APPLICATION_BRAND_GUIDE.html), which shows each rule as a live sample and draws every chart type. Open it in a browser.

Rebuild the page with `python docs/build_brand_guide.py` after changing either half. Its values mirror `lightning/ui/static/style.css`, and the app is the reference where the two differ. The sample figures are illustrative and don't change product requirements. The owner prefers a quiet, number-led look, and that preference outranks the brand's vivid gradients.

## 01 Seven rules behind every screen

1. **Lead on the left.** The most important card of a section sits on the left, on the soft lead gradient.
2. **Support on the right.** A white card beside the lead explains or extends it with a list, bars or a breakdown.
3. **Position, then activity.** What you have on a date comes before what changed in a period. The period control sits only above what it changes.
4. **One name per number.** Each figure has one name and one home page (see the Glossary). Other pages show it once and link to that home.
5. **Three control sizes.** 48px for page controls, 36px inside cards and for chips, and 30px for fields inside a register row. The Amount field (72px) is the one exception.
6. **Colour means something.** Green is money in and growing, soft rose is money out, azure is money you hold, and strong rose means something needs you. Asset classes keep their own colours.
7. **Honest numbers.** Estimates say "estimate". Nothing is annualised from under a year of data or compared with an empty period.

## 02 Colour

Most of the screen is canvas and paper. Nile is the one strong control colour. The app is light only: dark values exist for charts but are not wired in.

**Text**

| Token | Value | Use |
|---|---|---|
| Ink | `#0D2233` | Headings, amounts and primary text on every surface |
| Ink 2 | `#304A5C` | Secondary text, and the only secondary text on tints, lead and key-note cards |
| Muted | `#5C7483` | Labels, hints and codes, on white and paper only |
| Positive | `#097852` | Small money-in and gain amounts in lists; never the big lead number |

**Action and meaning**

| Token | Value | Use |
|---|---|---|
| Nile | `#0A2442` | Primary button, selected chip and segment, info-tip bubble |
| Meadow dark | `#0B8A5F` | Money-in marks, progress within plan, the focus ring |
| Meadow | `#14A874` | The plan line (dashed) and the key-note good edge |
| Soft rose | `#E68CA8` | Money-out and spending marks; never text |
| Strong rose | `#C93D72` | Over plan, negative balance, errors; never ordinary spending |
| Azure | `#0B6DD6` | Money you hold, links, transfers, trend lines |

**Surfaces**

| Token | Value | Use |
|---|---|---|
| Canvas | `#E3F6EC → #E6F4F1 → #E1EEFB`, 160° | Page background; only titles and cards sit on it |
| Paper (white card) | `#F8FCFA → #EFF8F4`, top to bottom, 1px `rgba(255,255,255,.94)` edge | Support cards, chart cards, the register |
| Surface | `#FFFFFF` | Entry cards, form fields, chips, popups, menus |
| Lead | `#E0F5E9 → #DCF1F0 52% → #D7ECF7`, 135° | Lead cards and the lead stat card |
| Wide | `#E0F5E9 0% → #E3F4EF 26% → #F7FCF9 52% → #FFFFFF 72%`, 100° | Full-width cards |
| Row field | `#F2F8F6` | Fields in a register add row |
| Tint growth | `#EAF8F0` | Growth badges, the active sidebar item, money-in avatars |
| Tint held | `#EAF3FD` | The register row being edited, info alerts, transfer avatars |
| Rose soft | `#FCEEF3` | Overage badges and error alerts, with ink text |
| Line · line control | `#DDE9E6` · `#7E96A0` | Hairlines between rows · field, button and chip borders |
| Track | `#E6EFEC` | The empty part of meters, rings and share bars |

- **Shadow:** cards use `0 14px 34px -24px rgba(10,36,66,.42)`; popups and menus use `0 24px 48px -16px rgba(10,36,66,.35)`.
- **Vivid Meadow** (`#0C9B63 → #0A9E96 → #0B6DD6`) is reserved for the logo bolt and the **Investment planner** button. It is never a card.

**Where each text colour may go**

| Text | Use on | Never on | Contrast |
|---|---|---|---|
| Ink | Every card, tint, chip and the canvas | Nile fills | 13:1 or more |
| Ink 2 | All of the above, including lead and key-note cards | Nile fills | 7.6:1 or more |
| Positive | Small amounts on white, tints, result bands | The big lead number, which stays ink | 4.5:1 or more |
| Muted | White and paper cards, hover | Lead cards, tints, the canvas | 4.0–4.4:1 there |
| Azure, strong rose | White cards; links (azure) on lead and key-note cards | Body text on tints | 3.9–4.4:1 |
| White | Nile and the vivid gradient | Anything light | 12:1 on Nile |

## 03 Type

The app uses two fonts. **Bricolage Grotesque** carries numbers and titles. **Manrope** is used for everything you read and press. Every amount uses tabular figures. Nothing is under 12px. Use the CSS variables (`--fs-*`, `--num-*`) and never a new size.

| Style | Font · px | Variable | Use |
|---|---|---|---|
| Lead amount | Bricolage 800 · 40 | `--num-lead` | The number on a lead card; one per section |
| Card figure | Bricolage 800 · 30 | `--num-card` | A support or wide card's headline figure |
| Tile figure | Bricolage 800 · 24 | `--num-tile` | Stat cards |
| Page title | Bricolage 700 · 28 | `--fs-page` | Top left of every page |
| Section title | Bricolage 700 · 20 | `--fs-section` | Left of the section line |
| Card title | Bricolage 700 · 17 | `--fs-card` | Every card header |
| Note title | Manrope 700 · 15 | `--fs-note` | Key-note titles, group titles |
| Body | Manrope 500 · 14 | `--fs-body` | Default text, row names |
| Secondary | Manrope 500 · 13 | `--fs-2` | The meaning line under a card title, row sub-lines, help |
| Label | Manrope 700 · 13 | `--fs-2` | Field labels, day headers, chips |
| Meta | Manrope 600 · 12 | `--fs-meta` | Codes, price dates, column headers, axis labels |

The fonts load from Google Fonts until they are bundled (see [Desktop build spec](desktop/BUILD_SPEC.md) §9.1). Offline, the app falls back to Plus Jakarta Sans, Inter and IBM Plex Sans Arabic.

**Numbers**

- Two decimals with thousands separators: `12,085.00`.
- A true minus with no space: `−5,000.00`, never `– 5,000.00` or `-455.00`.
- A `+` appears only on money in and gains. Balances and transfers carry no sign.
- EGP follows the number, small, and only beside a card's main number. Row amounts show just the number.
- Units read `1 piece`, `60 shares`, `12.500 g`.
- Numbers and dates never wrap.

**Dates and casing:** dates are `2026-09-30`, months `2026-09`, and ranges "2026-09-01 to 2026-09-30". Never "30 Sep 2026" or "31/1". Use sentence case everywhere, including the sidebar: "Cash and bank", not "CASH & BANK".

## 04 Cards

Every card has a **20px radius** and **24px padding**; stat cards use 16/18. A card never sits inside a card. Cards align to the top. Side-by-side support cards stretch to equal height; a lead card never does, because an empty gradient reads as missing content.

| Card | Where | Surface | Rules |
|---|---|---|---|
| **Lead** (gradient card) | Left, first in its section | Lead gradient, card shadow, no border | One per section: the section's answer and its parts. The number is always ink; other text is ink or ink 2; links are azure; an overage goes in a badge |
| **White** (support) card | Right of the lead, or full width alone | Paper wash, white 1px edge, card shadow | Explains or extends the lead. Six rows at most, then "N more" |
| **Wide** card | Full width | Wide gradient, green left fading to white by 72% | A page-wide card. It may split in two with a hairline divider (What it is made of · Investments if sold). Holdings, budget meters, reserves, analysis cards |
| **Entry** card | The drawer, popups and forms | White with a 1px line border, no shadow | Where you type. The only bordered card. One primary button |
| **Stat** card | A row of up to four under the page title | Alternating surfaces: lead green, white, mint (`#EAF8F0 → #F6FCF8`), white; 1px line in its own shade, card shadow | 164px tall. Label (15 Bricolage, ink) top left; a period chip top right (24px pill: green tint with ↑ when up, rose tint with ↓ when down, strong rose filled for "Over plan", grey otherwise); one big figure (30 Bricolage, ink; strong rose for a shortfall) at the bottom with its unit; one 13px line under it with its supporting figure in green or rose. One quiet visual in the band between label and figure, right side: a sparkline (2px at 75%, 10% fill, dot on the last point) for a figure with history, or an 8px meter for a share. The whole card is the link. Four in a row, two from 1,100px, one on phones |
| **Key note** | Up to three under the page title | A full tint of its tone, 135°, with a 1px tone border | See below |

**Inside a lead card, always in this order:**

1. The title and a one-line meaning.
2. One quiet action, top right, going to the page that owns the number.
3. The number below a hairline, with EGP after it. It is always ink; a gain shows its + sign, not a colour.
4. Two to four parts, as rows, meters or toggle rows.
5. One note, only if it asks you to act.

There are no white or tinted panels inside a lead card.

**Wide split cards (Overview, 2.5).** A wide card may hold one answer as two halves: the number and its toggle list on the left, the visual that explains it on the right, under a hairline divider. Net worth (list · trend over time), Free cash (list · waterfall), Net flow (list · column waterfall). No chart sits behind a toggle: if a chart is on the page, it is open.

**Overview stat cards** are exactly four: Change in net worth (Change in what you own when nothing is owed), Savings rate, Investing rate and Left in plan for the period's month. Safe to spend stays the lead of Cash planning.

**Inside a white card:** a list, bars, toggle groups, a breakdown with its result band, a chart, or "Needs you". A section with no single answer, such as every holding, is one wide card.

**Key notes** say only what the page doesn't already show: what is safe to spend, the top category and its change, categories over plan, the best class, the lowest point, the bills' share of income, the payoff date, months covered.

| Tone | Tint | Border | Icon tile and link |
|---|---|---|---|
| Good | `#D6F1E1 → #EDF9F2` | `#BDE5CD` | `#0B8A5F` tile · `#08744A` link |
| Info | `#D9E8FB → #EEF5FE` | `#C2D8F4` | `#0B6DD6` tile · `#0A5AB0` link |
| Needs you | `#F8DAE5 → #FDEFF4` | `#F0C0D1` | `#C93D72` tile · `#A02E5A` link |

**The number is the highlight.** Each key note reads top to bottom:

1. A 28px tone icon tile (white icon) and a short label, 15/500 ink 2: "Saved · 2026-09", "Safe to spend until 2026-11-01".
2. **One big figure**, 30px Bricolage 800, tabular: green (positive) for good, strong rose for needs you, ink for info.
3. One 13px ink 2 line of context: "13,600.00 of 42,000.00 that came in."
4. At most one 32px pill button in the tone colour, with white text ("See the plan"). The lead stat card uses a Nile pill.

A note with no figure ("Nothing needs you today") shows its sentence as the label. The full sentence stays as the card's screen-reader label. `keynotes.note()` takes `label` and `figure` for the card and `title` for the sentence.

The icon follows what the note says, not just its tone (`lightning/ui/keynotes.py` picks it from the title):

| Icon | Note is about |
|---|---|
| Trend up · trend down | A figure that rose or fell (grew, earned, more than, less than, lost) |
| Wallet | Safe to spend |
| Pie | A share ("took 48% of spending") |
| Alert triangle | Over plan, cash may run short |
| Chart line | The forecast's lowest point |
| Calendar | Loans, payoff dates, payments due |
| Shield | The emergency fund |
| People | Money held for others |
| Tag | Valued at cost, the cost of selling |
| Check · bulb | Defaults for good and info |

**Alerts** sit inside the card they concern: rose soft for a problem, tint held for information, with an ink title and an ink 2 line. There are no page-wide banners. Alerts, section titles and the period control are not cards.

**Special buttons**

- **Investment planner:** vivid Meadow, white text, and an icon.
- **Info tip:** a 20px "?" circle whose bubble is Nile. Only for a technical term such as XIRR.
- **Back:** a 36px pill with ‹ in the page header, on full pages opened from somewhere.
- **Full-page:** a 38px circle beside a popup's close button.

## 05 Sections and pages

A section groups the cards that share one date. It is a line on the canvas with one pair of cards under it.

1. **Title** on the left: a short noun phrase in sentence case ("Your position", "Cash flow").
2. **Date** on the right: "As of 2026-09-30" for what you have. For what changed, the range moves under the title.
3. **One hairline** 12px below the text and 16px above the cards.
4. **One pair:** lead left, white right, 6 + 6 columns, 16px apart. Or one wide card.
5. **48px of canvas** before the next section, with no divider or band.

- A new date starts a new section, and "As of" sections come before period sections.
- The period control appears once per page, in the page header. "As of" stays only where the period can move the date (the Overview).
- A page has two to four sections, answers one question, and never repeats a number from another section. To change something, the primary button opens the drawer or popup; there are no forms at the bottom of a page.
- Tabs switch views of one subject and never jump to another page. Sidebar pages are not repeated as sub-tabs.
- The Overview is the quick glance, and the reports under it (Budget, Expense analysis, Cash planning, Investments) hold the depth.
- On phones the line wraps (title first), the pair stacks with the lead on top, and tabs scroll on one line.

## 06 Controls

- **Pills are for pressing and 16px corners are for typing.** Selected always looks the same: a Nile fill.
- **Buttons:**
  - *Primary* (Nile), once per page, for the thing the page is for.
  - *Secondary* (white, line-control border) for the second action and every "Review".
  - *Quiet* (azure text) for card-header actions and "Show more"; it replaces every text link with an arrow.
  - *Danger* (strong rose text) only for deleting or deactivating.
- A page header holds at most Primary + Secondary + ⋯. Labels start with a verb, run one to three words and carry no arrows.
- **Chips** (36px) filter or fill in values. They are not actions.
- **Segments** offer two to four choices of one thing (Buy · Sell · Dividend · Already own).
- **Period control:** one component (All time · YTD · Monthly · Custom) with ‹ month › beside it. It replaces month and year dropdowns.
- **Month picker:** every month box opens it. It has a year row with ‹ ›, then twelve months, with future months disabled. Changing the year keeps it open. Months are never typed.
- **Toggle rows** are 48px buttons: name and total on the left, chevron on the right. Their items are indented, quieter, and add up to the row's total; a takeaway shows − (Reserves −5,000.00). They start closed, except the first group on the page that owns the number. Leave out items at 0.00, and show six at most, then "N more". Enter or Space toggles a row, and it reports open or closed to screen readers.
- **There are no explanation toggles.** A figure's name explains itself.

## 07 Fields

There are three kinds. Choosing from your own data is always type-and-pick, never a dropdown. Browser history suggestions (`autocomplete`) are off on every field; the only suggestions are the app's own.

**Form fields (48px)** live on white: entry cards, the drawer and popups.

- The label (13/700) goes above the field, and help or an error goes under it.
- The field has a `#7E96A0` border, a 16px radius and 15px text.
- **Focus:** a green ring (`0 0 0 2px white, 0 0 0 5px rgba(11,138,95,.28)`, border Meadow dark).
- **Error:** a strong rose border, with a message that says what to type instead ("Use yyyy-mm-dd, like 2027-01-31").

**The Amount field (72px)** is first in the drawer. It uses 30px Bricolage and accepts −, commas and Arabic-Indic digits.

**Pick field:**

- Type, then pick from a menu grouped as your accounts (a transfer), used before, categories, and create.
- It replaces every dropdown over five options and every "Search X" + "Choose X" pair.
- The date field adds Today and Yesterday chips and a calendar button.

**Soft fields in a register row.** The register is edited in place, so its fields must not jump or shout.

- **Fields are a soft shade of their row, never strong white.** The field you are in turns a deeper shade with a green edge (Meadow dark, plus a 3px ring at 12%), the same green as forms.
- **Add row:** fields 30px tall, the height of a line entry, so nothing jumps. They are filled `#F2F8F6` (focus `#E8F3EE`) with a transparent border that turns line on hover, 8px corners and 13px text. Placeholders name the column, with no labels. Add is a 30px primary pill.
- **Row being edited:** the row takes the held tint `#EAF3FD`. Its fields are a lighter shade of it (`#F3F8FE`, border `#D9E6F6`), and the field you are in a deeper one (`#E3EEFB`). Only **Save** shows in the row.
- **Row actions live in the right-click menu**, never in a bar under the row:
  - on the row being edited: Save, Details and history, Cancel edit, Delete;
  - on any other row: Edit, Details and history, Delete (of the selection).

  Enter saves and Esc cancels. The row's tooltip says so, along with its ref. The menu is a white popup with a 12px radius and 36px items, with Delete in strong rose below a hairline.
- **Inline number fields**, such as Required % on Target allocation, are 34px and right-aligned. They save on Enter or blur without reloading the page.

Fields never sit in read-only list rows. Arabic text gets `dir="auto"`. Group long forms by question and fold rare fields.

## 08 Lists, tables and status

- Two-line rows replace wide tables. Who or what goes on the left with details under it; the amount and one figure under it go on the right. A table has five columns at most.
- Registers group rows under day headers instead of repeating the date. Clicking a row edits it in place, or opens the drawer for investment rows.
- Money in is green with +; money out is ink with −; transfers carry no sign.
- Avatars are 36px with a 12px radius: rose soft for out, tint growth for in, tint held for transfer.
- Status is a word with a dot (green, gold, strong rose), or one sentence in an alert.
- Badges are pills: "925.00 over" on rose soft, "+4.2%" on tint growth.
- There are no empty tables with headers. An empty state says what's missing and offers the next useful action.
- Missing valuations, import errors and required decisions stay visible. Details reduce clutter without hiding problems.

## 09 Charts

Charts are hand-drawn SVG and CSS with no chart library. In the app, `lightning/ui/charts.py` computes the geometry and `templates/partials/charts.html` renders it. Pick the form from the job the data does: over time, rank, parts of a whole, how a number is built, progress, or spread. Sometimes the answer is a stat card, not a chart.

**Colour roles**

| Role | Colour |
|---|---|
| Money in | Meadow dark `#0B8A5F` |
| Money out | Soft rose `#E68CA8` |
| Over plan | Strong rose `#C93D72` |
| Money you hold, trends | Azure `#0B6DD6` |
| Plan | Meadow `#14A874`, dashed 6/5 |
| Reference (usual, last year) | Grey-green `#C9D6D2` |

- Asset classes use their colours from §15.
- Sequential data uses one hue from light to dark, and diverging data uses two hues with a neutral centre.
- Colour follows the entity, never its rank.

**Marks**

- Lines are 2px. Dots are 10px with a 2px white ring.
- Bars are 12px, with a rounded data end (4px) anchored at zero.
- Stacked parts have a 2px surface seam.
- The grid is recessive hairlines, with one y-axis.
- Bars, columns and areas start at zero.

**Labels:** put them on the marks when they fit; a legend is used for two or more series. Label the last value only on trends. Months on axes read `2026-09`. Every dot and bar has a tooltip, and every trend has a closed "Show the numbers" table.

**Honesty**

- Under two points, a trend says "Not enough history yet — check back next month."
- A trend starts at the first month with data, and missing data stays missing.
- Negative or refund values never produce negative sizes or silently disappear.
- A zero step in a waterfall is never "up".

**Catalogue.** **In the app** means built and used. **Ready to use** means specified here: build it in `charts.py` when a page needs it. **Avoid** means reference only.

| Group | Chart | Status | Use for | Where |
|---|---|---|---|---|
| Over time | Trend line | In the app | A value at comparable dates, with a dashed plan; a dot over plan turns strong rose | Expense analysis, Budget |
| | Area trend | In the app | One total that builds up (net worth); 12% fill | Overview · Net worth trend |
| | Stacked area | Ready | A total made of parts over time; four layers at most | Investments · allocation history |
| | Step line | Ready | A balance that jumps on each transaction | Account page |
| | Forecast with range | Ready | Solid past, dashed forecast, light azure range band, a Today line, the lowest point marked | Cash planning · Plan |
| | Pace (burn-up) | Ready | Spending so far against an even pace to plan | Budget · this month |
| | Columns: in and out | Ready | In above zero, out below it, net as a Nile mark on the same axis | Overview · Cash flow by month (stashed, see 16) |
| | Drawdown | Ready | Fall from the previous high; needs a year of month-ends | Investments · risk |
| | Candlestick | Avoid | Lightning keeps one price per month-end; use a trend line | — |
| | Calendar heatmap | Ready | Spending by day, one rose ramp in five steps | Expense analysis · by day |
| | Small multiples | In the app | The same trend per category, same scale, no axes | Expense analysis · usual month |
| | Sparkline | In the app | A trend inside a card; no axes, a dot on the last point | Expense analysis rows, white cards |
| Compare and rank | Horizontal bars | In the app | Ranking; largest first, six then "N more", each opens its transactions | Expense analysis |
| | Grouped bars (L1 · L2) | In the app | Categories under their parent: a bold header row with its total, the children indented | Expense analysis |
| | Clustered columns | Ready | Two values per category (this month against usual) | Expense analysis |
| | Dumbbell | Ready | Current % (azure dot) against required % (hollow Nile dot) | Target allocation |
| | Diverging bars | Ready | Value to adjust: azure put in, soft rose take out, a centre line | Target allocation |
| | Lollipop | Ready | Ranked values where the number matters (largest payments) | Expense analysis |
| | Slope chart | Ready | Shares at two dates, labels at both ends | Investments · this year |
| | Bullet | Ready | Actual against plan, with a light band to the plan and a Nile tick | Budget · categories |
| Parts of a whole | Donut | In the app | Allocation; six slices, total in the middle, legend with % and value and a Total row | Overview, Investments |
| | Share bar | In the app | Two to four parts in one line | Budget, Overview |
| | 100% stacked columns | Ready | Shares over time when the total doesn't matter | Investments |
| | Treemap | Ready | Many parts at once; one hue dark to light | Expense analysis · all categories |
| | Waffle | Ready | One share to feel (savings rate), 100 squares | Overview · Savings rate |
| | Pie | Avoid | Use the donut | — |
| How a number is built | Waterfall | In the app | Start in azure, takeaways soft rose, additions green, the result Meadow dark and bold | Overview · Free cash › How it is built |
| | Column waterfall | In the app | Money in green from zero, each kind of money out soft rose floating at the running total, net flow azure from zero (strong rose when short); dashed links, values on the columns, one zero line | Overview · Cash flow › From money in to net flow |
| | Breakdown list | In the app | The waterfall as rows, each result on a soft band | Overview, Investments |
| | Sankey | In the app | Sources (green) into one Money in hub, out to spending (soft rose) and Kept (azure); "From what you had" in strong rose when money out is larger. Never source-to-use flows: the ledger does not say which income paid which bill. Three sources, five uses, the rest in Other; flows at 22%; labels pushed apart; a table under it | Overview · Cash flow › Where money in went |
| Progress | Meter | In the app | Spent of plan or saved of target; the "over" badge or "left" on the right | Budget, Cash planning |
| | Progress ring | Ready | One goal with its value in the middle | Cash planning · Emergency fund |
| | Stat card | In the app | A number that needs no chart, with a sparkline or meter | Overview · four stat cards; Expense analysis |
| Spread | Histogram | Ready | Payments by size, touching columns | Expense analysis |
| | Usual range | Ready | 12-month range pill, middle-month tick, this month as a dot | Expense analysis |
| | Scatter | Ready | Return against how much it moves, labelled dots | Investments · risk and return |
| | Heatmap table | Ready | Category × month, shaded against each row's average, values in cells | Expense analysis |
| Loans and schedules | Principal and interest | Ready | Stacked columns per year: azure principal, light azure interest | Cash planning · Loans |
| | Loan balance | Ready | Line down to zero with the payoff date | Cash planning · Loans |
| | Timeline | Ready | Bills and income over the next 30 days, labels above and below | Cash planning · Next 30 days |
| Numbers | Show the numbers | In the app | Every chart's data as a table, closed by default | Every trend |

**Never:**

- two y-axes;
- 3D, shadows or gradients inside marks;
- gauges and speedometers;
- radar charts;
- pies, and donuts over six slices;
- sunburst and funnel charts;
- rainbow or cycled palettes;
- a number on every point;
- a chart for empty or one-month data.

## 10 Words

Write in a clear, encouraging, concrete, honest and local voice. Speak to "you". The Glossary defines each figure's one name; the table below is how they read on screen.

| Say | Instead of |
|---|---|
| Free cash | Available cash · Estimated available value |
| Net gain or loss | Result · Period result |
| Personal over plan | Budget exceeded: Personal |
| No earlier spending to compare | 44,420.00 more · Previously 0.00 EGP |
| Investments if sold (estimate) | Estimated liquid investments after liquidation factors |
| Held for others | Money from others · Cash held for others |
| Your position · Cash flow | Your Position · Cash Flow Analysis |
| 6,350.00 is in THNDR. Move it before you spend it. | Includes 6,350.00 EGP in brokerage cash; transfer it… |
| Review 3 items | An unexplained metric |

Red means a shortfall or overspend, not simply a negative number.

## 11 Spacing, shape and layout

- **Spacing** is on a 4px base:

  | px | Use |
  |---|---|
  | 4 | tight |
  | 8 | label gap |
  | 12 | bar and note gap |
  | 16 | card gap |
  | 20 | block gap |
  | 24 | card padding |
  | 32 | page top |
  | 48 | between sections |

- **Radii:**

  | Radius | Use |
  |---|---|
  | 8 | Register row fields |
  | 12 | Rows, menus, avatars |
  | 16 | Form fields |
  | 20 | Cards, key notes, stat cards |
  | Pill | Anything you press |

- **Heights:**

  | Height | Use |
  |---|---|
  | 72 | Amount field |
  | 48 | Page buttons, form fields, segments, toggle rows, period control |
  | 36 | Card buttons, chips, card actions |
  | 30 | Register row fields and buttons, the holdings horizon picker |

- **Grid:** content up to 1,120px beside a 272px sidebar, 12 columns with 16px gutters.
- **Phones:** one column with the lead first, 16px sides, and a full-width drawer. There is no sideways page scroll at 390px; a wide table scrolls inside its card.
- **Sidebar:**
  - each destination has its own icon;
  - the accounts list has a clear heading, subdued group labels, right-aligned balances and one selected marker;
  - Add account and Manage accounts sit in a stable footer;
  - Settings holds Counterparties, Categories, Target allocation and Data checks under one subsection navigation.

## 12 Accessibility

- Text contrast is 4.5:1 on its ground; borders, icons and the focus ring are 3:1.
- Colour is never the only signal: amounts carry signs, states carry words, and chart series carry labels or a legend.
- Targets are 44px or more. Row fields sit in rows of 36px or more.
- Esc closes popups and menus, and disclosures work from the keyboard.
- Every chart has an aria-label and a table view. Reduced motion turns transitions off.

## 13 Icons and logo

- Icons are Lucide at 1.75 stroke and 20px, in the current colour, with no emoji or icon font.
- Pages use house, pie chart, chart line, wallet and settings.
- Rows use arrows for out, in and transfer, a gem for gold and a user for held for others.
- Key notes use check (good), bulb (info) and alert circle (needs you).
- The bolt (`#45A9E8 → #1FB5A8 → #34BF8C`) sits beside the wordmark and is never recoloured by hand.

## 14 Before a screen ships, it has none of these

- All-caps labels, including in the sidebar.
- A vivid gradient card, or two leads in one section.
- More than five table columns, or an empty table with headers.
- Strong rose or green text for everyday amounts, or grey spending bars.
- The lead on the right, stretched to its neighbour's height, or with white panels inside it.
- Text links with arrows ("Review →"), or dropdowns for your own data.
- Strong white or labelled fields in a register row, a button bar under a row, or a fourth control height.
- Grey, blue or rose body text on the lead card; ▼, ^ or − as open/close markers.
- Dates like "30 Sep 2026" or "31/1"; "– 5,000.00" or "-455.00" instead of −5,000.00.
- A period control above figures it doesn't change, or the same number under two names.
- A chart from the Never list, or a chart for data under two points.

## 15 Asset class colours

There is one hue family per kind of asset, with a lighter shade for the fund version. The tokens are `--class-*` in `lightning/ui/static/style.css`.

| Family | Class | Colour |
|---|---|---|
| Cash | Cash (bank, wallet, brokerage) | `#0B6DD6` |
| Income | Deposits / CDs | `#00907F` |
| Income | Money market fund | `#6CC795` |
| Income | Fixed income fund | `#2E9CC8` |
| Gold | Gold | `#9A6708` |
| Gold | Gold fund | `#D6A23A` |
| Growth | Stocks | `#08744A` |
| Growth | Equity fund | `#3EB072` |
| Other | Other investments | `#687F8B` |
| Other | Other fund | `#A2B4BC` |

The donut order (the rows above, top to bottom) passes the palette validator for neighbouring slices. The greys are neutral on purpose. Some shades are under 3:1 contrast against white, so every chart keeps visible labels.

## Open visual gaps

- On a phone, the transactions register scrolls sideways inside its card.
- These charts are drawn in the guideline but not yet built in the app, although the pages would use them:
  - Cash planning: the forecast chart with its lowest point, and the 30-day timeline;
  - Budget: the pace chart and bullets;
  - Target allocation: the dumbbell and diverging bars.
- Transactions, account pages and Settings have not had the key-notes and charts pass.
- Dark mode is not wired in.

## 16 Visuals: active and stashed

Every visual the app draws, and the ones built but set aside. Update this list in the same change that adds, moves or removes a chart. Desktop (Windows) uses WebView2, the same Chromium engine as the browser, so every active visual renders the same there.

**Active: on a screen now**

| Where | Visual | Macro |
|---|---|---|
| Overview · stat cards | Sparkline (Change in net worth, Savings rate) · meter (Investing rate, Left in plan) | `stat_tiles` |
| Overview · Net worth | Area trend beside its breakdown list | `trend` |
| Overview · Free cash | Waterfall (How it is built) beside its list | `waterfall` |
| Overview · What it is made of | Donut | `donut` |
| Overview · Cash flow | Column waterfall (From money in to net flow) beside its list | `column_waterfall` |
| Overview · Where money in went | Sankey | `sankey` |
| Overview · Investments | Donut (What you hold) · gain-or-loss bars by asset class · movers list | `donut` |
| Expense analysis | Stat card · trend with plan · grouped bars · bars (Who you paid, Paid from) · sparkline rows | `trend`, `bars`, `sparkline` |
| Budget; Cash planning · reserves | Meter | `meter` |
| Cash planning · Plan | Forecast trend | `trend` |
| Investments | Area trend (portfolio value) · donut | `trend`, `donut` |
| Cash planning · Recurring | Bars | `bars` |

**Stashed: built, not on any screen**

| Visual | Form | Why, and how to bring it back |
|---|---|---|
| Month by month (money in and out per month) | Two-line trend under a toggle | Removed from the Overview in 2.5: no chart hides behind a toggle. `visuals.flow_trend` is kept; bring it back as Columns: in and out, always open |
| Where it went (Overview) | Grouped bars | Replaced by the Sankey in 2.5. `visuals.spending_bars` is kept; Expense analysis still uses grouped bars |
| Money in and money out comparison | Two meters | Replaced by the Cash flow list and column waterfall in 2.5 |
| Savings ring | Progress ring | Replaced by the Savings rate stat card in 2.5 |
| Safe to spend key note (Overview) | Key note | Moved off the Overview in 2.5; it stays the lead of Cash planning |
| Share bar | `charts.share` · `share_bar` | Built, used by no screen |

## 17 Versions

| Version | Date | What changed |
|---|---|---|
| 2.5 · Willow | 2026-10-01 | Overview as wide split cards (numbers and toggle list left, visual right); the column waterfall for cash flow; the Sankey replaces Where it went; Investments gets its own section; no chart behind a toggle; Month by month stashed. Stat cards redesigned: four in a row on alternating green and white, a period chip, one big figure and a sparkline or meter. New figures Change in net worth and Investing rate. New section 16, Visuals: active and stashed |
| 2.4 · Meadowlark | 2026-10-01 | Key notes put the number first: label, one big figure in the tone colour, one line, one pill button |
| 2.3 · Glade | 2026-10-01 | Key notes stand out: a full tone tint, a tone border, a solid icon tile, and icons chosen by meaning. Register fields are soft shades of their row, never white, with the green focus edge everywhere. Row actions move to the right-click menu |
| 2.2 · Grove | 2026-09-30 | **One unified guideline** with a visual page (`APPLICATION_BRAND_GUIDE.html`), numbered the same. **Changes:**<ul><li>soft register fields and the 30px row height;</li><li>stat cards;</li><li>key notes with tone tints and an edge;</li><li>the wide gradient card;</li><li>the 20px card radius;</li><li>one type scale;</li><li>the waterfall in azure, soft rose and green (replacing hatched grey);</li><li>the vivid gradient allowed on the Investment planner button;</li><li>a full chart catalogue (In the app, Ready to use, Avoid).</li></ul> |
| 2.1 · Bloom | 2026-09-29 | Soft rose for money out and spending bars, replacing grey. The lead number is always ink. Strong rose only for over plan, negative balances and errors |
| 2.0 · Clearing | 2026-09-29 | Lead left on the soft gradient, white support right; the vivid gradient leaves cards; toggle lists replace panels inside cards; the Sections part |
| 1.1 | 2026-09-29 | Meadow light by default with a dark preview; a faint wash on white cards; a soft band under breakdown results |
| 1.0 | 2026-09-29 | First app guideline |

Additions are numbered 2.5, 2.6 and so on. A change to the card rules is 3.0. Each version gets a name.
