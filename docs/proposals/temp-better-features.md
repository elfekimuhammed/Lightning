# Temp: better features from Actual Budget and GnuCash

**Status:** temporary proposal, 2026-10-05 · Claude. Nothing here is built. To build one section, say "build section 1.3", for example. When a section is built, move what holds into [Architecture](../ARCHITECTURE.md), delete the section here, and delete the file when it is empty.

**What was read:** `actualbudget/actual` at `6245a46` and `Gnucash/gnucash` at `53cc9e6`, against Lightning at `5665786`. [Competition › Actual Budget code analysis](../COMPETITION.md#actual-budget-code-analysis) lists *what* Actual does better; this file says *how* they do it and *what we change*.

**Each section has the same parts:** what they do better · how they do it, step by step, with their files · Lightning today, with our files · what to change, step by step · done when (the tests).

**Rules for every section:** figures come from Python services; nothing derived is stored; the ledger is the only truth; a change a user can see passes Mohab's test and guideline A16 before it ships; no setting is added that the screen does not need.

## Contents

| § | Section | From | Size | Needs |
|---|---|---|---|---|
| 1.1 | Category pre-filling | Actual | **Built** 2026-10-05: [Architecture › Default category for a counterparty](../ARCHITECTURE.md) | — |
| 1.2 | Rules with conditions and splits | Actual | Large | — |
| 1.3 | Undo for edits, deletes and imports | Actual | Medium | — |
| 1.4 | Finding the same transaction on import | Actual | **Owner decision** (one constant) | — |
| 1.5 | Locking a month checked against the bank | Actual | Small | — |
| 1.6 | Merging two transactions | Actual | Small | — |
| 1.7 | Due dates that know the Egyptian weekend | Actual | Small | — |
| 1.8 | Sums in amount fields | Actual | **Already built** (`core/money.py`, `tests/test_amount_sums.py`) | — |
| 2.1 | Cost per purchase (lots) | GnuCash | Medium | — |
| 2.2 | Bonus shares and stock splits | GnuCash | Medium | 2.1, 2.3 |
| 2.3 | One table of investment events | GnuCash | Medium | — |
| 2.4 | Investment checks in the integrity screen | GnuCash | Small | 2.1 |
| 2.5 | One order of price sources | GnuCash | Small | — |
| 2.6 | Return per purchase (ROI and CAGR) | GnuCash | Small | 2.1 |

**Suggested order:** 2.3 → 2.1 → 2.2 (bonus shares are common on the EGX and cannot be recorded honestly today), 1.5, 1.3, 2.4, 1.2, then the rest.

---

## 1. Actual Budget

### 1.2 Rules with conditions and splits

**They do better:** "if the counterparty contains Vodafone **and** the amount is between 100 and 300, file it under Phone; if it is above 300, split it 70% Phone, 30% Internet". Lightning can only say "Vodafone → Phone".

**How they do it** (`loot-core/src/server/rules/`, 1,824 lines):
1. **Three objects.** `Condition(field, op, value)` with `eval(txn)` (`condition.ts`); `Action(field, op, value, options)` with `exec(txn)` (`action.ts`); `Rule(stage, conditionsOp, conditions, actions)` (`rule.ts`).
2. **Ops.** is, is not, one of, contains, matches, between, **about** (±7.5% of the amount, `shared/rules.ts` `getApproxNumberThreshold`), greater/less than, has tag.
3. **Ranking** (`rule-utils.ts` `computeScore`). Each condition scores by op (is 10, one of 9, about and between 5, greater/less 1, contains 0); a rule whose conditions are all exact scores double. Rules run in stage order pre → default → post, most specific first.
4. **Index** (`rule-indexer.ts`). Rules are keyed by the lowercased payee (and by first character), so only a handful are tried per transaction; rules with no payee condition sit under `*`.
5. **Missing fields become null** before matching, so "payee is nothing" matches a row with no payee (`transaction-rules.ts` `runRules`, a bug they fixed).
6. **Splits** (`rule.ts` `execSplitActions`). Fixed amounts first, then percentages of what is left, then remainders shared equally; the last remainder takes the rounding difference so the parts always add up.
7. Rules run on import and on edit; saving a rule can apply it to past transactions.

**Lightning today:** a counterparty has one default category (`counterparties.default_category_id`); `ui/routes/budget.py` has a bulk apply with one undo. No conditions, no amounts, no splits by rule.

**What to change:**
1. Migration: `rules(id, stage, match_all, position, active)`, `rule_conditions(rule_id, field, op, value)`, `rule_actions(rule_id, field, op, value, split_index, split_method)`. Fields: counterparty, notes, amount, account, direction. Ops: is, contains, one of, between, about. Actions: set category, set counterparty, add tag, split.
2. `lightning/rules/engine.py`, pure functions over a dict, no database inside:
   ```python
   def rank(rules) -> list[Rule]                  # Actual's scores, then position
   def run(rules, txn: dict) -> dict              # the first matching rule sets each field
   def split(amount, actions) -> list[tuple[int, Decimal]]   # fixed, percent, remainder; parts add up
   ```
   and `RuleIndex = dict[str, set[Rule]]` on the lowercased counterparty, with `"*"` for the rest.
3. `lightning/rules/service.py`: create, edit, reorder, delete, and `preview(rule)` returning the past transactions it would change.
4. Hook points: `bank_imports._category_for` and the register's `_category_for_party` call `rules.run` first, then today's order ([Architecture › Default category for a counterparty](../ARCHITECTURE.md)). A counterparty's saved default is shown and stored as a generated `is` rule, so there is one mechanism, not two.
5. Screen: Settings › Rules, a list (header, then list, A16) and a form built from fields, never text typed into notes. Saving shows "This would change N past transactions" with apply-to-past, using one undo (1.3).

**Done when:** engine unit tests per op, ranking and split rounding (parts always add to the amount); an import test where a rule beats the usual category; Mohab adds a Vodafone rule with an amount range and his next import files both bills right.

### 1.3 Undo for edits, deletes and imports

**They do better:** any change can be undone, up to 20 steps back.

**How they do it** (`loot-core/src/server/undo.ts`):
1. Every write is a sync message that carries the **old value** (`appendMessages(messages, oldData)`).
2. `withUndo` puts a **marker** in the history; everything written until the next marker is one step.
3. Undo replays the old values of the last step; redo replays the new ones. 20 markers are kept (`HISTORY_SIZE`).
4. Screens wrap each user action in `undoable(...)`; background work does not.

**Lightning today:** no message layer. Every write goes through `Database.transaction()` (`database/connection.py` line 107). Undo exists only for the budget bulk rule (`ui/routes/budget.py` lines 665–698, a snapshot in a setting) and a skipped payment. A voided or deleted transaction can be restored, but an **edit or an import cannot be undone**.

**What to change:**
1. Migration: `undo_groups(id, label, created_at)` and `undo_log(group_id, seq, sql, params_json)`.
2. For each user-data table (transactions, ledger entries, budgets, planned items, categories, counterparties, rules), triggers `AFTER INSERT/UPDATE/DELETE` write the **inverse** statement into `undo_log`, under the current group read from a one-row `TEMP` table. With no current group they write nothing.
3. `Database.transaction(undo_label=None)`: at depth 0 with a label, open a group and set the temp row; clear it at commit or rollback. Migrations, price downloads and system revaluations pass no label, so they never enter the history.
4. `lightning/undo.py` `UndoService`: `undo()` runs the last group's inverse statements newest first in one transaction, then runs the integrity checks and refuses (rolls back) if one fails. Keep 20 groups. Clear the log when the profile closes and before a phone hand-off (the multi-device plan must not carry it).
5. Screens: the message after save, delete or import gets an **Undo** button. Move the budget bulk undo onto this service.
6. A test that lists every user-data table and fails if one lacks its three triggers.

**Done when:** tests undo an edit, a delete, an import of 30 rows and a bulk change, each leaving the database byte-for-byte equal in content to before; undo after a migration is refused. Mohab imports the wrong file and undoes it in one click.

### 1.4 Finding the same transaction on import

**They do better:** a payment the bank posts up to a week after the user typed it is still offered as the same transaction.

**How they do it** (`loot-core/src/server/accounts/sync.ts`, `matchTransactions`, line 826):
1. A row with the same bank id matches first.
2. Otherwise, candidates are rows in the same account with the **same amount within 7 days either side** (line 895).
3. Ranked by date distance, then rows **without** a bank id first, because those were typed by hand (`compareFuzzyMatchCandidates`, line 804).

**Lightning today:** already the same shape, with a narrower window: `bank_imports.py` `_link_candidates` offers entries with the same amount within `LINK_WINDOW_DAYS = 3`, closest first, never one already backed by an imported row, and never one entry to two rows ([Architecture › CSV import and export contract](../ARCHITECTURE.md)).

**What to change:** only `LINK_WINDOW_DAYS`, from 3 to 7, and the window test (`tests/test_bank_import_matching.py`, "within three days"). **The owner decides:** 7 catches slow card postings; but a weekly payment of the same amount (a café, a class) would then be offered last week's entry when this week's was not typed, and a row with a candidate defaults to *Link*. 3 avoids that.

**Done when:** the window test moves to the new number, and a test shows a weekly equal payment still posts as new when its own entry was not typed.

### 1.5 Locking a month checked against the bank

**They do better:** once a row is reconciled, nothing changes it by accident, not even an import.

**How they do it:** a reconciled row has `reconciled = 1`; matching skips updating it (`sync.ts` line 673); the screens ask before editing it.

**Lightning today:** `reconciliation.py` checks a balance (`check`, line 57) and can post an adjustment (`adjust`), but nothing stops a later edit of a checked month.

**What to change:**
1. Migration: `reconciled_through(account_id PRIMARY KEY, date)`.
2. When `check(...).matches` and the user confirms, store the date.
3. `TransactionService.update`, `void` and `delete_many` refuse a line on that account dated on or before it: "This month was checked against the bank. Unlock it first." Import rows on or before it are marked skipped.
4. One **Unlock** link on the account page clears it.

**Done when:** tests: edit, void, delete and import are refused on or before the date, allowed after it and after unlocking.

### 1.6 Merging two transactions

**They do better:** two rows that are the same payment become one, keeping the best of each.

**How they do it** (`loot-core/src/server/transactions/merge.ts`):
1. Keep the row with the bank id.
2. Copy payee, category and notes from the other row where the kept row is empty.
3. Delete the other row; a transfer stays linked.

**Lightning today:** none; the user voids one by hand and loses its category or notes.

**What to change:** `TransactionService.merge(keep_id, drop_id)` in one transaction (one undo step with 1.3): refuse if amounts or accounts differ; keep the one with `bank_reference`; copy category, notes, tags and counterparty where empty; void the other with reason "Merged into REF". A "Merge" action when exactly two rows are selected in the register.

**Done when:** a test merges a typed and an imported row and the kept row has the bank reference and the typed category.

### 1.7 Due dates that know the Egyptian weekend

**They do better:** a bill due on a weekend moves to the working day before or after.

**How they do it** (`loot-core/src/shared/schedules.ts`): each schedule has `skipWeekend` and `weekendSolve: before | after`; `getDateWithSkippedWeekend` (line 340) moves the date. But it uses date-fns `isWeekend`, **Saturday and Sunday**, which is wrong for Egypt.

**Lightning today:** `planning/schedule.py` `payment_dates` has no weekend handling. Amount tolerance already exists (`planning/service.py` `MATCH_TOLERANCE`, `DEFAULT_TOLERANCE`), so nothing to add there.

**What to change:**
1. `WEEKEND = {4, 5}` (Friday, Saturday in `date.weekday()`) in `planning/schedule.py`.
2. Planned items gain `weekend_move` (`none`, `before`, `after`); default `before` for salary (Egyptian payroll pays before the weekend) and `none` for the rest, so existing plans do not move.
3. `payment_dates` applies it after computing each date.
4. Later, optional: a dated public-holiday list shipped in the market data pack and applied the same way.

**Done when:** tests: a salary due Friday falls on Thursday; a bill set to `after` due Friday falls on Sunday; `none` does not move.

---

## 2. GnuCash

### 2.1 Cost per purchase (lots)

**They do better:** each purchase keeps its own cost and date, so a sale shows which purchases it used up, the gain on each and how long each was held.

**How they do it** (`libgnucash/engine/`):
1. Every buy opens a **lot** (`gnc-lot.cpp`).
2. A **policy** object picks the lot a sale comes from (`policy.cpp`): FIFO (oldest first), LIFO (newest first), average, or manual.
3. A sale bigger than the lot it hits is **cut into two pieces**, one that closes the lot and one carried to the next (`cap-gains.cpp` `xaccSplitAssignToLot`, line 219).
4. Each piece gets its own realized gain (`xaccSplitComputeCapGains`).
5. Lots are **stored**, so a back-dated edit leaves them stale; a "gains dirty" flag and scrubbers (`Scrub3.cpp`) repair them, and their own comment warns of "a potential trickle-through effect on all later lots".

**Lightning today:** `investments/service.py` `portfolio()` (lines 337–410) replays every investment line and keeps **one average-cost pool** per account, asset and owner. Right for funds and what Egyptian brokers show, but no per-purchase cost, gain or holding period.

**What to change** (derive lots, never store them, so there is nothing to scrub):
1. New pure module `lightning/investments/lots.py`:
   ```python
   @dataclass
   class Lot:          # one purchase, or what is left of it
       opened: str; quantity: Decimal; cost: Decimal; owner_id: int | None
   @dataclass
   class Disposal:     # one piece of a sale against one lot
       lot_opened: str; sold: str; quantity: Decimal; cost: Decimal; proceeds: Decimal
       gain = property(lambda self: self.proceeds - self.cost)
       days_held = property(...)
   def build_lots(lines, method="average") -> tuple[list[Lot], list[Disposal]]
   ```
2. `average` is one lot that absorbs every buy: exactly today's numbers. `fifo` takes from the oldest open lot and cuts a sale across lots; proceeds are shared by quantity and the last piece takes the rounding remainder so the pieces add up to the sale.
3. `portfolio()`'s inline pool loop (lines 360–375) becomes a call to `build_lots`. `Position` gains `lots` and `disposals`; `cost_basis` and `realized` become sums over them.
4. Migration: `accounts.cost_method TEXT NOT NULL DEFAULT 'average'`, shown on the account edit page for brokerage accounts only.
5. Later, only if asked: choose the exact purchases a sale uses (GnuCash "manual"), as `sale_lot_picks(transaction_id, lot_opened, quantity)` read by `build_lots`.

**Done when:** with `average`, every existing investment test and Mohab's test give the same numbers (the refactor guard); new tests for FIFO across three buys and a sale that spans two lots; the pieces always add up to the sale.

### 2.2 Bonus shares and stock splits

**They do better:** a split or bonus issue is its own event: units change, cost does not, and no fake purchase appears.

**How they do it:**
1. Split and reverse split are types in the stock assistant (`gnucash/gnome/assistant-stock-transaction.cpp`, line 273).
2. The user types the **new number of units**, not a ratio (`FieldMask::INPUT_NEW_BALANCE`).
3. When balances are recomputed, every earlier quantity is rescaled by `new balance / old balance` into an `adjusted_amount`; cost is left alone (`Account.cpp` around line 2285).
4. Cash for fractions is recorded as a sale **first**, then the split (the assistant's own instruction).

**Lightning today:** EGX companies often give bonus shares (أسهم مجانية). The only way is a buy at price 0, which shows as a purchase in the list and adds a false flow to XIRR.

**What to change:**
1. `DocType.SPL = "SPL"` ("Bonus or split") in `core/refs.py`: one units line, `amount_base_e6 = 0`, no cash line, no category, no effect on spending or income.
2. `build_lots` (2.1): on an SPL line, `ratio = (held + q) / held`; multiply every open lot's quantity by it, keep cost.
3. XIRR skips it (no money moved).
4. The price chart divides prices before the split date by the cumulative ratio when it builds the series (Python), so the line does not fall off a cliff. Stored prices stay as they are.
5. Form: "Units you hold after" (prefilled with today's holding), date, notes. Built as an event in 2.3.

**Done when:** tests: 100 units at 10, a 1-for-4 bonus, 125 units, cost unchanged, average cost 8; a reverse split; a sale after the split gives the right gain; XIRR unchanged by the split.

### 2.3 One table of investment events

**They do better:** adding an event type is one row in a table, not a new code path.

**How they do it** (`assistant-stock-transaction.cpp`):
1. Each event is one `TxnTypeInfo` row: for units, cash, fees, dividend and gains, a `FieldMask` says enabled or not, which direction, whether zero is allowed, and whether fees are added to cost.
2. **One** validator (`check_page`) and **one** journal builder read the table.
3. A review page shows the balanced journal before posting.
4. The table holds buy, sell, dividend, return of capital, notional distribution, split, reverse split and the short-side versions.

**Lightning today:** `investments/service.py` `_trade_lines` and `_dividend_lines` are separate branches; reinvested dividends, return of capital and bonus shares this way would triple them.

**What to change:**
1. `lightning/investments/events.py`:
   ```python
   @dataclass(frozen=True)
   class EventSpec:
       doc_type: DocType
       units: Sign            # IN, OUT, NONE, NEW_BALANCE
       cash: Sign             # IN, OUT, NONE
       fees: str              # "cost", "proceeds", "none"
       income_category: str | None
       lowers_cost: bool = False

   EVENTS = {
       "buy": EventSpec(DocType.BUY, Sign.IN, Sign.OUT, "cost", None),
       "sell": EventSpec(DocType.SEL, Sign.OUT, Sign.IN, "proceeds", None),
       "dividend": EventSpec(DocType.DIV, Sign.NONE, Sign.IN, "none", DIVIDEND_CATEGORY),
       "reinvested_dividend": ...,   # income, then units at that price, in one document
       "return_of_capital": EventSpec(DocType.SEL, Sign.NONE, Sign.IN, "none", None, lowers_cost=True),
       "bonus": EventSpec(DocType.SPL, Sign.NEW_BALANCE, Sign.NONE, "none", None),
   }
   def lines_for(event, values) -> list[PostingLine]   # the only builder
   def validate(event, values) -> None                  # the only validator
   ```
2. `buy()`, `sell()`, `dividend()` stay as thin wrappers, so routes and tests do not change.
3. The investment entry form shows only the fields the spec enables; the route passes the spec, and the template only reads it.
4. Return of capital lowers open lots' cost by quantity share; any excess over cost is a gain.

**Done when:** every existing investment test passes unchanged; new tests for reinvested dividend and return of capital.

### 2.4 Investment checks in the integrity screen

**They do better:** a report tab that finds broken investment records.

**How they do it** (`gnucash/report/reports/standard/investment-lots.scm`, Validation tab): it flags lots with a negative balance, lots with more than one purchase, sales not assigned to a lot, and gains that do not match.

**Lightning today:** `integrity.py` checks balances, budgets and the net-worth bridge; nothing about holdings. `_check_holdings` guards new posts and voids, but not every back-dated edit path.

**What to change:** in `IntegrityService.checks()` add:
1. *Lots add up:* per position, sum of lot cost = `cost_basis`, sum of lot quantity = `quantity`.
2. *Never sold what was not held:* replay each holding by date and flag the first day its quantity goes below zero.
3. *Sales add up:* sum of disposal gains = `realized`.

**Done when:** tests break each rule on purpose with direct SQL and the check reports it; Mohab's year passes all three.

### 2.5 One order of price sources

**They do better:** when two prices exist for one day, which one wins is a single written rule.

**How they do it** (`libgnucash/engine/gnc-pricedb.h`, line 166): every price has a source from a ranked list (editor, online quote, user, transfer, register, import, split, transaction…); a higher source overwrites a lower one that day, never the reverse.

**Lightning today:** `price_history` is unique on `(asset_id, date, source)`, so one day can hold several prices; `reporting/valuation.py` chooses by its own branches (manual value, then reference).

**What to change:** one `SOURCE_RANK` tuple in `reporting/valuation.py` (manual, then trade, then the market pack's sources, then cost) used by every lookup, replacing the branch order.

**Done when:** tests: a manual price beats the pack's price that day; the pack's later price beats an older manual one; a trade price counts for its own day.

### 2.6 Return per purchase (ROI and CAGR)

**They do better:** per purchase, how much it made (ROI) and how fast per year (CAGR), split into sold and still held.

**How they do it** (`investment-lots.scm`): `ROI = gain / basis`; `CAGR = (end value / basis)^(1 / years) − 1`, for realized and unrealized parts.

**Lightning today:** XIRR per holding and for the portfolio (`investments/xirr.py`). Better than GnuCash for money added over time, but nothing per purchase.

**What to change:** after 2.1, add `roi` and `cagr` properties to `Lot` and `Disposal`, shown on lot rows only. XIRR stays the headline. Add both terms to the Glossary.

**Done when:** tests: a single purchase's CAGR equals its XIRR; ROI and CAGR are None for less than a day held or zero basis.

---

## Not worth copying

- **From GnuCash:** stored lots with scrubbers (derive them instead, 2.1), short selling, accounting words (debit, credit, split) on screens, report option pages.
- **From Actual:** see [Competition › What not to copy](../COMPETITION.md#what-not-to-copy).
