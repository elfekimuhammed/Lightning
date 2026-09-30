# App brand guideline · 2.1 · Bloom

**Last updated 2026-09-30.** This file sets how every screen looks, reads and adds up: colour, type, cards, sections, controls, charts and words. It is built on the Meadow brand guidelines. The product story is in [Project Overview](PROJECT_OVERVIEW.md), code rules in [Architecture](ARCHITECTURE.md) and terms in the [Glossary](GLOSSARY.md).

The guideline sets visual properties only. Its sample copy, values and page groupings are illustrative and do not change product requirements or workflows. Where the app differs from the guideline on purpose, the difference is noted under **In the app**. The user prefers a quiet, number-led look, and that preference outranks the brand's vivid gradients.

## Six rules behind every screen

1. **Lead on the left.** The most important card of each section sits on the left, on the soft Meadow gradient.
2. **Support on the right.** A white card beside it explains or extends the lead, with a list, bars or a breakdown.
3. **Position, then activity.** What you have on a date comes before what changed in a period. The period control sits only above what it changes.
4. **One name per number.** A figure has one name and one home page. Other pages show it once and link there ("Free cash", never also "Available cash").
5. **Same control, same size.** Everything you press or type into is 48px tall. Chips and card actions are 36px. Nothing else.
6. **Honest numbers.** Estimates say "estimate". Nothing is annualised from under a year or compared with an empty period.

## Colour

Most of the screen is canvas and paper. Nile is the one strong control colour. Green means money coming in and growing, soft rose means money going out, azure means money you hold, and strong rose means something needs attention. Values are given as light · dark.

**Text**

| Token | Value | Use |
|---|---|---|
| Ink | `#0D2233` · `#E8F3EF` | Headings, amounts, primary text on every surface |
| Ink 2 | `#304A5C` · `#C4D6D2` | Secondary text; the only secondary text on tints and the canvas |
| Muted | `#5C7483` · `#98AFB5` | Labels, hints and codes, on white and paper only |
| Positive | `#097852` · `#5FD6A7` | Small money-in and gain amounts in lists; never the big lead number |

**Action and meaning**

| Token | Value | Use |
|---|---|---|
| Nile | `#0A2442` · `#DDF4E8` | Primary button, selected chip and segment, step numbers |
| Meadow dark | `#0B8A5F` · `#34C88F` | Money-in bars, progress within plan, the focus ring |
| Soft rose | `#E68CA8` · `#C9738F` | Money-out and spending bars; never text |
| Strong rose | `#C93D72` · `#F58FB4` | Over plan, negative balance, errors; never ordinary spending |
| Azure | `#0B6DD6` · `#7DB8F7` | Money you hold, links, transfers, trend lines |
| Gold | `#B8841E` · `#E8B456` | Gold in charts, always |
| Teal | `#0A9E96` · `#4FC9C1` | Deposits and fixed income in charts |

**Surfaces**

| Token | Value | Use |
|---|---|---|
| Canvas | `#E3F6EC → #E1EEFB` | Page background; only titles and cards sit on it |
| Paper | `#F8FCFA → #EFF8F4` · `#10232A` | Support cards, as a faint top-to-bottom wash |
| Surface | `#FFFFFF` · `#152B33` | Entry cards, drawer, fields, chips |
| Line · line control | `#DDE9E6` · `#7E96A0` | Hairlines between rows; field, button and chip borders |
| Tint growth | `#EAF8F0` · `#12322C` | Money-in avatars, growth badges, left end of the result band |
| Tint held | `#EAF3FD` · `#132A40` | Transfer avatars, info alerts, right end of the result band |
| Lead | `#E0F5E9 → #D7ECF7` | The lead card, always on the left of a section |
| Rose soft | `#FCEEF3` · `#3A1A28` | Error alerts and overage badges, with ink text |

The vivid Meadow gradient (`#0C9B63 → #0A9E96 → #0B6DD6`) is reserved for the logo and a small accent bar. It is never a card.

**Where each text colour may go**

| Text | Use on | Never on | Contrast |
|---|---|---|---|
| Ink | Every card, tint, chip and the canvas | Nile fills | 13:1 or more |
| Ink 2 | All of the above, including the lead card | Nile fills | 7.6:1 or more |
| Positive | Small amounts on support and entry cards, tints, the result band | The big lead number, which stays ink | 4.5:1 or more |
| Muted | Support and entry cards, hover | The lead card, tints, the result band, the canvas | 4.0–4.4:1 there |
| Azure, rose | Support and entry cards | The lead card and tints (use a badge or an icon there) | 3.9–4.4:1 there |
| White | Nile buttons | Anything light | 12:1 on Nile |

**In the app:** light only. The dark values are chosen and validated for charts but not wired in yet.

## Type

The app uses two fonts. **Bricolage Grotesque 800** carries the brand in big numbers and titles. **Manrope** 500 and 700 is used for everything you read and press. Every amount uses tabular figures so columns line up. Refs use the system mono at 12px, in the drawer only. Until the brand fonts are bundled, the app falls back to its offline fonts (Plus Jakarta Sans, Inter, IBM Plex Sans Arabic).

| Style | Guideline | In the app (`style.css`, "Crisp pass") | Use |
|---|---|---|---|
| Lead amount | Bricolage 48/52 (40 on phones) | 40 | The number on a lead card; one per section |
| Card figure | Bricolage 28/32 | 30 card · 24 tile | A support card's headline figure, the drawer amount |
| Page title | Bricolage 32/38 | 28 | Top left of every page |
| Section title | Bricolage 24/30 | 20 | Left of the section line; its date on the right |
| Card title | Bricolage 20/26 | 17 (15 for a group or note title) | Every card header |
| Body | Manrope 500 15/24 | 14 | Default text and field values |
| Meaning line, small | Manrope 500 13/20 | 13 | Under a card title; row sub-lines, help text |
| Label | Manrope 700 13/18 | 13 | Field labels, day headers, chips |
| Caption | Manrope 600 12/16 | 12 | Codes after names, price dates; nothing smaller |

The app's scale is a tighter version of the guideline, adopted so a page uses 5–10 sizes and none under 12px. Use the CSS variables (`--fs-*`, `--num-*`) and never a new size.

**Numbers:** two decimals with thousands separators (`12,085.00`). Use a true minus with no space (`−5,000.00`), never `– 5,000.00` or `-455.00`. A `+` appears only for money in and gains; balances carry no sign. EGP follows the number, small, and only beside a card's main number; row amounts show just the number. Units read `1 piece`, `60 shares`, `12.500 g`. Numbers and dates never wrap.

**Dates and casing:** dates are `2026-09-30`, months `2026-09`, and ranges "2026-09-01 to 2026-09-30". Never "30 Sep 2026" or "31/1". Use sentence case everywhere, including the sidebar: "Cash and bank", not "CASH & BANK".

## Cards

| Card | Where | Surface | Rules |
|---|---|---|---|
| Lead | Left, first in its section | Soft lead gradient, soft shadow | One per section: the section's answer and its parts. The number is always ink; other text ink or ink 2; an overage goes in a badge |
| Support | Right of the lead, or full width alone | White paper with a faint wash, soft shadow | Explains or extends the lead. Six rows at most, then "See all" |
| Entry | The drawer and forms | White with a 1px border | Where you type. The only bordered card. One primary button |

**Inside a lead card, always in this order:**

1. The title and a one-line meaning.
2. One quiet action, top right, going to the page that owns the number.
3. The number below a hairline, with EGP after it. It is always ink; a gain shows its + sign, not a colour.
4. Two to four parts, as rows, meters or toggle rows.
5. One note, only if it asks you to act.

**Inside a support card:** a list, bars, toggle groups, a breakdown with its result band, or "Needs you", under the same header as the lead. A section with no single answer, such as every holding, is one support card at full width.

- Cards align to the top. The lead never stretches to its neighbour's height, because an empty gradient reads as missing content. **In the app:** side-by-side support cards do stretch to equal height.
- Every card has a 22px radius and 24px padding. A card never sits inside a card, and there are no white or tinted panels inside a lead card.
- Alerts, section titles and the period control are not cards.

**Toggle rows** open on a tap. Each is a 48px button with the chevron on the right, then the name and total (**in the app:** title left, chevron right, one style for every expander). Items are indented, quieter and in full-ink amounts, and they add up to the row's total. A takeaway shows − on the row (Reserves −5,000.00). Toggle rows start closed, except the first group on the page that owns the number. Leave out items at 0.00; show six at most, then "N more". Enter or Space opens and closes the row, and it reports open or closed to screen readers. The quiet "How is this worked out?" and "Show the numbers" toggles share this look, and a figure's formula appears only inside "How is this worked out?".

**Key notes (app):** up to three cards under the page title. Each has a tone (good, info, needs you), an icon, one sentence with its number and at most one link. A note says only what the page doesn't already show: what needs you, the cost of selling, the top category and its change, categories over plan, the best class, the lowest point, the bills' share of income, the payoff date, months covered.

## Sections and pages

A section groups the cards that share one date. It is a line on the canvas with one pair of cards under it.

1. **Title** on the left: a short noun phrase in sentence case ("Your position", "Cash flow").
2. **Date** on the right: "As of 2026-09-30" for what you have. For what changed, the range moves under the title and the period control takes the right.
3. **One hairline** 12px below the text and 16px above the cards.
4. **One pair:** lead left, support right, 6 + 6 columns, 16px apart. Or one support card at full width.
5. **48px of canvas** before the next section, with no divider or band.

- A new date starts a new section. "As of" sections come before period sections.
- The period control appears once per page, on the first period section. In the app the period lives in the page header, and "As of" stays only where the period can move the date (Overview).
- A page has two to four sections. A section is never a card, never has tabs, and never repeats a number from another section.
- Every page answers one question. The flow is the section line, then lead and support, then position before activity. To change something, the primary button opens the drawer; there are no forms at the bottom of a page.
- Tabs switch views of one subject and never jump to another page. Sidebar pages are not repeated as sub-tabs.
- On phones the line wraps (title first) and the pair stacks with the lead on top. Tabs scroll on one line.

The guideline's page merge (Overview + Birdview, Budget + Expense analysis, Reserves into Cash) is not adopted. The app keeps the screens listed in the Project Overview.

## Controls

- **Pills** are for pressing and **16px corners** are for typing. There are two heights only: 48px, and 36px inside cards and for chips. Selected always looks the same: a Nile fill.
- **Buttons:** *Primary* (Nile), once per page, for the thing the page is for. *Secondary* for the second action and every "Review". *Quiet* for card-header actions and "Show more"; it replaces every text link with an arrow. *Danger* only for cancelling or deactivating.
- A page header holds at most Primary + Secondary + ⋯, and extra actions go into "More actions". Labels start with a verb, run one to three words and carry no arrows.
- In a bar, field, picker, segments and button all line up at 48px.
- **Chips** (36px) filter or fill in values. They are not actions: "Track", "One-off" and "Reset carryover" are choices in the drawer instead.
- **Segments** offer two to four choices of one thing (Buy · Sell · Dividend · Already own).
- The **period control** is one component (Month · YTD · All time · Custom, with a month stepper) that replaces month and year dropdowns.

## Fields

- The label goes above, the 48px field below it, and help or an error under that. Fields live on white (entry cards and the drawer), never inside list rows.
- The **Amount** field is the one 72px control, first in the drawer. It accepts −, commas and Arabic-Indic digits.
- Choosing from your own data is always type-and-pick, never a dropdown. A pick field replaces every dropdown over five options and every "Search X" + "Choose X" pair. The menu order is your accounts (a transfer), used before, categories, then create.
- Group long forms by question and fold rare fields; the reserve form goes from nine visible fields to four.
- Errors say what to type instead ("Use yyyy-mm-dd, like 2027-01-31"). Focus is always the green ring. Arabic text gets `dir="auto"`.

## Charts

Charts are hand-drawn SVG and CSS with no chart library. In the app: `lightning/ui/charts.py` computes the geometry and `templates/partials/charts.html` renders it.

| Chart | Use | Rules |
|---|---|---|
| Trend | Values over comparable dates | One series in azure; a plan as a dashed green line; a point over plan turns rose; a "Show the numbers" table |
| Bars | Ranking categories | Horizontal, soft rose for spending, largest first, value at the end, each opens its transactions |
| Meter | Spent of plan, progress to a target | "925.00 over · 2,300.00 of 1,375.00"; over plan first |
| Waterfall | How a number is built | Additions in blue, takeaways hatched grey (not red), totals in Nile, the result in green |
| Breakdown list | The waterfall as rows | Each result on a soft band |
| Donut | Allocation | Six slices at most, in class colours |
| Share bar | Two to four parts of one whole | More parts than that is a bar chart |
| Sparkline | A trend inside a support card | No axes or labels; two points or more |

- Colour follows meaning: money in green, money out soft rose, over plan strong rose. By class: cash azure, deposits teal, equity green, gold gold, other grey.
- Put labels on the marks; use a legend only when labels don't fit. Months on axes read `2026-09`.
- Bars and waterfalls start at zero. No 3D, no gradients inside charts, no animation beyond the first draw.
- With under two months of history a trend says "Not enough history yet — check back next month." Don't draw a chart for an empty state, and don't show a decorative 100% bar as insight. A trend starts at the first month with data, and missing data stays missing.
- Negative or refund values never produce negative dimensions or silently disappear.

## Lists and status

- Two-line rows replace wide tables. Who or what goes on the left with details under it; the amount and one figure under it go on the right. A table has five columns at most.
- Registers group rows under day headers instead of repeating the date.
- Money in is green with +; money out is ink with −. Clicking a row opens the drawer; nothing is edited inside rows.
- Status is a word with a dot, or one sentence in an alert. Alerts sit inside the card they concern. There are no page-wide banners, and no empty tables with headers; an empty state offers the next useful action.
- Missing valuations, import errors and required decisions stay visible. Details reduce clutter without hiding problems.

## Words

Write in a clear, encouraging, concrete, honest and local voice. Speak to "you". The Glossary defines each figure's name; the table below is how they read on screen.

| Say | Instead of |
|---|---|
| Free cash | Available cash · Estimated available value |
| Personal over plan | Budget exceeded: Personal |
| No earlier spending to compare | 44,420.00 more · Previously 0.00 EGP |
| No plan yet | Consider tracking · Background |
| If you sold today (estimate) | Estimated liquid investments after liquidation factors |
| Held for others | Money from others · Cash held for others |
| Your position · Cash flow | Your Position · Cash Flow Analysis |
| 6,350.00 is in THNDR. Move it before you spend it. | Includes 6,350.00 EGP in brokerage cash; transfer it… |
| Review 3 items | An unexplained metric |

Red means a shortfall or overspend, not simply a negative number.

## Spacing, shape and layout

- **Spacing** is on a 4px base: 4 tight · 8 label gap · 12 bar gap · 16 card gap · 20 field gap · 24 card padding · 32 page top · 48 between sections.
- **Radii:** 12 for rows and menus · 16 for fields · 22 for cards · pill for anything you press.
- **Grid:** content up to 1,120px beside a 272px sidebar, 12 columns with 16px gutters.
- **Phones:** one column with the lead first, 16px sides, a 40px lead number and a full-width drawer. There is no sideways page scroll at 390px.

**Sidebar:** each destination has its own semantic icon, and there is no Management toggle. The Accounts list has a clear heading, subdued group labels, right-aligned balances and one selected marker. Add account and Manage accounts sit in a stable footer. Settings holds Counterparties, Categories and Data checks under one subsection navigation.

## Accessibility

- Text contrast is 4.5:1 on its ground; borders, icons and the focus ring are 3:1.
- Colour is never the only signal: amounts carry signs and states carry words.
- Targets are 44px or more. Esc closes the drawer and menus. Disclosures work from the keyboard. Reduced motion turns transitions off.

## Icons and logo

Icons are Lucide at 1.75 stroke, 20px, in the current colour, with no emoji or icon font. Pages use house, pie chart, chart line, wallet and settings. Rows use arrows for out, in and transfer, a gem for gold and a user for held for others. The bolt sits beside the wordmark at 26px and is never recoloured by hand.

## Before a screen ships, it has none of these

- All-caps labels, including in the sidebar.
- A vivid gradient card, or two leads in one section.
- More than five table columns, or an empty table with headers.
- Strong rose or green text for everyday amounts, or grey spending bars.
- The lead on the right, or stretched to its neighbour's height.
- White or tinted panels inside a lead card.
- Text links with arrows ("Review →").
- Dropdowns for your own data.
- Grey, blue or rose text on the lead card; ▼, ^ or − as open/close markers.
- Dates like "30 Sep 2026" or "31/1"; "– 5,000.00" or "-455.00" instead of −5,000.00.
- A period control above figures it doesn't change.
- The same number under two names.

## Open visual gaps

- On a phone, the transactions register scrolls sideways inside its card.
- Plan: the forecast line doesn't mark the lowest point yet (a key note names it).
- Budget: there is no share bar of the plan used.
- Transactions, account pages and Settings have not had the key-notes and charts pass.
- Dark mode is not wired in.

## Versions

| Version | Date | What changed |
|---|---|---|
| 2.1 · Bloom | 2026-09-29 | Soft rose for money-out and spending bars, replacing grey. The lead number is always ink. Strong rose only for over plan, negative balances and errors |
| 2.0 · Clearing | 2026-09-29 | Lead left on the soft gradient, white support right; the vivid gradient leaves cards; toggle lists replace panels inside cards; the Sections part |
| 1.1 | 2026-09-29 | Meadow light by default with a dark preview; a faint wash on white cards; a soft band under breakdown results |
| 1.0 | 2026-09-29 | First app guideline |

Additions are numbered 2.2, 2.3 and so on. A change to the card rules is 3.0. Each version gets a name.
