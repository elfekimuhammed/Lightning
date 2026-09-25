# Glossary and naming standard

The same words are used in the code, the database and the screens.

| Term | Meaning | Example |
|---|---|---|
| **Account** | A place where money or assets are held | CIB Current, THNDR, Wallet |
| **Financial asset** | A specific thing you own a quantity of | EGP cash, COMI shares, 21K gold (grams) |
| **Asset class** | A group of financial assets (editable tree) | Funds › Gold Fund |
| **Holding** | How much of one asset one account holds — always calculated | THNDR holds 100 COMI |
| **Category** | Why money came in or went out (editable tree) | Personal › Food |
| **Transaction** | What happened — the document you see | `OUT-2026-09-25-003` |
| **Ledger line** | One effect of a transaction on one account and asset | `OUT-2026-09-25-003/1` |
| **Money in** (inflow) | Value entering your finances | Salary, interest |
| **Money out** (outflow) | Value leaving your finances | Groceries, fees, tax |
| **Transfer** | Money moving between your own accounts; net worth unchanged | CIB → THNDR |
| **Conversion** | One asset swapped for another inside your finances (M3/M4) | Cash → shares, EGP → USD |
| **Revaluation** | A value change with no money moving (M3/M4) | Share price up |
| **Opening balance** | What an account held when tracking started | `OPN-2026-09-01-001` |
| **New balances added** | Opening balances of accounts started during a period | |
| **Net worth** | Everything you own (Lightning does not track debts) | |
| **Register** | An account page: its transactions with an entry row on top | Payee · Category · Payment · Deposit |
| **Receivable** | Money owed to you | Pending reimbursement (M5) |
| **Cost basis** | What you paid for a holding, including fees (M3) | |
| **Void** | Cancelled: kept for history, excluded from balances | |

## Codes

| Kind | Pattern | Examples |
|---|---|---|
| Account | `INSTITUTION-TYPE-CURRENCY` | `CIB-CUR-EGP`, `QNB-CUR-EGP`, `CIB-CD-EGP`, `THNDR-BRK-EGP`, `WALLET-CSH-EGP` |
| Financial asset | `CLASS:SYMBOL` | `CASH:EGP`, `STK:COMI`, `FND:AZ-GOLD`, `GLD:21K` |
| Asset class | dotted path | `CASH.BANK`, `DEPOSIT.CD`, `FUND.GOLD` |
| Category | dotted path | `EXP.PERSONAL.FOOD`, `EXP.WORK.SOFTWARE`, `INC.INVEST.DIVIDEND` |
| Transaction ref | `TYPE-yyyy-mm-dd-NNN` | `OUT-2026-09-25-003` (never changes) |
| Ledger line | `<ref>/<line>` | `TRF-2026-09-26-001/2` |
| Backup file | `lightning_yyyy-mm-dd_HHMM.db` | `lightning_2026-09-25_1600.db` |

Account type abbreviations: CSH wallet · CUR bank (current or savings) · CD certificate / time deposit ·
BRK brokerage · RCV owed to me · OTH other · PHY physical asset (from M3).

Screens show plain names for categories and asset classes ("Personal › Food & Groceries");
codes are used in search, ledger detail, exports and the database.

Transaction types: `OPN` opening · `IN` money in · `OUT` money out · `TRF` transfer · `CNV` conversion ·
`BUY` · `SEL` · `DIV` dividend · `VAL` valuation · `ADJ` reconciliation adjustment.

Account codes always appear with their names: **`CIB-CUR-EGP · CIB Current`**, never a bare code.
