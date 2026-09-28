# Lightning application visual system

Derived from the supplied Meadow brand guide, 28 September 2026. This is the application adaptation: retain the identity while replacing landing-page scale and repeated decorative cards with compact financial workspaces. The supplied document is a design reference; its signup, campaign, and external-service instructions are not application requirements.

## User preference: quiet, soft, number-led

The user explicitly prefers minimalism and softness, with numbers as the highlight rather than gradients, animation or colourful decoration. This preference overrides the source guide’s vivid focal surface. Use a nearly neutral canvas (`#F5F8F7`), white/paper data cards, and a very soft sage key-card surface (`#EFF6F3`). Primary amounts are Ink, large and tabular. No decorative gradients or motion. Keep brand colours for a restrained primary action, links and meaningful status.

## Three structures, repeated everywhere

| Structure | Fixed order | Use |
|---|---|---|
| Summary | Page title and period → compact key card with category toggles → focused follow-ups | Overview, Budget, Investments |
| Analysis | Section title and scope → one chart → exact values or transaction drilldown | Composition, spending, performance |
| Work list | Title → search/filter and primary action → rows → details/edit | Accounts, transactions, reserves, names, categories |

Do not invent a new layout for a new metric. A page combines these structures. Use the same horizontal rhythm, header placement, filter position, units, and link treatment in every instance.

## Card hierarchy: three types only

1. **Result:** `.key-card`, with one headline amount, currency and date/scope, followed by a short aligned category list. Each `.key-card-row` uses a native details/summary toggle: label left, amount right, supporting records or explanation below. This is the user-selected reference pattern. At most one primary key card per analytical page. Overview: free cash; Budget: remaining/over-plan; Spending: total; Investments: result. Prefer a flat soft sage surface and dark Ink text. The supplied screenshot informs the category-toggle structure, not a requirement to retain its gradient. Never repeat the headline total as the last row. No fixed height or empty filler. Negative/unavailable values remain explicit. Ordinary `.metric-card` tiles support distinct measures only; do not scatter the breakdown across many cards.
2. **Data:** `.data-panel` and ordinary `.metric-card`. Neutral paper/white, thin border, restrained or no shadow. Header, chart/list/table, then optional drilldown. No card nesting solely to group text. Supporting metrics have equal weight.
3. **Interaction:** `.interaction-panel`. Neutral surface with clear fields, one primary action, optional cancel, and adjacent validation. Often a modal or disclosure. Open automatically when validation requires attention.

Notes and assumptions are inline muted text or a standard disclosure, not another decorative card type. Errors, missing prices and required decisions remain visible. Alerts use a consistent icon/text/status treatment outside the card hierarchy.

### Key-card anatomy

Headline label → amount and currency → scope/date → 3–5 category summary rows → contextual detail only when expanded. Align all row amounts to the same right edge. Use one shared expand/collapse icon and visible keyboard focus. A row without supporting content is static, not a fake toggle. Expand content in place, keep the surrounding card stable, and preserve keyboard access. Reserve the final footer for one useful drilldown. This reference structure takes precedence over presenting every subtotal as a separate tile.

## Colour tokens and meaning

| Token | Value | Application role |
|---|---|---|
| Ink | `#0D2233` | Main text and financial values |
| Secondary ink | `#304A5C` | Supporting content |
| Muted | `#5C7483` | Labels and dates on light paper |
| Meadow | `#14A874` | Positive series/progress, decorative accent |
| Meadow dark | `#0B8A5F` | Large positive text/accent |
| Accessible positive text | `#08764F` | Small positive labels on light surfaces |
| Azure | `#0B6DD6` | Neutral comparison series, links and custody context |
| Nile | `#0A2442` | Primary actions and selected controls |
| Rose | `#C93D72` | Overage/negative series; pair with signed values |
| Accessible negative text | `#A82F5D` | Small negative labels, particularly tinted surfaces |
| Paper | `#F8FCFA` | Quiet card surface |
| Border | `#DDE9E6` | Dividers and card edges |
| Canvas | `#E3F6EC` → `#E1EEFB` | Very soft page environment |

Growth/income uses Meadow; neutral allocation and ordinary spending use Azure; overspending/shortfall uses Rose. Spending is not automatically bad. Categories use a small stable palette with labels, never random colours. The primary category-toggle card uses a flat quiet surface and dark text. The user’s latest preference replaces the screenshot’s gradient while retaining its structure. The brand's vivid gradient is `#0C9B63 → #0A9E96 → #0B6DD6`; retain it as a brand reference only; do not use it in the application’s quiet default theme. Normal white text does not pass AA on its original green/teal stops. The supplied Meadow Dark is approximately 4.36:1 against white, so use the darker text token for small labels. Check the actual background, not just white.

## Typography and financial values

Brand families: **Bricolage Grotesque** for titles and major figures; **Manrope** for controls and body. Prefer locally bundled font assets. Until these assets are bundled, use the existing Plus Jakarta Sans/Inter fonts as deliberate offline fallbacks; do not make the local app depend on Google Fonts. Keep IBM Plex Sans Arabic for Arabic glyph coverage.

| Role | App size | Treatment |
|---|---|---|
| Page title | 26–30 px | Display, 700–800; one per page |
| Section heading | 18–20 px | Display, 700; sentence case |
| Primary metric | 28–32 px | Tabular numbers; avoid clipping large balances |
| Supporting metric | 22–26 px | Tabular numbers |
| Body / table | 14–15 px | Body, 400–500, line-height 1.45–1.55 |
| Label / help | 12–13 px | Body, 500–600; preserve contrast |

Use full precision appropriate to the existing money formatter; the marketing guide's whole-EGP examples do not override accounting decimals. Put the currency in the same position beside each metric; put shared units in a table/chart header. Right-align numeric columns. Use a true minus sign or consistent signed formatting. Label unknown values “Unavailable”; zero means a known zero. Always distinguish position date from activity range.

## Spacing and controls

Use a 4 px scale: 4, 8, 12, 16, 20, 24, 32. Typical card padding 16–20 px, grid gap 14–18 px, section gap 24 px. Ordinary radius 16 px, focal radius up to 22 px, inputs 10–12 px. Avoid fixed/minimum heights on content cards; align using grids without manufacturing empty space.

- Primary: Nile fill, white label, pill shape, 44–48 px target, one per task area.
- Secondary: white/paper fill, border, dark label, same control height.
- Tertiary: text link for drilldown or “More actions”; never disguised as a primary action.
- Destructive: explicit verb and negative colour; separate from the routine primary action.
- Selected period/filter: Nile and white, with an accessible selected state. Labels retain their meaning across pages.
- Focus: visible high-contrast ring with offset. Disabled controls look disabled and explain why when useful. Reduced motion disables decorative transitions.

## Three chart grammars

| Question | Chart | Required elements |
|---|---|---|
| Which is larger / where did it go? | Ranked horizontal bars | Left labels; shared baseline/scale; right exact values; scoped drilldown |
| How close am I to my limit or goal? | Progress bar | Actual, target, remaining/overage text; fill capped at 100%; excess shown explicitly |
| How did it change? | Line over time | Comparable dated points, units, baseline/axis, honest gaps for missing values; matching table/detail access |

Keep legends, labels and tooltips consistent. Do not use a donut, gauge, stacked bar or sparkline merely to decorate a number. Never mix stocks (wealth) and flows (income) in one scale. Negative/refund values require signed labels and nonnegative visual dimensions; a chart must not silently omit them. For sparse or empty data, show the fact and a useful action instead of a fake chart.

## Tables, forms, states and responsive use

Sidebar: every destination uses its own simple outlined SVG icon, with consistent 20 px size and stroke. Use familiar meanings, not letters or decorative emoji. Settings contains Counterparties, Categories and Data checks; there is no Management toggle. The account list separates its heading, subdued type labels, account names and right-aligned balances by typography and spacing, not several competing coloured boxes. Selected accounts use the same restrained selected-state treatment as tabs.

Tables share aligned headers, subtle row dividers, restrained hover, and one visible detail/edit path. Group secondary maintenance in the same menu pattern. Search belongs above the list it affects. Never truncate financial values; allow horizontal scrolling for genuinely wide ledgers and keep the rest of the page within the viewport.

Forms use persistent labels, optional hints, clear required fields, and preserved values on error. Display import decisions before posting. Put copy/download feedback next to the control. Empty states explain what is absent and offer the next relevant action; they do not advertise unimplemented capabilities.

At narrower widths, four metrics become two then one, and paired panels stack in reading order. Primary actions stay reachable. Focus, colour-independent status labels, Arabic text handling, keyboard dialogs, and long currency values are review gates. This visual system does not itself claim full localization, RTL support, or international financial compliance.

## Implementation review

The visual reference should demonstrate the three structures and card types, controls/states, table, comparison/progress/time-series charts, and a narrow layout using the same stylesheet as the app. Its sample financial data must be labelled illustrative. Future components must fit these patterns or explain why a new pattern is necessary.
