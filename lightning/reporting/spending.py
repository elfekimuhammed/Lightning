"""How a period's spending compares with your usual months (the figures behind Expense analysis).

Every number here is a registry figure (Per month, Usual month, Usual range); `lightning.ui.visuals`
only draws them.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from lightning.core.dates import fmt_date, months_back, parse_month
from lightning.core.money import ZERO


def _median(values: list[Decimal]) -> Decimal | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _against_history(past: list[Decimal], per_month: Decimal) -> dict:
    """Usual month (the average of the last six whole months) and Usual range (lowest, middle and
    highest of the history), and where this period's Per month sits against them."""
    recent = past[-6:]
    usual = sum(recent, ZERO) / len(recent) if recent else None
    low, high = (min(past), max(past)) if past else (None, None)
    return {"usual": usual, "past": past, "low": low, "high": high, "median": _median(past),
            "above": high is not None and per_month > high, "below": low is not None and per_month < low,
            # More than 10% over the usual month counts as over it.
            "over_usual": bool(usual) and per_month > usual * Decimal("1.1"),
            "change_vs_usual": (per_month - usual) / usual * 100 if usual else None}


def spending_profile(reporting, first: date, last: date, code_filter: str = "", history: int = 12,
                     floor_share: Decimal = Decimal(1), top: int = 4) -> dict:
    """Money out by category (second level) for the period, the biggest ``top`` categories that are at
    least ``floor_share`` % of it, one "Other" row for the rest, and each row against the ``history``
    whole months before the period. Per month is the period's money out per calendar month it covers,
    so a year to date compares like with like."""
    def by_cat(start, end) -> dict[str, tuple[str, Decimal]]:
        rows = {}
        for g in reporting.spending_by_category(start, end, depth=2):
            if g.value > 0 and (not code_filter or g.code.startswith(code_filter)):
                rows[g.code] = (g.label.split(" › ")[-1], g.value)
        return rows

    now = by_cat(first, last)
    spent = sum((v for _, v in now.values()), ZERO)
    # A category whose refunds outweigh its spending (August's purchase returned in October) takes
    # money off: it is its own row, so the rows add up to Money out and every share is of Money out.
    refunds = [{"code": g.code, "name": g.label.split(" › ")[-1], "value": g.value}
               for g in reporting.spending_by_category(first, last, depth=2)
               if g.value < 0 and (not code_filter or g.code.startswith(code_filter))]
    money_out = spent + sum((r["value"] for r in refunds), ZERO)
    total = money_out if money_out > 0 else spent
    months_in = max(1, (last.year - first.year) * 12 + last.month - first.month + 1)
    ranked = sorted(now.items(), key=lambda kv: -kv[1][1])
    big = [(code, name, value) for code, (name, value) in ranked[:top]
           if total and value / total * 100 >= floor_share]
    small = spent - sum((v for _, _, v in big), ZERO)
    # Whole months before the period, oldest first, never before the first record.
    keys = months_back(first.replace(day=1) - timedelta(days=1), history, reporting.first_activity_date())
    hist = [by_cat(*parse_month(k)) for k in keys]
    rows = []
    for code, name, value in big:
        per_month = value / months_in
        rows.append({"code": code, "name": name, "value": value, "per_month": per_month, "share": value / total * 100,
                     **_against_history([h.get(code, ("", ZERO))[1] for h in hist], per_month)})
    big_codes = {code for code, _, _ in big}
    if small > 0:  # everything past the biggest categories is one "Other" row, with its own history
        per_month = small / months_in
        rows.append({"code": "", "name": "Other", "others": True, "value": small, "per_month": per_month,
                     "share": small / total * 100,
                     **_against_history([sum((v for code, (_, v) in h.items() if code not in big_codes), ZERO)
                                         for h in hist], per_month)})
    # Every month of the period itself, clipped to the period (a period of three months gives three).
    period_keys = months_back(last, months_in, fmt_date(first))
    period_months = {k: by_cat(max(parse_month(k)[0], first), min(parse_month(k)[1], last)) for k in period_keys}
    for r in rows:
        r["period_values"] = [sum((v for code, (_, v) in period_months[k].items() if code not in big_codes), ZERO)
                              if r.get("others") else period_months[k].get(r["code"], ("", ZERO))[1]
                              for k in period_keys]
    # The usual month is each month's Money out, refunds included, so it compares like with like with
    # this period's Money out (audit 2026-10-05 #12: a category refunded in full was left out).
    def money_out(start, end) -> Decimal:
        return sum((g.value for g in reporting.spending_by_category(start, end, depth=2)
                    if not code_filter or g.code.startswith(code_filter)), ZERO)
    recent_all = [money_out(*parse_month(k)) for k in keys[-6:]]
    for r in refunds:
        r["share"] = r["value"] / total * 100 if total else ZERO
    return {"rows": rows, "refunds": refunds, "total": total, "small": small, "months_in": months_in, "history_keys": keys,
            "period_keys": period_keys, "per_month": total / months_in,
            "usual_total": sum((r["usual"] or ZERO for r in rows), ZERO),
            "usual_out": sum(recent_all, ZERO) / len(recent_all) if recent_all else None}
