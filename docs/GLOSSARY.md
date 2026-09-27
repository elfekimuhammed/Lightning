# Glossary and taxonomy

## Document status

- **Last updated:** 2026-09-27
- **Document revision:** 2026-09-27.1
- **App version:** 0.3.0 (`lightning/__init__.py`); `pyproject.toml` packaging metadata remains at 0.1.0.
- **Role:** canonical product and technical terms. Current workflow and roadmap live in [Project Overview](PROJECT_OVERVIEW.md); calculation contracts live in [Architecture](ARCHITECTURE.md).

This is Lightning's canonical language for product, database, code, and UI. Use these definitions consistently. The user's visible label is the **Name**; IDs and codes support data integrity and lookup and should not clutter ordinary screens.

## The basic model

| Term | Meaning | Example |
|---|---|---|
| **Account** | Where value is held. | CIB, Cash wallet, THNDR brokerage |
| **Financial asset** | What value is held or counted in an account. Designed as an extensible type so new products can be added without changing the account model. | EGP cash, COMI share, fund unit, CD, gold gram |
| **Asset class** | A grouping for financial assets; describes what kind of wealth it is, not where held or why a payment happened. | Funds → Money Market |
| **Exposure** | What economic value an asset tracks, separately from its wrapper/class. | Gold fund → Gold exposure |
| **Holding / position** | Calculated quantity of one financial asset in one account at a date. | 100 COMI shares in THNDR |
| **Physical item** | Individually named tangible asset tracked by piece count, per-piece net gold-bearing weight, karat, cost, and valuation reference. Its item record is not a tickered security. | One Gold ring, 1 piece, 4.2 g of 18K alloy |
| **Net gold weight** | Grams of gold-bearing alloy per physical piece, excluding stones and non-gold parts. It is not fine-gold grams unless the item's karat is 24K. | Ring: 4.2 g at 18K |
| **Fine-gold exposure** | Pure-gold-equivalent grams derived for allocation/reporting: piece count × net gold grams per piece × karat/24. This reporting measure does not change the item's display weight or reference valuation formula. | 1 × 4.2 g × 18/24 = 3.15 g fine gold |
| **Karat-specific gold price** | Price per gram of alloy at the named karat. Multiply by matching-karat net gold weight; never adjust the quote by purity again. | EGP per gram of 18K gold |
| **Acquisition cost** | Historical total paid for the item's current acquired quantity; may include workmanship, stones, and fees. Reference-price updates never change it. | 18,000 EGP including workmanship |
| **Manual item valuation** | User-entered dated total value for a physical item and its held quantity, used when the shared gold price is unsuitable. | Ring's 2026-09-26 resale estimate |
| **Balance** | Calculated value/quantity of an account or position on a date; not an independent user-entered fact. | 12,000 EGP; 100 shares |
| **Activity** | The broad reason/kind of a transaction, represented by its category family. It is independent of whether money came in or went out. | Personal, Work, Investment |
| **Category** | A label for the activity behind a transaction. Categories do not describe the counterparty, account, or owned asset. | Personal → Food & Groceries |
| **Counterparty** | The canonical person, business, institution, or own account on the other side of a transaction. A saved canonical name can have confirmed aliases; close matches are suggestions and require an explicit user decision. | Talabat, employer, CIB |
| **Confirmed alias** | User-approved alternative spelling attached to one canonical Counterparty; up to ten per Counterparty. A typo suggestion is not an alias until confirmed. | “Talbat” saved for Talabat |
| **Search suggestion** | A ranked possible match shown to help recover from spelling mistakes; it never silently chooses an identity, transfer, category, or custody owner. | “Did you mean Talabat?” |
| **Whom / owner** | Who actually owns funds/assets held in the user's account. Separate from Counterparty: one identifies transaction context, the other identifies beneficial owner/custody. | Dad owns part of THNDR cash |
| **Transaction** | A dated user or system event shown in the main ledger. | 450 EGP Talabat payment |
| **Main ledger** | The single activity ledger from which account registers, all-transaction view, budget actuals, and reporting are derived. | Register filtered to CIB |
| **Ledger line / journal line** | One transaction's effect on a particular account and financial asset. | CIB cash −450 EGP |
| **Owner ID** | Optional Counterparty reference on a ledger line; blank means the user owns the value on that line. | Dad owns 2,000 EGP of THNDR cash |
| **Money in / money out** | Direction in which value crosses an account boundary. Direction does not determine category. | Salary is money in; grocery purchase is money out |
| **Transfer** | Value moved between accounts owned by the user; not income or expense. Selecting an owned account as Counterparty creates both account effects. | CIB → THNDR |
| **Investment trade** | Exchange of brokerage cash for asset units (buy) or units for cash (sell). It is recorded inside that brokerage account's register. | Buy 10 fund units |
| **Budget** | Planned spending amount attached to a category/group and month. Budget limits are not reserve accounts or ledger transactions. | Monthly Food limit |
| **Monthly limit** | New amount allowed by a budget line for a month, from a fixed setting or a chosen rolling average. | Food limit of 3,000 EGP |
| **Available limit / room in plan** | Monthly limit plus opening carryover; room is that available limit less actual spending. It is a spending constraint, not bank cash. | 3,000 + 500 carried in − 1,200 spent = 2,300 room |
| **Budget carryover** | Optional unused spending room added to a later month's limit. It never sets aside cash, creates a transaction, or reduces free cash. | 500 EGP of unused Food limit carried into October |
| **Reserve** | A plan assigning some already-owned cash to an emergency fund or future goal. Assignment does not itself move money or change net worth; the actual payment is a normal ledger transaction. | Rent reserve |
| **Emergency fund** | Permanent, dedicated reserve section. Its progress can be compared with the completed six-month average salary to express coverage in salary-months. | 13 months of average salary |
| **Cash available to spend** | Owned bank and wallet cash at the selected date, less effective reserve assignments at that date. It can be negative when assignments exceed eligible cash; brokerage cash is excluded until moved to a bank or wallet. Past values are unavailable before assignment history can be reconstructed. | 380,000 eligible cash − 51,000 assigned = 329,000 EGP |
| **Change during this period** | Owned value at the selected range end minus owned value immediately before its start. It describes tracked wealth movement, not investment return. | 420,000 EGP ending value − 400,000 EGP opening value = +20,000 EGP |
| **Net worth / owned wealth** | The user's share of tracked assets after excluding outstanding money belonging to others. Lightning does not currently track liabilities or money owed to the user. | Account total 20,000; Dad's 5,000 excluded; owned 15,000 |
| **Estimated liquidatable assets** | Scenario value: owned liquid cash plus owned investments multiplied by the user's liquidation factor. It is neither full owned wealth nor a sale quote. | 380,000 cash + 95% of 20,050 invested |
| **Liquidation factor** | User-selected percentage applied to owned investment value in the liquidation scenario. It does not change holdings or full owned wealth. | 95% |
| **Money from others / custody** | The separately attributable amount that belongs to another person but sits in an account the user tracks. It remains in the full account balance but is excluded from owned totals, net worth, and relevant budget/overview totals. | Dad's 10,000 in CIB |
| **Revaluation** | Change in investment value caused by price changes, not deposits, purchases, or withdrawals. | Shares appreciate by 1,000 EGP |
| **Reevaluation ledger** | Monthly per-account/per-asset record of units, prices, values, and returns. Its account-level total links to one generated journal transaction in the main ledger. | September COMI return detail linked to one THNDR `VAL` journal |
| **System-generated posting** | An auditable ledger transaction created by application rules, not manually entered by the user. | Monthly `VAL` journal |
| **Cost basis / average cost** | Remaining units' recorded acquisition cost, including buy fees when fees are included in total. | Remaining shares cost 9,500 EGP |
| **Realized / unrealized return** | Gain/loss from units sold / change in value of units still held. | Sale gain / current paper gain |
| **XIRR** | Annualized money-weighted investment return from dated cash flows and an ending value. A since-inception rate and a selected-period currency return answer different questions; an unavailable result needs an explanation. | Portfolio XIRR since first contribution |
| **Opening balance** | A separately dated ledger entry for the account's value at a chosen point. It does not set a minimum date for later-entered activity; users can add earlier transactions at any time. | CIB starts at 50,000 EGP on 1 January; a December transaction may be added later |
| **Void / delete** | A recoverable correction that removes a transaction from active balances while retaining history. | Void a duplicate import |

## Category taxonomy (why the activity happened)

There are three levels in the model, but only two are used now:

- **L1 — Activity family:** Personal · Work · Investment.
- **L2 — Broad category:** the simple, useful analysis bucket within one family.
- **L3 — Detail:** intentionally unused/empty for now. Do not prepopulate it; add only when a user chooses to track more detail.

Examples: `Personal → Food & Groceries`, `Work → Salary`, `Investment → Dividends`. Categories are not divided into income and expense trees: choose the activity that explains the event regardless of sign. For example, a refund should retain the original activity category. Counterparty defaults may suggest a category (Talabat → Personal / Food & Groceries), but the user can choose another.

Categories are selected from an explicit list, not silently created by typing. Names are sorted alphabetically within their parent. A category with historical use cannot be physically deleted; it is archived. Archived categories remain legible on old transactions but cannot be selected for new ones. Names should be unique among siblings; the same broad term may exist under different L1 families when meaning differs (e.g., Transportation under Personal and Work).

## Names and identifiers

| Term | Rule | Example |
|---|---|---|
| **Name** | Human-readable label shown in ordinary app screens. Account codes never appear under account names in normal UI. Canonical Counterparty names are unique; other taxonomy names may repeat under different parents. | CIB; Talabat; Food & Groceries |
| **Code** | Stable machine-friendly identifier for relationships, imports, and technical search. It is not the display name and should not appear in ordinary account UI. | `STK:COMI` |
| **ID** | Internal database key; not meaningful to a person and never displayed. | `account_id = 12` |
| **Ticker / symbol** | Public exchange/provider symbol used to find an instrument. It is not Lightning's code or database ID. | `COMI` |
| **ISIN** | Optional global security identifier, useful for source matching; ordinary users need not know or enter it. | Egyptian security ISIN |
| **Unit** | What is counted for an asset. | EGP, share, fund unit, gram |
| **Transaction reference (ref)** | Fixed human-readable ID assigned to a transaction. It does not change if its date is edited and has no account prefix because transfers can touch two accounts. | `OUT-2026-09-25-003` |
| **Ledger-line reference** | A transaction ref plus its line number. | `TRF-2026-09-26-001/2` |
| **Date input** | Accepts ISO (`2026-01-31`), day/month/year (`31/1/2026`), or day/month (`31/1`, current year); stored canonically as ISO. Ambiguous numeric dates are interpreted day-first. | `31/1` → `2026-01-31` in 2026 |

## Asset and account taxonomy (what vs where)

Financial assets can include currency/cash, stocks, funds, physical gold, deposits/CDs, and future supported asset kinds. Asset class and exposure are separate dimensions: a gold fund is a Fund by wrapper/class but has Gold exposure. Account types describe location/container, for example cash wallet, bank account, deposit account, brokerage, physical-asset location, and other asset account. A brokerage may contain both its cash balance and many investment holdings.

Example internal-code patterns (for data/search, not routine UI labels):

- Account: `INSTITUTION-TYPE-CURRENCY`, e.g. `THNDR-BRK-EGP`.
- Financial asset: `CLASS:SYMBOL`, e.g. `CASH:EGP`, `STK:COMI`, `FND:AZG`, `GLD:21K`.
- Category/asset-class path: dotted tree code; nesting in the UI is by parent, not repeated breadcrumb text on every child.

## Transaction and posting types

`OPN` opening · `IN` inflow · `OUT` outflow · `TRF` internal-account transfer · `BUY` investment buy · `SEL` sell · `DIV` dividend · `VAL` system-generated valuation · `ADJ` reconciliation adjustment · `CNV` conversion (future/multi-currency use).

An investment overview is a filtered/calculated view, not a separate place for buy/sell/dividend entry: those transactions are entered within the brokerage account register. Monthly return details live in the reevaluation ledger; one aggregate per affected account is journaled in the main ledger for reconciliation.
