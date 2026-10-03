"""Traceable, owner-scoped investment report derived from posted ledger entries."""
from collections import defaultdict
from decimal import Decimal

from lightning.accounts.domain import INVESTMENT_ACCOUNT_TYPES
from lightning.core.memo import request_cached
from lightning.core.money import ZERO, from_e6


def investment_period(db, accounts, assets, reporting, start: str, end: str):
    """The investment report for a period, with its Result.

    Change in unrealized gain = Unrealized gain at the end − Unrealized gain the day before the start.
    Result = Realized gain + Change in unrealized gain + Dividends and interest (None if a price is missing).
    """
    from datetime import date, timedelta
    closing = build_investment_report(db, accounts, assets, reporting, start, end)
    before = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    opening = build_investment_report(db, accounts, assets, reporting, start, before)
    change = (None if closing["unrealized"] is None or opening["unrealized"] is None
              else closing["unrealized"] - opening["unrealized"])
    closing["unrealized_change"] = change
    closing["result"] = None if change is None else closing["realized"] + change + closing["dividends"]
    closing["opening"] = opening
    return closing


def period_growth(result: Decimal | None, opening_value: Decimal | None, money_added: Decimal) -> Decimal | None:
    """Growth = Net gain or loss ÷ (Portfolio value at the start + Money added), as a percentage.
    None when the result is unavailable or nothing was invested."""
    if result is None or opening_value is None:
        return None
    base = opening_value + money_added
    return result / base * 100 if base > ZERO else None


def investing_rate(money_added: Decimal, money_in: Decimal, net_flow: Decimal | None = None) -> Decimal | None:
    """Investing rate = Money added ÷ Money in, as a percentage; None without money in.

    What you invest is part of what you saved (money in − money out − saved = 0), so with ``net_flow``
    the amount counted is at most this period's net flow: money taken from earlier savings is not
    this period's investing, and the investing rate never exceeds the savings rate."""
    if money_in <= ZERO:
        return None
    invested = money_added if net_flow is None else min(money_added, max(net_flow, ZERO))
    return max(invested, ZERO) / money_in * 100


def saved_and_invested(flow, money_added: Decimal) -> dict:
    """Money in split three ways for one period: invested (inside saved), the rest of saved, spent.

    Savings rate = Net flow ÷ Money in; Investing rate = Money added ÷ Money in, at most the saved part.
    Returns the rates, the amounts, and 100 squares read row by row (invested, kept, spent)."""
    inflow = flow.inflows
    kept = max(flow.net, ZERO)
    put_in = min(max(money_added, ZERO), kept)
    share = (lambda v: float(v / inflow * 100)) if inflow > 0 else (lambda v: 0.0)
    bar = {"invested": share(put_in), "saved": share(kept - put_in), "spent": share(min(flow.outflows, inflow)),
           "invested_amount": put_in, "kept": kept, "spent_amount": flow.outflows,
           "earlier": max(money_added - kept, ZERO)}
    invest_cells = round(bar["invested"]) if inflow > 0 else 0
    saved_cells = min(round(bar["invested"] + bar["saved"]), 100) if inflow > 0 else 0
    spent_cells = min(saved_cells + round(bar["spent"]), 100)
    bar["cells"] = (["invested"] * invest_cells + ["kept"] * (saved_cells - invest_cells)
                    + ["spent"] * (spent_cells - saved_cells) + [""] * (100 - spent_cells))
    return {"saved": flow.savings_rate, "invested": investing_rate(money_added, inflow, flow.net),
            "saved_cells": saved_cells, "invest_cells": invest_cells, "bar": bar,
            "money_in": inflow, "net": flow.net, "money_added": money_added}


@request_cached(deep=True)
def build_investment_report(db, accounts, assets, reporting, start: str, end: str):
    """Return period flows and end positions for the user's own investment portfolio."""
    account_rows = accounts.list(active_only=False)
    account_by_id = {a.id: a for a in account_rows}
    investment_account_ids = {a.id for a in account_rows if a.account_type in INVESTMENT_ACCOUNT_TYPES}
    placeholders = ",".join("?" for _ in investment_account_ids)
    if not placeholders:
        return {"new_money": ZERO, "withdrawn": ZERO, "net_money": ZERO,
                "dividends": ZERO, "realized": ZERO, "unresolved_dividends": 0,
                "holdings": [], "investment_cash": ZERO, "missing": [], "at_cost": [], "cost": ZERO,
                "value": ZERO, "unrealized": ZERO}
    rows = db.all(
        f"SELECT le.*,t.type,t.ref,t.status,c.code AS category_code, "
        f"da.asset_id AS dividend_asset_id "
        f"FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
        f"LEFT JOIN categories c ON c.id=le.category_id "
        f"LEFT JOIN investment_dividend_assets da ON da.transaction_id=t.id "
        f"WHERE t.status='POSTED' AND t.type<>'VAL' AND le.owner_id IS NULL AND le.date<=? "
        f"ORDER BY le.date,t.id,le.line_no", (end,))
    # Metadata is stable for this read-only report invocation. Loading it once
    # avoids one SELECT per historical ledger row while keeping all results
    # local to this report (no cross-request invalidation concerns).
    asset_by_id = {a.id: a for a in assets.list_assets()}
    # Average cost is retained independently for each account and asset.
    books = defaultdict(lambda: {"units": ZERO, "cost": ZERO, "realized": ZERO})
    movements = defaultdict(Decimal)
    dividends = ZERO
    cash_quantities = defaultdict(Decimal)
    # Use asset metadata by id; account boundaries are determined by account type.
    for row in rows:
        key = (row["owner_id"], row["account_id"], row["asset_id"])
        asset = asset_by_id[row["asset_id"]]
        q, amount = from_e6(row["quantity_e6"]), from_e6(row["amount_base_e6"])
        if asset.is_cash:
            if row["account_id"] in investment_account_ids:
                cash_quantities[row["asset_id"]] += q
            if (row["account_id"] in investment_account_ids and
                    (row["type"] == "DIV" or row["category_code"] in
                     ("EXP.INVEST.DIVIDEND", "EXP.INVEST.INTEREST")) and row["date"] >= start):
                dividends += amount
            continue
        if row["type"] == "DIV":
            # Missing legacy attribution is explicitly unresolved; cash remains in portfolio cash.
            continue
        b = books[key]
        if q > ZERO:
            b["units"] += q
            b["cost"] += amount
        elif q < ZERO:
            removed = b["cost"] / b["units"] * -q if b["units"] else ZERO
            if row["type"] == "SEL":
                b["realized"] += -amount - removed
            b["cost"] -= removed
            b["units"] += q
            if not b["units"]:
                b["cost"] = ZERO
    # Portfolio boundary movement per source transaction: inside-to-inside lines cancel.
    for row in rows:
        if (row["date"] < start or row["type"] in ("DIV", "OPN") or row["category_code"] in
                ("EXP.INVEST.DIVIDEND", "EXP.INVEST.INTEREST")):
            continue
        acc = row["account_id"]
        if acc in investment_account_ids:
            movements[row["transaction_id"]] += from_e6(row["amount_base_e6"])
    # Normalize transaction deltas: positive means cash/value entered the portfolio.
    new_money = withdrawn = ZERO
    for delta in movements.values():
        if delta > ZERO:
            new_money += delta
        elif delta < ZERO:
            withdrawn -= delta
    period_realized = _realized_between(rows, start, end)
    holdings = []; total_cost = total_value = unrealized = ZERO; missing=[]; at_cost=[]
    holdings_unavailable = False
    for (owner_id, account_id, asset_id), b in books.items():
        if b["units"] <= ZERO:
            continue
        asset = asset_by_id[asset_id]
        valuation = reporting.value_of(asset_id, b["units"], end)
        value = valuation.value
        if value is None:
            missing.append({"asset": asset.name, "reason": valuation.reason or "Missing confirmed market price"})
            holdings_unavailable = True
        else:
            # Before an asset's first price, what you paid is the best value there is: count it at
            # cost (no gain yet) and say so, rather than making the whole result unavailable.
            if valuation.source == "COST":
                at_cost.append({"asset": asset.name, "since": valuation.price_date})
            total_value += value
            unrealized += value-b["cost"]
        total_cost += b["cost"]
        holdings.append({"account": account_by_id[account_id].label, "asset": asset.name,
                         "units": b["units"], "cost": b["cost"], "value": value,
                         "realized": b["realized"], "unrealized": None if value is None else value-b["cost"],
                         "price_date": valuation.price_date, "price_source": valuation.source})
    cash = ZERO
    cash_unavailable = False
    for cash_asset_id, quantity in cash_quantities.items():
        valuation = reporting.value_of(cash_asset_id, quantity, end)
        asset = assets.get_asset(cash_asset_id)
        if valuation.value is None:
            missing.append({"asset": f"{asset.currency} investment cash", "reason": valuation.reason or "Missing dated exchange rate"})
            cash_unavailable = True
        else:
            cash += valuation.value
    unresolved = db.scalar("SELECT COUNT(*) FROM transactions t JOIN ledger_entries le ON le.transaction_id=t.id "
                           "LEFT JOIN investment_dividend_assets da ON da.transaction_id=t.id "
                           "WHERE t.status='POSTED' AND t.type='DIV' AND le.owner_id IS NULL AND da.asset_id IS NULL "
                           "AND le.date BETWEEN ? AND ?", (start,end)) or 0
    if cash and not cash_unavailable:
        holdings.append({"account": "Investment accounts", "asset": "Uninvested cash", "units": cash,
                         "cost": cash, "value": cash, "realized": ZERO, "unrealized": ZERO,
                         "price_date": end, "price_source": "CASH"})
    return {"new_money": new_money, "withdrawn": withdrawn, "net_money": new_money-withdrawn,
            "dividends": dividends, "realized": period_realized, "holdings": holdings,
            "investment_cash": None if cash_unavailable else cash, "cost": total_cost,
            "value": None if holdings_unavailable else total_value,
            "unrealized": None if holdings_unavailable else unrealized,
            "missing": missing, "at_cost": at_cost, "unresolved_dividends": unresolved}


def _realized_between(rows, start, end):
    books = defaultdict(lambda: {"units": ZERO, "cost": ZERO})
    realized = ZERO
    for row in rows:
        if row["type"] == "DIV" or row["date"] > end:
            continue
        if row["asset_id"] is None:
            continue
        # Caller rows include cash; only sale/buy/opening investment lines have signed units and no cash asset.
        if row["type"] not in ("BUY", "SEL", "OPN"):
            continue
        key=(row["owner_id"],row["account_id"],row["asset_id"]); b=books[key]
        q,amount=from_e6(row["quantity_e6"]),from_e6(row["amount_base_e6"])
        if q>ZERO: b["units"]+=q; b["cost"]+=amount
        elif q<ZERO:
            removed=b["cost"]/b["units"]*(-q) if b["units"] else ZERO
            if row["type"]=="SEL" and row["date"]>=start: realized += -amount-removed
            b["cost"]-=removed; b["units"]+=q
            if not b["units"]: b["cost"]=ZERO
    return realized


def results_by_asset(investments, money_from_others, reporting, opening_day: str, current_day: str):
    """Result per asset class and per asset between two dates, for the user's own share.

    Each holding's Result = Change in unrealized gain + Realized gain + Dividends and interest; a
    holding sold out during the period keeps its realized gain and distributions.
    Returns ({class name: result}, {asset id: {"label", "result"}}).
    """
    current_portfolio = investments.portfolio(current_day)
    opening_portfolio = investments.portfolio(opening_day)
    current_by_key = {(h.account_id, h.asset_id): h for h in current_portfolio.positions}
    opening_by_key = {(h.account_id, h.asset_id): h for h in opening_portfolio.positions}

    def owned_values(portfolio, on_day):
        custody_units = defaultdict(lambda: ZERO)
        for row in money_from_others.investment_positions(on_day):
            custody_units[(row["account_id"], row["asset_id"])] += row["units"]
        values = {}
        for holding in portfolio.open:
            key = (holding.account_id, holding.asset_id)
            others = custody_units.get(key, ZERO)
            other_value = (reporting.value_of(holding.asset_id, others, on_day).value or ZERO) if others else ZERO
            share = ((holding.value or ZERO) - other_value) / holding.value if holding.value else ZERO
            values[key] = (share, (holding.value or ZERO) - other_value,
                           holding.cost_basis * (holding.quantity - others) / holding.quantity
                           if holding.quantity else ZERO)
        return values

    current_owned = owned_values(current_portfolio, current_day)
    opening_owned = owned_values(opening_portfolio, opening_day)
    class_results = defaultdict(lambda: ZERO)
    asset_results = defaultdict(lambda: {"label": "", "result": ZERO})
    for key, holding in current_by_key.items():
        previous = opening_by_key.get(key)
        old_share, old_value, old_cost = opening_owned.get(key, (ZERO, ZERO, ZERO))
        if not holding.is_open:
            # Sold out during the period: its sale gain and distributions still
            # belong to the period result, less any gain it carried in.
            realized = holding.realized - (previous.realized if previous else ZERO)
            dividends = holding.dividends - (previous.dividends if previous else ZERO)
            if not realized and not dividends:
                continue
            share = old_share if previous and old_share else Decimal(1)
            result = (realized + dividends) * share - ((old_value - old_cost) if previous else ZERO)
            class_results[holding.asset_class.split(" › ")[-1]] += result
            asset_result = asset_results[holding.asset_id]
            asset_result["label"] = holding.asset_name
            asset_result["result"] += result
            continue
        if holding.value is None:
            continue
        share, owned_value, owned_cost = current_owned.get(key, (ZERO, ZERO, ZERO))
        if previous and previous.value is not None:
            unrealized_change = (owned_value - owned_cost) - (old_value - old_cost)
            realized_change = (holding.realized - previous.realized) * share
            distribution_change = (holding.dividends - previous.dividends) * share
        else:
            unrealized_change = owned_value - owned_cost
            realized_change = holding.realized * share
            distribution_change = holding.dividends * share
        result = unrealized_change + realized_change + distribution_change
        class_results[holding.asset_class.split(" › ")[-1]] += result
        asset_result = asset_results[holding.asset_id]
        asset_result["label"] = holding.asset_name
        asset_result["result"] += result
    return class_results, asset_results


PLANNER_MODES = ("prorata", "fill_gaps")


def suggest_contributions(values: dict[str, Decimal], targets: dict[str, Decimal], amount: Decimal,
                          mode: str = "prorata") -> dict[str, Decimal]:
    """Split new money across allocation classes to move toward their targets; nothing is ever sold.

    A class's gap is how far below its target share it would sit once the new money is in, in
    percentage points of that total. At a fixed total that is proportional to its shortfall in money,
    so both modes work on shortfalls. ``prorata`` gives every under-target class the same fraction of
    its gap. ``fill_gaps`` levels from the top: the furthest-behind class is filled until it matches
    the next, then both together, and so on. When the money covers every gap the two agree.
    Returns {} until the targets total 100%."""
    if mode not in PLANNER_MODES:
        raise ValueError(f"Unknown planner mode: {mode}")
    if amount <= ZERO or sum(targets.values(), ZERO) != 100:
        return {}
    total = sum(values.values(), ZERO) + amount
    shortfalls = {b: s for b, t in targets.items() if (s := t * total / 100 - values.get(b, ZERO)) > ZERO}
    deficit = sum(shortfalls.values(), ZERO)
    if not deficit:
        return {}
    if mode == "prorata":
        raw = {b: amount * s / deficit for b, s in shortfalls.items()}
    else:
        # The level every gap is brought down to: the k largest gaps lose (sum - amount) / k each,
        # as long as that stays at or above the next gap down.
        ordered = sorted(shortfalls.values(), reverse=True)
        level, running = ZERO, ZERO
        for k, s in enumerate(ordered, 1):
            running += s
            level = (running - amount) / k
            if k == len(ordered) or level >= ordered[k]:
                break
        level = max(ZERO, level)
        raw = {b: s - level for b, s in shortfalls.items() if s > level}
    cent = Decimal("0.01")
    split = {b: x.quantize(cent) for b, x in raw.items()}
    # Rounding leftovers go to the largest suggestion, so the split adds up and none turns negative.
    split[max(split, key=lambda b: (split[b], b))] += amount - sum(split.values(), ZERO)
    return {b: x for b, x in split.items() if x > ZERO}


def _adjust_alone(value: Decimal, total: Decimal, target: Decimal | None) -> Decimal | None:
    """Buy (+) or sell (−) of one class alone so it becomes ``target`` % of the new total."""
    if target is None:
        return None
    share = target / 100
    if share >= 1:  # 100%: only possible by selling everything else, which this class cannot do alone
        return None if total - value else ZERO
    return ((share * total - value) / (1 - share)).quantize(Decimal("0.01"))


def allocation_plan(values: dict[str, Decimal], targets: dict[str, Decimal], classes: list[str]) -> dict:
    """Target allocation: for each class its current share, the required share, the difference, and
    the value to adjust: how much to buy (or sell, when negative) of that one class alone to reach its
    required share, with every other class left as it is. Buying grows the total too, so for a value v,
    total T and target t the amount is (t × T − v) ÷ (1 − t). ``values`` are owned holdings by class."""
    total = sum(values.values(), ZERO)
    # Every class is listed, so a target can be set on one you hold nothing in yet. Heaviest first.
    names = list(classes) + sorted(set(values) - set(classes))
    rows = []
    for name in names:
        value = values.get(name, ZERO)
        current = value / total * 100 if total else ZERO
        target = targets.get(name)
        rows.append({"name": name, "value": value, "current": current, "target": target,
                     "difference": None if target is None else target - current,
                     "adjust": _adjust_alone(value, total, target)})
    rows.sort(key=lambda r: (-r["value"], -(r["target"] or ZERO), r["name"].casefold()))
    required = sum(targets.values(), ZERO)
    return {"rows": rows, "total": total, "required": required, "complete": required == 100,
            "unset": [n for n in classes if n not in targets and not values.get(n)]}
