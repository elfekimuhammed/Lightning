"""Chart data for pages: read figures from services, then shape them with lightning.ui.charts.

No financial calculation happens here: every value is a figure a service computed.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from lightning.core.dates import fmt_date, month_of, parse_date, parse_month
from lightning.core.money import ZERO, from_e6

from . import charts


def months_back(end: date, count: int, first_activity: str | None) -> list[str]:
    """Up to ``count`` months ending with ``end``'s month, never before the first recorded activity."""
    keys, cursor = [], end.replace(day=1)
    floor = parse_date(first_activity).replace(day=1) if first_activity else cursor
    while len(keys) < count and cursor >= floor:
        keys.append(month_of(cursor))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(keys))


def flow_trend(c, end: date, count: int = 6) -> dict:
    """Money in and money out per month (the same figures as Cash flow), ending with ``end``."""
    keys = months_back(end, count, c.reporting.first_activity_date())
    if not keys:
        return charts.trend([], [])
    rows = {r["month"]: r for r in c.reporting.monthly_flow_between(parse_month(keys[0])[0], end)}
    return charts.trend(keys, [
        {"name": "Money in", "tone": "in", "values": [rows.get(k, {}).get("inflows", ZERO) for k in keys]},
        {"name": "Money out", "tone": "spend", "values": [rows.get(k, {}).get("outflows", ZERO) for k in keys]},
    ])


def spending_trend(c, end: date, category_code: str = "", count: int = 6) -> dict:
    """Money out per month, with the month's plan as a dashed line when one exists."""
    keys = months_back(end, count, c.reporting.first_activity_date())
    if not keys:
        return charts.trend([], [])
    if category_code:
        values = []
        depth = c.categories.get_by_code(category_code).depth
        for key in keys:
            first, last = parse_month(key)
            last = min(last, end)
            values.append(sum((g.value for g in c.reporting.spending_by_category(first, last, depth=depth)
                               if g.code == category_code), ZERO))
    else:
        rows = {r["month"]: r for r in c.reporting.monthly_flow_between(parse_month(keys[0])[0], end)}
        values = [rows.get(k, {}).get("outflows", ZERO) for k in keys]
    plan, over = None, None
    if not category_code:
        # Each month is over (or not) against its own plan; the dashed line is the latest month's.
        plans = [c.budgets.month_view(k).available if c.budgets.has_plan(k) else None for k in keys]
        over = [p is not None and v > p for p, v in zip(plans, values)]
        plan = plans[-1] or None
    return charts.trend(keys, [{"name": "Money out", "tone": "hold", "values": values, "area": True, "over": over}],
                        plan=plan)


def spending_bars(c, first: date, last: date, limit: int = 6) -> dict:
    """Money out by category: each L1 as a header with its L2 categories under it, each linking to
    its transactions."""
    rows = []
    for group in c.reporting.spending_by_category(first, last, depth=2):
        if group.value <= 0:
            continue
        category = c.categories.get_by_code(group.code)
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first), "date_to": fmt_date(last)})
        parent = c.categories.get(category.parent_id).name if category.parent_id else category.name
        rows.append({"group": parent, "label": category.name, "value": group.value, "href": f"/transactions?{query}"})
    return charts.grouped_bars(rows, limit)


def _leaf(name: str) -> str:
    return name.split(" › ")[-1]


def cash_flow_columns(c, first: date, last: date, cash_flow) -> dict:
    """Money in, less money out by top-level category (Personal, Work, ...), down to net flow."""
    groups = [g for g in c.reporting.spending_by_category(first, last, depth=1) if g.value]
    steps = [(_leaf(g.label), -g.value) for g in groups]
    rest = cash_flow.outflows - sum((g.value for g in groups), ZERO)
    if rest:  # anything the category tree does not carry, so the path still ends at net flow
        steps.append(("Other money out", -rest))
    return charts.column_waterfall(("Money in", cash_flow.inflows), steps, ("Net flow", cash_flow.net))


def money_out_groups(c, first: date, last: date) -> list[dict]:
    """Money out by top-level category, each linking to its transactions (the Cash flow list)."""
    rows = []
    for g in c.reporting.spending_by_category(first, last, depth=1):
        category = c.categories.get_by_code(g.code)
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first), "date_to": fmt_date(last)})
        rows.append({"label": _leaf(g.label), "value": g.value, "href": f"/transactions?{query}"})
    return rows


def money_in_groups(c, first: date, last: date) -> list[dict]:
    """Money in by income category, largest first, each linking to its transactions."""
    rows = []
    for g in c.reporting.money_in_by_category(first, last):
        category = c.categories.get_by_code(g.code)
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first), "date_to": fmt_date(last)})
        rows.append({"label": _leaf(g.label), "value": g.value, "href": f"/transactions?{query}"})
    return rows


def money_sankey(c, first: date, last: date, cash_flow, sources_shown: int = 3, targets_shown: int = 5) -> dict:
    """Where money in went: income by category into money in, and money in out to spending
    categories and what you kept. When money out is larger, the gap comes from what you had."""
    incomes = money_in_groups(c, first, last)
    sources = [{**r, "tone": "in"} for r in incomes[:sources_shown]]
    rest_in = cash_flow.inflows - sum((r["value"] for r in sources), ZERO)
    if rest_in > 0:
        sources.append({"label": "Other income", "value": rest_in, "tone": "in"})
    if cash_flow.net < 0:
        sources.append({"label": "From what you had", "value": -cash_flow.net, "tone": "over"})
    spending = []
    for g in c.reporting.spending_by_category(first, last, depth=2):
        if g.value <= 0:
            continue
        category = c.categories.get_by_code(g.code)
        query = urlencode({"category_id": category.id, "date_from": fmt_date(first), "date_to": fmt_date(last)})
        spending.append({"label": _leaf(g.label), "value": g.value, "tone": "spend", "href": f"/transactions?{query}"})
    targets = spending[:targets_shown]
    rest_out = cash_flow.outflows - sum((t["value"] for t in targets), ZERO)
    if rest_out > 0:
        targets.append({"label": "Other spending", "value": rest_out, "tone": "spend"})
    if cash_flow.net > 0:
        targets.append({"label": "Kept", "value": cash_flow.net, "tone": "hold"})
    return charts.sankey(sources, targets, "Money in")


def savings_rate_spark(c, end: date, count: int = 6) -> dict:
    """Savings rate for each recent month (the service's own figure), as a sparkline."""
    values = []
    for key, day in month_ends(end, count, c.reporting.first_activity_date()):
        values.append(c.reporting.cash_flow(parse_month(key)[0], day).savings_rate)
    return charts.sparkline(values)


def holdings_donut(position, include_deposits: bool = False, include_cash: bool = False) -> dict:
    """What you hold by asset class, in class colours (cash, deposits, gold, equity, other)."""
    slices = []
    if include_cash and position.cash_you_own:
        slices.append({"label": "Cash you own", "value": position.cash_you_own, "tone": "cash"})
    for cls in position.classes:
        if cls.is_deposit and not include_deposits:
            continue
        slices.append({"label": cls.name, "value": cls.value, "tone": charts.class_tone(cls.code)})
    if include_cash and position.other_you_own > 0:
        slices.append({"label": "Other you own", "value": position.other_you_own, "tone": "other"})
    return charts.donut(slices)


def portfolio_trend(values: list[tuple[str, Decimal | None]]) -> dict:
    """Portfolio value per month, starting at the first month that held anything."""
    started = False
    kept = []
    for label, value in values:
        if not started and not value:
            continue
        started = True
        kept.append((label, value))
    return charts.trend([k for k, _ in kept], [{"name": "Portfolio value", "tone": "hold",
                                                "values": [v for _, v in kept], "area": True}])


def forecast_trend(forecast) -> dict:
    """The forecast's Ends with for each month."""
    labels = [m.month for m in forecast.months]
    values = [m.closing for m in forecast.months]
    return charts.trend(labels, [{"name": "Ends with", "tone": "hold", "values": values, "area": True}])


def month_ends(end: date, count: int, first_activity: str | None) -> list[tuple[str, date]]:
    """(yyyy-mm, month end) for up to ``count`` months ending with ``end`` (the last one is ``end``)."""
    out = []
    for key in months_back(end, count, first_activity):
        _, last = parse_month(key)
        out.append((key, min(last, end)))
    return out


def net_worth_trend(c, end: date, count: int = 12) -> dict:
    """Net worth at each month end (the same Position as the Overview's cards)."""
    points = [(key, c.position.at(day)) for key, day in month_ends(end, count, c.reporting.first_activity_date())]
    owes = any(pos.what_you_owe for _, pos in points)
    # One line: the breakdown right under the chart carries What you own and What you owe.
    series = [{"name": "Net worth" if owes else "What you own", "tone": "hold", "area": True,
               "values": [pos.net_worth if owes else pos.what_you_own for _, pos in points]}]
    return charts.trend([k for k, _ in points], series)


def free_cash_steps(position) -> dict | None:
    """Cash you own, less reserves and bills due, down to free cash."""
    if position.free_cash is None:
        return None
    return charts.waterfall(("Cash you own", position.cash_you_own),
                            [("Reserves", -(position.reserves or ZERO)), ("Bills due", -position.bills_due)],
                            ("Free cash", position.free_cash))


def trend_spark(t: dict) -> dict:
    """The first series of a trend as a sparkline (a stat card's background line)."""
    series = t.get("series") or []
    return charts.sparkline(series[0]["values"] if series else [])


def usual_rows(rows: list[dict], limit: int = 10) -> list[dict]:
    """Categories against their usual month, each with a mini trend."""
    return [{**r, "label": r["label"].split(" › ")[-1], "group": r["label"].split(" › ")[0],
             "spark": charts.sparkline(r["history"])} for r in rows[:limit]]


def counterparty_bars(c, first: date, last: date, limit: int = 8) -> dict:
    """Who you paid most, each linking to their transactions."""
    rows = [{"label": name, "value": value,
             "href": "/transactions?" + urlencode({"q": name, "date_from": fmt_date(first), "date_to": fmt_date(last)})}
            for name, value in c.reporting.spending_by_counterparty(first, last)]
    return charts.bars(rows, limit)


def account_bars(c, first: date, last: date) -> dict:
    """Which accounts the spending was paid from."""
    names = {a.id: a.name for a in c.accounts.list()}
    rows = [{"label": names.get(account_id, "Account"), "value": value,
             "href": f"/accounts/{account_id}?" + urlencode({"month": fmt_date(last)[:7]}) if fmt_date(first)[:7] == fmt_date(last)[:7] else f"/accounts/{account_id}"}
            for account_id, value in c.reporting.spending_by_account(first, last)]
    return charts.bars(rows, 6)


def holding_journey(c, account_id: int, asset_id: int, end: date, months: int = 24) -> dict:
    """One holding's month-end history (price, units, value, cost) and what it says about
    profitability and volatility. Up to ``months`` month ends, from its first trade to ``end``."""
    lines = [l for l in c.reporting.investment_lines(fmt_date(end), account_id)
             if l.get("asset_id") == asset_id or l.get("dividend_asset_id") == asset_id]
    trades = [l for l in lines if l.get("asset_id") == asset_id and l["type"] != "DIV"]
    if not trades:
        return {"labels": [], "trades": []}
    first = parse_date(trades[0]["date"])
    keys = months_back(end, months, fmt_date(first))
    labels, price, value, cost = [], [], [], []
    for key in keys:
        _, last = parse_month(key)
        day = min(last, end)
        pos = next((x for x in c.investments.portfolio(fmt_date(day), account_id).positions if x.asset_id == asset_id), None)
        labels.append(key)
        price.append(pos.price if pos and pos.quantity else None)
        value.append(pos.value if pos and pos.quantity else None)
        cost.append(pos.cost_basis if pos and pos.quantity else None)
    returns = []
    for i in range(1, len(price)):
        if price[i] is not None and price[i - 1]:
            returns.append((labels[i], (price[i] / price[i - 1] - 1) * 100))
    peak, drawdown = None, []
    for p in price:
        if p is None:
            drawdown.append(None)
            continue
        peak = p if peak is None or p > peak else peak
        drawdown.append((p / peak - 1) * 100 if peak else ZERO)
    moves = [r for _, r in returns]
    typical = None
    if len(moves) >= 3:
        mean = sum(moves, ZERO) / len(moves)
        typical = (sum(((m - mean) ** 2 for m in moves), ZERO) / len(moves)).sqrt()
    known_dd = [d for d in drawdown if d is not None]
    # The journey: every trade and payout, with units held after it.
    held, journey = ZERO, []
    names = {"BUY": "Bought", "SEL": "Sold", "DIV": "Dividend", "OPN": "Starting holding", "ADJ": "Adjusted"}
    for l in lines:
        units = ZERO if l["type"] == "DIV" else from_e6(l["quantity_e6"] or 0)
        amount = from_e6(l["amount_base_e6"] or 0)
        held += units
        journey.append({"date": l["date"], "kind": names.get(l["type"], "Holding added" if units > 0 else "Units out"),
                        "units": units, "amount": abs(amount), "price": abs(amount / units) if units else None,
                        "held": held, "ref": l.get("ref")})
    average = cost[-1] / (value[-1] / price[-1]) if cost[-1] and value[-1] and price[-1] else None
    return {
        "labels": labels, "first": fmt_date(first), "months_held": len(keys),
        "price": charts.trend(labels, [{"name": "Price", "tone": "hold", "values": price, "plan_applies": False}],
                              plan=average),
        "value_cost": charts.trend(labels, [{"name": "Value", "tone": "hold", "values": value, "area": True},
                                            {"name": "Cost", "tone": "other", "values": cost}]),
        "drawdown": charts.trend(labels, [{"name": "Below its high", "tone": "spend", "area": True,
                                           "values": drawdown}]),
        "returns": charts.diverging([{"label": k, "value": v} for k, v in returns]),
        "best": max(returns, key=lambda r: r[1]) if returns else None,
        "worst": min(returns, key=lambda r: r[1]) if returns else None,
        "typical": typical, "max_drawdown": min(known_dd) if known_dd else None,
        "up": sum(1 for m in moves if m > 0), "down": sum(1 for m in moves if m < 0),
        "spark": charts.sparkline(value[-6:]), "trades": list(reversed(journey)),
    }


def expense_analysis(c, first: date, last: date, code_filter: str = "", history: int = 12,
                     floor_share: Decimal = Decimal(1), top: int = 8) -> dict:
    """Expense analysis in five questions, big items only.

    Categories (L2) under ``floor_share`` % of money out, or past the ``top`` largest, fold into
    "Smaller categories". History is the ``history`` whole months before the period; "now" is the
    period's money out per month, so a year to date compares like with like."""
    def by_cat(start, end):
        rows = {}
        for g in c.reporting.spending_by_category(start, end, depth=2):
            if g.value > 0 and (not code_filter or g.code.startswith(code_filter)):
                rows[g.code] = (g.label.split(" › ")[-1], g.value)
        return rows

    now = by_cat(first, last)
    total = sum((v for _, v in now.values()), ZERO)
    months_in = max(1, (last.year - first.year) * 12 + last.month - first.month + 1)
    ranked = sorted(now.items(), key=lambda kv: -kv[1][1])
    big = [(code, name, value) for code, (name, value) in ranked[:top]
           if total and value / total * 100 >= floor_share]
    small = total - sum((v for _, _, v in big), ZERO)
    # Whole months before the period, oldest first, never before the first record.
    keys = months_back(first.replace(day=1) - timedelta(days=1), history, c.reporting.first_activity_date())
    hist = [by_cat(*parse_month(k)) for k in keys]
    rows = []
    for code, name, value in big:
        past = [h.get(code, ("", ZERO))[1] for h in hist]
        per_month = value / months_in
        recent = past[-6:]
        usual = sum(recent, ZERO) / len(recent) if recent else None
        ordered = sorted(past)
        median = (ordered[len(ordered) // 2] if len(ordered) % 2 else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2) if ordered else None
        low, high = (min(past), max(past)) if past else (None, None)
        scale = max([per_month] + past) or Decimal(1)
        category = c.categories.get_by_code(code)
        rows.append({"code": code, "name": name, "value": value, "per_month": per_month, "share": value / total * 100,
                     "usual": usual, "past": past, "low": low, "high": high, "median": median,
                     "above": high is not None and per_month > high, "below": low is not None and per_month < low,
                     "range": None if low is None else {"low": float(low / scale * 100), "high": float(high / scale * 100),
                                                        "median": float(median / scale * 100), "now": float(per_month / scale * 100)},
                     "href": f"/transactions?category_id={category.id}&date_from={fmt_date(first)}&date_to={fmt_date(last)}"})
    tiles = charts.treemap([{"label": r["name"], "value": r["value"], "share": r["share"], "href": r["href"]} for r in rows]
                           + ([{"label": "Smaller categories", "value": small, "share": small / total * 100 if total else 0,
                                "small": True}] if small > 0 else []))
    # Clustered columns: usual month (neutral) beside now (its meaning colour), one scale, from zero.
    col_max = max([r["per_month"] for r in rows] + [r["usual"] or ZERO for r in rows] + [ZERO]) or Decimal(1)
    clusters = [{"name": r["name"], "now": r["per_month"], "usual": r["usual"],
                 "over": bool(r["usual"]) and r["per_month"] > r["usual"] * Decimal("1.1"),
                 "now_h": float(r["per_month"] / col_max * 100), "usual_h": float((r["usual"] or ZERO) / col_max * 100)}
                for r in rows[:6]]
    # Small multiples: the same twelve months plus now, one scale for every panel.
    panels = rows[:6]
    lines = charts.shared_lines([r["past"] + [r["per_month"]] for r in panels])
    multiples = [{"name": r["name"], "now": r["per_month"], "line": line, "points": len(r["past"]) + 1}
                 for r, line in zip(panels, lines)]
    # Heatmap: category by month, each cell against that row's own average (four rose steps). The
    # history months, then every month of the period itself (a period of three months shows three).
    period_keys = months_back(last, months_in, fmt_date(first))
    period_months = [by_cat(max(parse_month(k)[0], first), min(parse_month(k)[1], last)) for k in period_keys]
    past_cols = keys[-max(1, 12 - len(period_keys)):] if keys else []
    heat_keys = past_cols + period_keys
    now_from = len(past_cols)
    heat = []
    for r in rows:
        values = r["past"][-len(past_cols):] if past_cols else []
        values = values + [m.get(r["code"], ("", ZERO))[1] for m in period_months]
        known = [v for v in values if v > 0]
        avg = sum(known, ZERO) / len(known) if known else ZERO
        cells = []
        for v in values:
            ratio = v / avg if avg else ZERO
            step = 0 if v <= 0 else 1 if ratio < Decimal("0.75") else 2 if ratio < Decimal("1.1") else 3 if ratio < Decimal("1.5") else 4
            cells.append({"value": v, "step": step})
        heat.append({"name": r["name"], "cells": cells})
    heat_now = now_from
    usual_total = sum((r["usual"] or ZERO for r in rows), ZERO)
    recent_all = [sum((v for _, v in h.values()), ZERO) for h in hist[-6:]]
    usual_out = sum(recent_all, ZERO) / len(recent_all) if recent_all else None
    return {"rows": rows, "total": total, "small": small, "months_in": months_in, "tiles": tiles,
            "clusters": clusters, "multiples": multiples, "heat": heat, "heat_keys": heat_keys, "heat_now": now_from,
            "history_months": len(keys), "usual_total": usual_total, "usual_out": usual_out,
            "per_month": total / months_in,
            "has_history": len(keys) >= 1, "has_range": len(keys) >= 3}
