# Glossary and taxonomy

This is the canonical vocabulary for the product, database, code, and UI. Use these meanings consistently.
The plain **Name** is for people; internal identifiers are for linking and integrity.

## Core concepts

| Term | Definition | Example |
|---|---|---|
| **Account** | A place where value is held. It answers **where?** | CIB Current, Wallet, THNDR, Gold at home |
| **Account type** | The broad kind of place, which controls how it is reported and what it can hold. | Bank, cash wallet, deposit/CD, brokerage |
| **Financial asset** | A kind of value that can have a balance or units. It answers **what?** | EGP cash, COMI shares, AZ Gold Fund units, gold grams |
| **Asset class** | A taxonomic group for financial assets. It answers **what kind?** | Funds → Gold Fund |
| **Exposure** | The economic thing an investment's value follows, independent of its wrapper/class. | A gold fund has Gold exposure |
| **Holding / position** | The calculated quantity of one financial asset in one account at a point in time. | 150 COMI shares in THNDR |
| **Balance** | The calculated quantity or value in an account/position at a date; not a separately typed fact. | 12,000 EGP; 150 shares |
| **Category** | Why money entered or left: an editable tree used to classify inflows/outflows. It does not describe what is owned. | Personal → Food & Groceries |
| **Payee / partner** | The person, company, merchant, employer, or institution at the other end of a transaction. A controlled partner record should be selected or created—not repeatedly typed as arbitrary text. | Talabat, CIB, employer |
| **Transaction** | The dated event a person records and edits. It may have one or more ledger effects. | A 450 EGP Talabat purchase |
| **Ledger line** | One effect of a transaction on one account and financial asset; lines are the balance source of truth. | CIB cash −450 EGP, categorized as Food |
| **Money in / inflow** | Value entering the user's finances from outside. Needs an income category. | Salary, dividend |
| **Money out / outflow** | Value leaving the user's finances. Needs an expense category. | Groceries, bank fee |
| **Transfer** | Value moving between accounts owned by the user. It is neither income nor spending and does not change net worth. | CIB → THNDR |
| **Investment trade** | A conversion between cash and investment units; buys and sells are internal movements, not household spending/income. | Buy 10 fund units using brokerage cash |
| **Budget** | A planned amount for a category (or category group) in a month. | 6,000 EGP for Food in October |
| **Net worth** | The value of what the user owns, less any tracked amounts that belong to someone else. Lightning does not aim to track ordinary loans or credit-card debt. | Owned assets − money held for others |
| **Money from others / money held for others** | Someone else's money temporarily present in the user's account. It is not owned wealth, income, or spending; it must be excluded from net worth and attributed to its owner/account. | A relative's 20,000 EGP in your bank account |
| **Receivable** | Money another person owes the user. This is distinct from money belonging to another person. Receivables are not part of the intended everyday personal-finance workflow. | A loan you made to someone |
| **Revaluation** | A change in value with no purchase, sale, or cash movement, caused by a price or exchange-rate change. | COMI price rises from 92 to 98 EGP |
| **Cost basis** | The recorded cost of the units still held, including buy fees; average-cost method. | Remaining shares cost 9,500 EGP |
| **Realized / unrealized gain** | Gain/loss locked in by a sale / change in value of units still held. | Sold gain / paper gain |
| **Opening balance** | What an account or investment position contained when tracking began. | 50,000 EGP on the tracking start date |
| **Void** | A cancelled transaction retained for history but excluded from balances and reports. | A duplicate entry marked void |

## Names and identifiers

| Term | Meaning and rule | Example |
|---|---|---|
| **Name** | Human-readable, editable text shown as the primary label in the UI. Names need not be unique. | `CIB Current`, `Commercial International Bank` |
| **Code** | Stable, unique, machine-friendly identifier for a master record. Used for relationships, imports, exports, and debugging—not as a subtitle beneath the Name in ordinary screens. | `CIB-CUR-EGP`, `STK:COMI` |
| **ID** | Internal database key used to connect records. It is not meaningful to users and should not be displayed. | `account_id = 12` |
| **Label** | A presentation string. Default UI label is the **Name**; show code only when it helps explicitly (e.g. a technical/export view). Never confuse a label with the record's identity. | `CIB Current` (UI), optional `CIB-CUR-EGP · CIB Current` in export |
| **Ticker / symbol** | Identifier assigned by an exchange, fund provider, or market-data provider. It is not the app's internal ID. | `COMI`, `AZG` |
| **ISIN** | International Securities Identification Number, when available. Optional metadata used to resolve a security across sources. | `EGS…` |
| **Unit** | The thing counted for a financial asset. | EGP, share, fund unit, gram |
| **Counterparty** | Current database/API term for the other party on a transaction; the UI concept is **Payee / partner**. Today this is stored as text with suggestions; a true partner dropdown requires a partner master-data model. | `Talabat` |
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

Categories form a separate tree. A transaction's category explains its purpose; it does not identify the merchant, account, or asset. Direction is part of the category rules.

- **Income (inflow)** → Salary · Bonus · Business & Freelance · Gifts · Other Income · Investment Income → Interest · Dividends
- **Expenses (outflow)** → Personal → Food & Groceries · Eating Out · Transportation · Housing & Rent · Utilities & Bills · Health · Shopping · Entertainment · Education · Travel · Gifts & Donations · Other Personal
- **Expenses (outflow)** → Work → Transportation · Software · Meals · Office Supplies · Travel · Other Work
- **Fees & Charges (outflow)** → Bank Fees · Interest Paid
- **Taxes (outflow)**
- **Unaccounted** system categories are reconciliation fallbacks, not normal user choices.

Transfers, investment buys/sells, opening balances, and revaluations are not everyday expense categories. A known partner can suggest a default category (e.g. Talabat → Food), but the partner and category remain separate records so one partner can be recategorized when appropriate.

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
| Category | Dotted tree path | `EXP.PERSONAL.FOOD`, `EXP.WORK.SOFTWARE`, `INC.INVEST.DIVIDEND` |
| Transaction reference | `TYPE-yyyy-mm-dd-NNN` | `OUT-2026-09-25-003` |
| Ledger line | `<transaction ref>/<line number>` | `TRF-2026-09-26-001/2` |

Account-type abbreviations: `CSH` cash wallet · `CUR` bank · `CD` certificate/time deposit · `BRK` brokerage · `PHY` physical asset · `OTH` other. `RCV` is legacy receivable terminology and should not be promoted as a core personal-finance workflow.

Financial-asset codes use prefixes such as `CASH`, `STK`, `FND`, `GLD`, and `OTH`. A ticker is used as the symbol when one exists; an app-generated symbol is not an exchange ticker.

## Product decisions and current implementation gaps

1. **UI shows names, not internal codes**, in ordinary navigation and forms. Codes stay available for technical details, search, and data exchange.
2. **Money from others is a distinct ownership concept**, not a receivable and not an income/expense category. The data model must eventually record owner + account + amount and subtract it from net worth. This section is a product requirement; the current schema does not yet implement it.
3. **Partners are intended to be selectable records**, optionally associated with a default category. The current transaction `counterparty` is still free text with past-entry suggestions; it is not yet a partner catalogue.
4. **Receivables are out of the core workflow** per the personal-finance scope. Legacy account/class definitions may remain until safely migrated, but they should not define the normal user's taxonomy.

## Transaction types

`OPN` opening · `IN` money in · `OUT` money out · `TRF` transfer · `CNV` conversion · `BUY` buy · `SEL` sell · `DIV` dividend · `VAL` valuation · `ADJ` reconciliation adjustment.
