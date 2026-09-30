# Application brand guide

The canonical visual reference is [`application-brand-guide.html`](application-brand-guide.html), supplied as **Lightning App guideline 2.1 · Bloom**. Use it for visual properties such as palette, typography, card surfaces, spacing, controls, and chart styling.

The file's sample copy, labels, values, page arrangement, reporting semantics, and interaction examples are illustrative only; they do not change product requirements or existing workflows.

## Asset class colours (2026-09-30)

One hue family per kind of asset, a lighter shade for the fund version. The swatches are in the HTML guide under 08 Data visuals, and the tokens are `--class-*` in `lightning/ui/static/style.css`.

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
