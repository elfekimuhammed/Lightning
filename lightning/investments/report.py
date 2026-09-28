"""Traceable, owner-scoped investment report derived from posted ledger entries."""
from collections import defaultdict
from decimal import Decimal

from lightning.accounts.domain import INVESTMENT_ACCOUNT_TYPES
from lightning.core.money import ZERO, from_e6


def build_investment_report(db, accounts, assets, reporting, start: str, end: str):
    """Return period flows and end positions for the user's own investment portfolio."""
    investment_account_ids = {a.id for a in accounts.list(active_only=False)
                              if a.account_type in INVESTMENT_ACCOUNT_TYPES}
    placeholders = ",".join("?" for _ in investment_account_ids)
    if not placeholders:
        return {"new_money": ZERO, "withdrawn": ZERO, "net_money": ZERO,
                "dividends": ZERO, "realized": ZERO, "unresolved_dividends": 0,
                "holdings": [], "investment_cash": ZERO, "missing": [], "cost": ZERO,
                "value": ZERO, "unrealized": ZERO, "estimated_cash": ZERO}
    rows = db.all(
        f"SELECT le.*,t.type,t.ref,t.status,c.code AS category_code, "
        f"da.asset_id AS dividend_asset_id "
        f"FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
        f"LEFT JOIN categories c ON c.id=le.category_id "
        f"LEFT JOIN investment_dividend_assets da ON da.transaction_id=t.id "
        f"WHERE t.status='POSTED' AND t.type<>'VAL' AND le.owner_id IS NULL AND le.date<=? "
        f"ORDER BY le.date,t.id,le.line_no", (end,))
    # Average cost is retained independently for each account and asset.
    books = defaultdict(lambda: {"units": ZERO, "cost": ZERO, "realized": ZERO})
    movements = defaultdict(Decimal)
    dividends = ZERO
    cash_quantities = defaultdict(Decimal)
    # Use asset metadata by id; account boundaries are determined by account type.
    for row in rows:
        key = (row["owner_id"], row["account_id"], row["asset_id"])
        asset = assets.get_asset(row["asset_id"])
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
    holdings = []; total_cost = total_value = unrealized = estimated = ZERO; missing=[]
    holdings_unavailable = False
    factors = {r["asset_class_id"]: Decimal(str(r["factor"])) / 100
               for r in db.all("SELECT asset_class_id,factor FROM investment_liquidation_factors")}
    for (owner_id, account_id, asset_id), b in books.items():
        if b["units"] <= ZERO:
            continue
        asset = assets.get_asset(asset_id)
        valuation = reporting.value_of(asset_id, b["units"], end)
        value = valuation.value
        if value is None or valuation.source == "COST":
            missing.append({"asset": asset.name, "reason": "Missing confirmed market price" if value is None else "Only cost fallback is available"})
            holdings_unavailable = True
        else:
            total_value += value
            unrealized += value-b["cost"]
            estimated += value*factors.get(asset.asset_class_id, Decimal(1))
        total_cost += b["cost"]
        holdings.append({"account": accounts.get(account_id).label, "asset": asset.name,
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
            "estimated_cash": None if missing or cash_unavailable else cash+estimated,
            "missing": missing, "unresolved_dividends": unresolved}


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
