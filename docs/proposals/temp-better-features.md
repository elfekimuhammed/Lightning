# Temp: better features from GnuCash and Actual (code level)

**Status:** temporary proposal, 2026-10-05 · Claude. Not built. When an item is built, move what holds into [Architecture](../ARCHITECTURE.md) and delete it here; delete the file when it is empty.

**What was read:** `Gnucash/gnucash` at `53cc9e6` (engine lots, cost policies, capital gains, stock splits, price database, the stock transaction assistant, the Investment Lots and Advanced Portfolio reports) and `actualbudget/actual` at `6245a46` (rules, undo, import match, schedules). Lightning was read at `5665786`. [Competition › Actual Budget code analysis](../COMPETITION.md#actual-budget-code-analysis) already lists *what* Actual does better; this file says *how* we would build it in our code, and adds GnuCash, which that section does not cover.

**Rules that hold for every item:** figures come from Python services, nothing derived is stored, the ledger is the only truth, Mohab's test covers each item before it ships, and no screen gains a setting it does not need.

---

## Part A — GnuCash: investment correctness

Lightning today ([`investments/service.py` `portfolio()`](../../lightning/investments/service.py)) replays every investment line and keeps **one average-cost pool per (account, asset, owner)**. That is right for THNDR-style funds, and the XIRR is better than anything GnuCash shows. What GnuCash has and we do not:

### A1. Lots, as a derived structure

**GnuCash:** every buy opens a *lot*; a sale is assigned to lots by a policy object (`engine/policy.cpp`: FIFO, LIFO, average, manual), and a sale bigger than the lot it hits is **cut into two pieces**, one that closes the lot and one for the next lot (`cap-gains.cpp` `xaccSplitAssignToLot`). Each closed piece carries its own realized gain and its own holding period. GnuCash *stores* lots and then needs scrubbers (`Scrub3.cpp`) and a "gains dirty" flag to repair them after a back-dated edit (its own comment: "a potential trickle-through effect on all later lots").

**Lightning, better:** derive lots, never store them, so there is nothing to scrub.

- New pure module `lightning/investments/lots.py`:
  ```python
  @dataclass
  class Lot:            # one purchase, or what is left of it
      opened: str; quantity: Decimal; cost: Decimal; owner_id: int | None
  @dataclass
  class Disposal:       # one piece of a sale against one lot
      lot_opened: str; sold: str; quantity: Decimal; cost: Decimal; proceeds: Decimal
      @property
      def gain(self): return self.proceeds - self.cost
      @property
      def days_held(self): ...
  def build_lots(lines, method: str = "average") -> tuple[list[Lot], list[Disposal]]
  ```
- `average` is one lot that absorbs every buy: exactly today's numbers, so `portfolio()` keeps its results and Mohab's test must not move. `fifo` takes from the oldest open lot and cuts the sale across lots (proceeds shared pro rata to quantity, the last piece takes the rounding remainder so the pieces add up to the sale).
- `portfolio()` lines 360–375 (the inline pool loop) become a call to `build_lots`; `Position` gains `lots` and `disposals`, and `cost_basis` / `realized` become sums over them.
- The method is one column on the brokerage account (`cost_method TEXT NOT NULL DEFAULT 'average'`), shown on the account edit page only for brokerage accounts. Average stays the default: it is what Egyptian brokers (THNDR, EFG Hermes) show.
- Later, only if asked: a *specific lot* choice on a sale (GnuCash "manual") as a table `sale_lot_picks(transaction_id, lot_opened, quantity)` read by `build_lots`.

**What the user gets:** "held 1 year 3 months", gain per purchase, and a sell screen that can say which purchases a sale uses up.

### A2. Stock splits and bonus shares

EGX companies often give **bonus shares** (أسهم مجانية). Today the user can only record them as a buy at price 0, which drags the average cost the right way but shows as a purchase, breaks XIRR flows and is a lie in the list.

**GnuCash:** a split is its own transaction type; the user types the **new number of units**, not a ratio (`assistant-stock-transaction.cpp`, `FieldMask::INPUT_NEW_BALANCE`). The account then rescales every earlier split's quantity by `new_balance / old_balance` into an `adjusted_amount` (`Account.cpp` around line 2285), cost unchanged. Cash in lieu of fractions is recorded as a sale *first*.

**Lightning:**
- New `DocType.SPL = "SPL"` ("Bonus or split") in `core/refs.py`: one units line, quantity = units received (or removed in a reverse split), `amount_base_e6 = 0`, no cash line, no category, no effect on spending or income.
- `build_lots`: on an `SPL` line, `ratio = (held + q) / held`; multiply every open lot's quantity by `ratio`, keep cost. Average cost per unit falls; value and cost do not jump.
- XIRR ignores it (no money moved), which is right.
- Price history before the split date stays as stored; the price chart divides earlier prices by the cumulative ratio when it draws (in Python, in the series builder), so the line does not drop off a cliff.
- Form: "Units you hold after" (prefilled with today's holding), date, notes. One field, the same as GnuCash's choice, because users read the new number off their broker, not a ratio.

### A3. One table of investment events, not one branch per kind

**GnuCash:** every stock event is one row in a table (`TxnTypeInfo`): for each of units, cash, fees, dividend and gains a `FieldMask` says enabled or not, debit or credit, may be zero, fees added to cost by default. **One** validator (`check_page`) and **one** journal builder read the table, and a review page shows the balanced journal before posting. The table holds Buy, Sell, Dividend, Return of capital, Notional distribution, Stock split, Reverse split, and the short-side versions.

**Lightning today:** `_trade_lines` and `_dividend_lines` are separate branches; adding bonus shares, reinvested dividends and return of capital this way would triple them.

**Lightning:** `lightning/investments/events.py`:
```python
@dataclass(frozen=True)
class EventSpec:
    doc_type: DocType
    units: Sign          # IN, OUT, NONE, NEW_BALANCE
    cash: Sign           # IN, OUT, NONE
    fees: str            # "cost" (added to cost), "proceeds" (taken from them), "none"
    income_category: str | None   # DIVIDEND_CATEGORY for dividends
    lowers_cost: bool = False     # return of capital

EVENTS = {
    "buy": EventSpec(DocType.BUY, Sign.IN, Sign.OUT, "cost", None),
    "sell": EventSpec(DocType.SEL, Sign.OUT, Sign.IN, "proceeds", None),
    "dividend": EventSpec(DocType.DIV, Sign.NONE, Sign.IN, "none", DIVIDEND_CATEGORY),
    "reinvested_dividend": ...,   # DIV and BUY in one document: income, then units at that price
    "return_of_capital": EventSpec(DocType.SEL, Sign.NONE, Sign.IN, "none", None, lowers_cost=True),
    "bonus": EventSpec(DocType.SPL, Sign.NEW_BALANCE, Sign.NONE, "none", None),
}
def lines_for(event: str, values: dict) -> list[PostingLine]   # the only builder
def validate(event: str, values: dict) -> None                   # the only validator
```
`buy()`, `sell()`, `dividend()` stay as thin wrappers so routes and tests do not change. The entry form shows only the fields the spec enables (the template reads the spec passed by the route, no logic in the template). Return of capital lowers the open lots' cost pro rata in `build_lots` and records no gain unless cost would go below zero (the excess is a gain).

### A4. Investment checks in the integrity screen

**GnuCash:** the Investment Lots report has a *Validation* tab: lots with a negative balance, lots with more than one purchase, sales not assigned to a lot, gains that do not match.

**Lightning:** [`integrity.py`](../../lightning/integrity.py) checks balances, budgets and the net-worth bridge, nothing about holdings. Add to `IntegrityService.checks()`:
- *Lots add up:* for each position, sum of lot cost = `cost_basis`, sum of lot quantity = `quantity`.
- *Never sold what was not held:* replay each holding by date and flag the first day its quantity goes below zero. `_check_holdings` guards new posts and voids, but a back-dated **edit** of an earlier buy's quantity is the case GnuCash warns about; this check proves it cannot slip through.
- *Disposals add up:* sum of disposal gains = `realized`.

### A5. Price source priority

**GnuCash:** each price has a source from a ranked enum (`gnc-pricedb.h`: editor, online quote, user, transfer dialog, register, import, stock split, transaction…); a higher-ranked source overwrites a lower one on the same day and never the reverse.

**Lightning:** `price_history` is `UNIQUE(asset_id, date, source)`, so two sources can hold a price for one day, and `reporting/valuation.py` decides by its own order (manual value, then reference). Write that order down as one ranked list in `valuation.py` (`SOURCE_RANK = ("MANUAL", "TRADE", <market pack sources>, "COST")`) used by every lookup, and test it: a manual price on a day always beats the downloaded pack's price that day; a trade price beats the pack for that day only.

### A6. ROI and CAGR beside XIRR

**GnuCash:** per lot, `ROI = gain / basis` and `CAGR = (end / basis)^(1/years) − 1`, split into realized and unrealized (`investment-lots.scm` `calculate-cagr`, `calculate-roi`).

**Lightning:** keep XIRR as the headline (it is money-weighted and right when buys are spread out, which GnuCash does not show). Per lot, add CAGR only once A1 exists; for a single purchase it equals XIRR, so show it on the lot rows, not as a second headline figure. Add both terms to the Glossary when built.

---

## Part B — Actual: how to build what Competition lists

### B1. Rules with conditions (Competition #1)

**Actual's code shape** (`server/rules/`): `Condition(op, field, value)` with `eval(txn)`, `Action(op, field, value, options)` with `exec(txn)`, `Rule(stage, conditionsOp, conditions, actions)`. Rules are **ranked**: each condition op has a score (`is` 10, `oneOf` 9, `isapprox`/`isbetween` 5, `gt` 1, `contains` 0), doubled when every condition is exact (`rule-utils.ts` `computeScore`), so specific rules run first; then stage order pre → default → post. A `RuleIndexer` keys rules by the lowercased payee (and first character) so only a few rules are tried per transaction. Before evaluating, missing fields are set to `null` so a "payee is nothing" rule still matches (a bug they hit).

**Lightning:**
- Migration: `rules(id, stage, match_all, position, active)`, `rule_conditions(rule_id, field, op, value)`, `rule_actions(rule_id, field, op, value, split_index, split_method)`. Fields: counterparty, notes, amount, account, direction. Ops: is, contains, one of, between, about (±7.5%, Actual's `getApproxNumberThreshold`). Actions: set category, set counterparty, add tag, split.
- `lightning/rules/engine.py`, pure functions over a dict, no database inside (easy to test):
  ```python
  def rank(rules) -> list[Rule]                      # Actual's score, then position
  def run(rules, txn: dict) -> dict                  # first match per field wins, like Actual
  def split(amount, actions) -> list[(category_id, amount)]
      # fixed amounts first, then percent of what is left, then remainders;
      # the last remainder takes the rounding difference, so the parts always add up
  ```
  plus `RuleIndex` = `dict[str, set[Rule]]` on lowercased counterparty, with `"*"` for the rest.
- Hook points: `bank_imports._category_for` (line 430) calls `rules.run` first, then today's fallbacks (CSV category, counterparty default, usual category). A counterparty's default category becomes a generated `is` rule, so there is one mechanism.
- **Tighten "usual category":** `TransactionService.usual_categories` (line 344) treats a single past choice as usual; Actual suggests only after the same category was picked **3 times** for that payee (`transaction-rules.ts` line 949). Require `count >= 2` and a clear majority before an import pre-fills it, so one odd filing does not spread.
- Saving a rule shows "This would change N past transactions" with an apply-to-past checkbox, using the existing bulk-apply with one undo.

### B2. Undo for edits and imports (Competition #2)

**Actual's code shape** (`server/undo.ts`): every write is a sync message carrying the old value; `withUndo` drops a marker, everything written until the next marker is one step; undo replays the old values; 20 steps kept.

**Lightning has no message layer**, but it has one door for writes (`Database.transaction()`, depth 0) and an audit trail. Build it in SQLite:
- Migration: `undo_log(group_id, seq, sql, params_json)` and `undo_groups(id, label, created_at)`.
- Triggers `AFTER INSERT/UPDATE/DELETE` on the user-data tables (transactions, ledger entries, budgets, planned items, rules, categories, counterparties) write the **inverse** statement into `undo_log` with the current group from a one-row `TEMP` table.
- `Database.transaction()` at depth 0 takes an optional `undo_label`; with a label it opens a group, without one it writes nothing (migrations, price downloads and system revaluations stay out).
- `UndoService.undo()` runs the last group's inverse statements in reverse order inside one transaction, then the integrity checks; keeps 20 groups; cleared when the profile closes and before a phone hand-off (the multi-device plan must not ship an undo log).
- Screens: the flash message after save, delete or import gets an **Undo** button (the budget bulk undo in `ui/routes/budget.py` already shows the pattern; it then moves onto this service).
- A generator test checks every user-data table has its three triggers, so a new table cannot be forgotten.

### B3. Import match and a locked checked month (Competition #3)

**Actual** (`accounts/sync.ts`): a bank id match first; then candidates with the **same amount within 7 days either side**, nearest date first, a row without a bank id preferred on a tie (`compareFuzzyMatchCandidates`); **reconciled rows are never updated** (line 673).

**Lightning today:** `_similarity_warning` (`bank_imports.py` line 442) only flags the **same date and same amount**, so a card purchase posted a day late by the bank is imported twice.

- Replace it with `_match_candidates(account_id, parsed)` returning ranked rows: same amount, `date ± 7 days`, ordered by date distance, then rows without a `bank_reference` first. The review screen pre-selects "link to existing" for the top candidate instead of only warning.
- When a balance check matches (`reconciliation.check(...).matches`), store `reconciled_through(account_id, date)`. `TransactionService.update/void/delete_many` refuse lines on that account on or before that date with "This month was checked against the bank. Unlock it first." Imports skip those dates. One "Unlock" link on the account page clears it.
- **Merge two transactions** (`transactions/merge.ts`): keep the imported one (it has the bank reference), copy category, notes and tags from the hand-typed one if the imported one has none, void the other, one undo group.

### B4. Schedules that know the Egyptian weekend (Competition #4)

**Actual:** `getDateWithSkippedWeekend` moves a date before or after a weekend, but its weekend is date-fns `isWeekend`, **Saturday and Sunday**: wrong for Egypt.

**Lightning** (`planning/schedule.py` `payment_dates`): add per planned item `weekend_move` (`none`, `before`, `after`, default `before` for salary, `after` for bills) and one constant `WEEKEND = {4, 5}` (Friday, Saturday in `date.weekday()`). Optional later: a dated public-holiday list as data (in the market data pack), applied the same way. Amount tolerance already exists (`MATCH_TOLERANCE`, `DEFAULT_TOLERANCE`), so nothing to add there.

### B5. Arithmetic in amount fields (Competition #7)

**Actual** (`shared/arithmetic.ts`): a small recursive-descent parser for `+ - * / ( )`, no `eval`.

**Lightning:** `lightning/core/arithmetic.py` with the same grammar over `Decimal`, Arabic-Indic digits accepted (reuse the existing digit mapping). `to_decimal` calls it when the text contains an operator, so every amount field gains it at once and the result is still checked for places by `check_places`. The field shows the result after leaving it. Calculations stay in Python, as the product rule requires.

---

## Not worth copying

From GnuCash: stored lots with scrubbers (derive them instead), short selling, accounting words (debit, credit, split) on screens, report options pages. From Actual: see [Competition › What not to copy](../COMPETITION.md#what-not-to-copy).

## Suggested order

1. **A1 lots** with `average` reproducing today's numbers exactly (a refactor with Mohab's test as the guard), then **A4 checks**.
2. **A2 bonus shares**, built on **A3 events**: the most common EGX event we cannot record honestly.
3. **B3 import match** (±7 days) and the **reconciled lock**: double imports are a trust bug today.
4. **B2 undo** through triggers.
5. **B1 rules**, then **B4 weekend** and **B5 arithmetic**.
6. **A5, A6** when the investment screens are next touched.
