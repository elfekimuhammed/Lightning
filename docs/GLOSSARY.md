# Glossary and taxonomy

This is the canonical vocabulary for the product, database, code, and UI. Use these meanings consistently.
The plain **Name** is for people; internal identifiers are for linking and integrity.

## Core concepts

| Term | Definition | Example |
|---|---|---|
| **Account** | A place where value is held. It answers **where?** | CIB Current, Wallet, THNDR, Gold at home |
| **Account type** | The kind of place where your value is held; it sets reporting and allowed activity. | Bank, cash wallet, deposit/CD, brokerage |
| **Financial asset** | A kind of value that can have a balance or units. It answers **what?** | EGP cash, COMI shares, AZ Gold Fund units, gold grams |
| **Asset class** | A taxonomic group for financial assets. It answers **what kind?** | Funds → Gold Fund |
| **Exposure** | The economic thing an investment's value follows, independent of its wrapper/class. | A gold fund has Gold exposure |
| **Holding / position** | The calculated quantity of one financial asset in one account at a point in time. | 150 COMI shares in THNDR |
| **Balance** | The calculated quantity or value in an account/position at a date; not a separately typed fact. | 12,000 EGP; 150 shares |
| **Category** | The activity a transaction belongs to. Categories are grouped by Personal, Work, or Investment—not by whether money entered or left. It does not describe what is owned. | Personal → Food & Groceries |
| **Counterparty** | The canonical person, business, institution, or owned account on the other side of a transaction. A canonical name is unique; source spellings such as “Talabaat” can be stored as aliases of “Talabat”. Typing a new value creates its canonical record when no close match exists; a near-match must be explicitly reused or explicitly created. Confirmed alternate spellings become aliases and ledger transactions link to the canonical record. Choosing an owned account makes a transfer. | Talabat, employer, or CIB Current |
| **Transaction** | The dated event a person records and edits. It may have one or more ledger effects. | A 450 EGP Talabat purchase |
| **Ledger line** | One effect of a transaction on one account and financial asset; lines are the balance source of truth. | CIB cash −450 EGP, categorized as Food |
| **Money in / inflow** | Value entering an account from outside. It uses the activity category that best explains it. | Salary under Work; refund under its original Personal activity |
| **Money out / outflow** | Value leaving an account. It uses the activity category that best explains it. | Groceries under Personal → Food; work software under Work |
| **Transfer** | Value moving between accounts owned by the user. It is neither income nor spending and does not change net worth. | CIB → THNDR |
| **Investment trade** | A conversion between cash and investment units; buys and sells are internal movements, not household spending/income. | Buy 10 fund units using brokerage cash |
| **Budget** | A planned amount for a category (or category group) in a month. | 6,000 EGP for Food in October |
| **Net worth** | The value of the user's tracked accounts and assets minus outstanding money belonging to others. Ordinary loans and credit-card debt are outside the product scope. | Owned balances − a relative's 20,000 EGP held in your bank account |
| **Money from others / money held for others** | A separately tracked custody balance, assigned to its owner and account. Positive entries record money received or identified; negative entries record returns. The outstanding balance is excluded from net worth. | A relative's 20,000 EGP in your bank account |
| **Revaluation** | A change in value with no purchase, sale, or cash movement, caused by a price or exchange-rate change. | COMI price rises from 92 to 98 EGP |
| **Cost basis** | The recorded cost of the units still held, including buy fees; average-cost method. | Remaining shares cost 9,500 EGP |
| **Realized / unrealized gain** | Gain/loss locked in by a sale / change in value of units still held. | Sold gain / paper gain |
| **Opening balance** | The cash value in an account when tracking starts. An investment position already owned is recorded separately as an opening holding with units and total cost. | 50,000 EGP in CIB on the tracking start date |
| **Void** | A cancelled transaction retained for history but excluded from balances and reports. | A duplicate entry marked void |

## Names and identifiers

| Term | Meaning and rule | Example |
|---|---|---|
| **Name** | Human-readable, editable text shown as the primary label in the UI. Names need not be unique. | `CIB Current`, `Commercial International Bank` |
| **Code** | A unique machine-friendly identifier for a master record. It can be edited and is useful for relationships, imports, exports, and technical search; ordinary screens should lead with the Name. | CIB-CUR-EGP, STK:COMI |
| **ID** | Internal database key used to connect records. It is not meaningful to users and should not be displayed. | `account_id = 12` |
| **Label** | Text shown to identify a record in a particular screen. Ordinary account headings use the Name; account pickers may include a code to distinguish accounts. A label is not a separate identity. | CIB Current; a technical picker may show CIB-CUR-EGP · CIB Current |
| **Ticker / symbol** | Identifier assigned by an exchange, fund provider, or market-data provider. It is not the app's internal ID. | `COMI`, `AZG` |
| **ISIN** | International Securities Identification Number, when available. Optional metadata used to resolve a security across sources. | `EGS…` |
| **Unit** | The thing counted for a financial asset. | EGP, share, fund unit, gram |
| **Reference (ref)** | Fixed identifier for a transaction document. Unlike a Name, it does not change if the transaction date is edited. | `OUT-2026-09-25-003` |

## Taxonomy: what is owned (asset classes)

Asset class is a tree attached to a financial asset. Accounts describe **where** it is; asset class describes **what kind** it is.

- **Liquid Cash** → Physical Cash · Bank Balance · Brokerage Cash
- **Deposits** → CDs / Time Deposits
- **Stocks**
- **Funds** → Equity · Money Market · Fixed Income · Gold · Other
- **Gold** (physical gold, measured in grams)
- **Other Investments**

`Exposure` is a separate reporting dimension: Cash · Equity · Fixed Income · Gold · Real Estate · Other. For example, a gold fund is classed as a Fund → Gold Fund and has Gold exposure. Do not create a new asset class just to represent a location/account or a transaction purpose.

## Taxonomy: why money moved (categories)

Categories form a separate tree. A transaction's category explains its activity; it does not identify the merchant, account, or asset. Category stays the same for money in or out; direction belongs to the transaction.

- **Personal** → Food & Groceries · Eating Out · Transportation · Housing & Rent · Utilities & Bills · Health · Shopping · Entertainment · Education · Travel · Gifts & Donations · Fees & Charges · Taxes · Gifts Received · Other Income
- **Work** → Salary · Bonus · Business & Freelance · Transportation · Software · Meals · Office Supplies · Travel · Other Work
- **Investment** → Interest · Dividends · Investment Fees · Other Investment
- **Unaccounted** system categories are reconciliation fallbacks, not normal user choices.

Transfers, investment buys/sells, opening balances, and revaluations are not everyday expense categories. A saved Counterparty may have a default category (e.g. Talabat → Food); users can override it on a transaction. Category remains separate from Counterparty.

## Taxonomy: accounts (where value is held)

- Cash wallet
- Bank account (current or savings)
- Certificate / time deposit (CD)
- Brokerage / investment account (e.g. THNDR)
- Physical asset location (e.g. gold at home)
- Other asset account

A brokerage account can contain brokerage cash and many investment positions. The account is not itself a stock or fund.

## Codes and patterns

| Record | Pattern | Examples |
|---|---|---|
| Account | `INSTITUTION-TYPE-CURRENCY` | `CIB-CUR-EGP`, `THNDR-BRK-EGP`, `WALLET-CSH-EGP` |
| Financial asset | `CLASS:SYMBOL` | `CASH:EGP`, `STK:COMI`, `FND:AZG`, `GLD:21K` |
| Asset class | Dotted tree path | `CASH.BANK`, `DEPOSIT.CD`, `FUND.FIXED_INCOME` |
| Category | Dotted tree path | `EXP.PERSONAL.FOOD`, `EXP.WORK.SOFTWARE`, `EXP.INVEST.DIVIDEND` |
| Transaction reference | TYPE-yyyy-mm-dd-NNN; it identifies the transaction, not a particular account. It has no account-code prefix because a transfer touches two accounts. Transaction search can find account codes through their ledger lines. | OUT-2026-09-25-003 |
| Ledger line | `<transaction ref>/<line number>` | `TRF-2026-09-26-001/2` |

Account-type abbreviations: `CSH` cash wallet · `CUR` bank · `CD` certificate/time deposit · `BRK` brokerage · `PHY` physical asset · `OTH` other.

Financial-asset codes use prefixes such as `CASH`, `STK`, `FND`, `GLD`, and `OTH`. A ticker is used as the symbol when one exists; an app-generated symbol is not an exchange ticker.

## Product decisions and current implementation gaps

1. **UI shows names, not internal codes**, in ordinary navigation and forms. Codes stay available for technical details, search, and data exchange.
2. **Money from others** records another person's funds held in one of the user's accounts. Positive entries increase the amount held; negative entries record returns. The outstanding balance is excluded from net worth, without becoming income or spending.
3. **Counterparty is the universal register and import field** for the person, business, institution, or owned account on the other side. Each real-world party has one canonical record; confirmed aliases collapse harmless spelling variants, while approximate matches require a user to choose reuse or create. The register suggests canonical names, imports retain source spellings, and ledger entries link to the canonical identity. Categories remain distinct and are never duplicated to mirror merchant spelling.

## Transaction types

`OPN` opening · `IN` money in · `OUT` money out · `TRF` transfer · `CNV` conversion · `BUY` buy · `SEL` sell · `DIV` dividend · `VAL` valuation · `ADJ` reconciliation adjustment.
