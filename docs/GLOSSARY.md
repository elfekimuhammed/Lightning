# Glossary and taxonomy

## Document status

- **Last updated:** 2026-09-30
- **Document revision:** 2026-09-30.1
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
| **Monthly base budget** | A tracked category’s monthly plan before any carryover: fixed EGP, a selected percentage of budgeting income, or an observed-month spending average. | Food fixed at 3,000 EGP or 10% of income |
| **Observed-month average** | Spending average whose 3m/6m window is divided by the distinct months with qualifying recorded activity. Months without activity are not treated as zero and the window is not extended backward. | 12,000 EGP across two observed months in a six-month window = 6,000 EGP |
| **Available limit / room in plan** | Monthly base budget plus signed incoming carryover; room is the available amount less owned spending. It is a spending constraint, not bank cash. | 3,000 + (−500 carried in) − 1,200 spent = 1,300 over plan |
| **Budget carryover** | Optional unused spending room added to a later month's limit. It never sets aside cash, creates a transaction, or reduces free cash. | 500 EGP of unused Food limit carried into October |
| **Reserve** | A plan assigning some already-owned cash to an emergency fund or future goal. Assignment does not itself move money or change net worth; the actual payment is a normal ledger transaction. | Rent reserve |
| **Emergency fund** | Permanent, dedicated reserve section. Its progress can be compared with the completed six-month average salary to express coverage in salary-months. | 13 months of average salary |
| **Full owned wealth** | The known value of all tracked assets that belong to the user, including assigned reserves and brokerage cash, after excluding custody. Missing valuations are called out. What you owe is shown beside it as a separate item (see Net worth); receivables are outside the current model. | 400,000 EGP of owned assets; 10,000 EGP held for Dad is excluded |
| **Free cash** | Owned liquid cash in wallets, banks, and brokerage accounts less effective reserve assignments **and bills due** for the selected date. Brokerage cash is included but must be transferred before everyday spending. Historical values are unavailable when reserve history cannot be reconstructed. A cash forecast never changes it. | 380,000 EGP owned liquid cash − 51,000 assigned − 480 bills due = 328,520 EGP free cash |
| **What you own** | Owned wealth: in your accounts minus money held for others. Shown as the lead figure whenever nothing is owed. | 255,717.74 EGP |
| **What you owe** | Certain obligations only: bills due plus loans still to pay, each payment counted once. Upcoming bills and forecasts are not included. | 480 EGP electricity due + 60,000 EGP car loan = 60,480 EGP |
| **Net worth** | What you own minus what you owe. When nothing is owed it equals what you own, and the Overview shows What you own instead. | 255,717.74 − 60,000 = 195,717.74 EGP |
| **Cash planning** | The tab for spendable cash and commitments. Sub-tabs: Plan, Recurring, Loans, Reserves. Nothing in it posts to the ledger on its own. | — |
| **Recurring item** | A bill, subscription or income that repeats on a schedule (weekly, monthly, every 3 months, yearly, or once). | WE Internet · 650 EGP monthly on day 20 |
| **Loan** | A loan or installment plan, entered as its payments: amount per payment, the next payment date, and payments left. Optional amount borrowed. | Car loan · 24 × 2,500 EGP from 2026-10-05 |
| **Payment status** | For each scheduled date: **Paid** (settled by a posted transaction), **Skipped** (the user says it won't happen), **Due** (the date is today or earlier and nothing settled it) or **Upcoming**. Voiding the linked transaction makes it Due again. | Rent · 2026-10-03 · Upcoming |
| **Bills due** | Every Due bill, subscription and loan payment. It comes off free cash now. | 480 EGP electricity dated 2026-09-25, unpaid |
| **Loans still to pay** | Every unpaid loan payment, due or upcoming. It comes off net worth; only the due ones come off free cash. | 24 × 2,500 = 60,000 EGP |
| **Cash forecast** | An estimate that carries free cash forward month by month with scheduled payments, the budget still planned and reserve goals. A bill in a budgeted category counts inside that budget, never on top. It never changes net worth or free cash. | 2026-11 ends with 93,220 EGP |
| **Average income** | Owned income averaged over the last three completed months that had income. The forecast uses it only when no income is scheduled, and labels it. | 45,000 EGP over 2 months |
| **Safe to spend** | Free cash less the bill and loan payments before the next income, the budget still planned this month, and what reserve goals still need. Shown with its parts as an estimate. | 57,815 − 1,845 = 55,970 EGP until 2026-10-01 |
| **Change during this period** | Owned value at the selected range end minus owned value immediately before its start. It describes tracked wealth movement, not investment return. | 420,000 EGP ending value − 400,000 EGP opening value = +20,000 EGP |
| **Owned wealth / full owned value** | The user's known share of all tracked assets after excluding money belonging to others. Reserves remain owned. Certain obligations are tracked in cash planning as What you owe and shown beside it; money owed to the user is not tracked. | Account total 20,000; Dad's 5,000 excluded; owned 15,000 |
| **Estimated available value** | Birdview scenario: free cash plus the sum of owned investment value in each asset class multiplied by that class's current liquidation factor. Brokerage cash is counted once in free cash. It is not full owned wealth, a sale quote, or a ledger loss. | 329,000 EGP free cash + 95% of a 20,050 EGP investment class |
| **Liquidation factor** | User-selected 0–100% estimate applied to one owned investment asset class. It does not change holdings or full owned wealth. Historical scenarios use current factor settings. | Gold 90%; equity funds 95% |
| **Money from others / custody** | The separately attributable amount that belongs to another person but sits in an account the user tracks. It remains in the full account balance but is excluded from owned totals, net worth, and relevant budget/overview totals. | Dad's 10,000 in CIB |
| **Revaluation** | Change in investment value caused by price changes, not deposits, purchases, or withdrawals. | Shares appreciate by 1,000 EGP |
| **New money added** | Owned cash/value entering the investment boundary from outside it. A brokerage deposit followed by a purchase is counted once; an opening holding is excluded. | 10,000 EGP transferred into a brokerage |
| **Money withdrawn** | Owned cash/value leaving the investment boundary for a bank or wallet, including direct sale proceeds paid outside investment accounts. | 2,000 EGP of sale proceeds transferred to a bank |
| **Net money added** | New money added less money withdrawn during the selected period. | 10,000 added − 2,000 withdrawn = 8,000 EGP |
| **Change in unrealized gain/loss** | Unrealized balance at period end less the balance immediately before period start. | 1,200 EGP ending unrealized − 900 EGP opening = +300 EGP |
| **Investment result** | Realized gain/loss plus change in unrealized gain/loss plus posted distributions, with distinct FX and costs counted once. | 300 realized + 200 unrealized change + 50 distributions |
| **Estimated cash after sale** | Investment cash plus owned dated holding values multiplied by asset-class liquidation factors; excludes reserves and is an assumption-based scenario. | 1,000 cash + 90% of a 10,000 EGP holding |
| **Opening adjustment** | A holding entered as already owned when tracking began; it establishes a baseline and is not period contribution. | 5,000 EGP cost basis entered on tracking start |
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
