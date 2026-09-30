"""Key notes: each page's answer in up to three short sentences.

Notes only phrase figures that services already computed (the position, cash flow, budget,
forecast, investment report); they never compute a figure of their own beyond comparing two of
them. Names follow lightning/core/figures.py.
"""
from __future__ import annotations

from decimal import Decimal

from lightning.core.money import ZERO, fmt


def note(tone: str, title: str, text: str, href: str = "", action: str = "", popup: bool = False) -> dict:
    return {"tone": tone, "title": title, "text": text, "href": href, "action": action, "popup": popup}


def _signed(value: Decimal) -> str:
    return ("+" if value > 0 else "−" if value < 0 else "") + fmt(abs(value))


def change_in_what_you_own(change: Decimal | None, period_label: str, href: str) -> dict | None:
    if change is None:
        return None
    if change >= 0:
        return note("good", f"What you own grew {fmt(change)}", f"{period_label}. Saving, price changes and new balances together.",
                    href, "See how it adds up")
    return note("attention", f"What you own fell {fmt(-change)}", f"{period_label}. Check spending and prices.",
                href, "See how it adds up")


def kept(flow, period_label: str, href: str) -> dict | None:
    if not flow.inflows and not flow.outflows:
        return None
    if flow.net >= 0 and flow.savings_rate is not None:
        return note("good", f"You kept {flow.savings_rate:.0f}% of money in",
                    f"{fmt(flow.net)} left after spending {fmt(flow.outflows)} · {period_label}.", href, "See where it went")
    return note("attention", f"You spent {fmt(-flow.net)} more than came in",
                f"Money in {fmt(flow.inflows)}, money out {fmt(flow.outflows)} · {period_label}.", href, "See where it went")


def needs_you(attention: list[dict], safe_to_spend: Decimal | None, next_income: str | None) -> dict:
    if attention:
        first = attention[0]
        more = f" and {len(attention) - 1} more" if len(attention) > 1 else ""
        return note("attention", first["label"] + more, first["detail"], first["href"], first.get("action") or "Review",
                    popup=bool(first.get("popup")))
    if safe_to_spend is not None:
        until = f" until {next_income}" if next_income else ""
        return note("info", f"{fmt(safe_to_spend)} safe to spend{until}",
                    "Nothing is due. Free cash less what is promised before your next income.",
                    "/plan", "See cash planning")
    return note("info", "Nothing needs you today", "No bills are due and nothing is waiting for a decision.")


def top_category(groups: list, total: Decimal, href: str) -> dict | None:
    if not groups or not total:
        return None
    top = max(groups, key=lambda g: g["value"])
    share = top["value"] / total * 100
    return note("info", f"{top['label']} took {share:.0f}% of spending", f"{fmt(top['value'])} of {fmt(total)}.",
                top.get("href") or href, "See its transactions")


def compared(spent: Decimal, prior: Decimal | None, prior_label: str) -> dict | None:
    if prior is None:
        return None
    if not prior:
        return note("info", "No earlier spending to compare", f"Nothing was spent in {prior_label}.")
    diff = spent - prior
    if diff > 0:
        return note("attention", f"{fmt(diff)} more than {prior_label}", f"{fmt(spent)} against {fmt(prior)}.")
    if diff < 0:
        return note("good", f"{fmt(-diff)} less than {prior_label}", f"{fmt(spent)} against {fmt(prior)}.")
    return note("info", f"The same as {prior_label}", f"{fmt(spent)} both times.")


def budget_left(left: Decimal, days_left: int, over: list[str], href: str) -> list[dict]:
    """Only what the summary cards don't say: which categories went over plan."""
    if over:
        names = ", ".join(over[:2]) + (f" and {len(over) - 2} more" if len(over) > 2 else "")
        return [note("attention", f"{names} over plan", "Open a category to see what pushed it over.", href, "See categories")]
    if left < 0:
        return [note("attention", f"{fmt(-left)} over plan this month", "Cut back or raise a category's plan.")]
    return []


def per_day(left: Decimal, days_left: int) -> str:
    """Under Left in plan: what it means for the rest of the month."""
    if left < 0:
        return "Spending passed the plan"
    if days_left <= 0:
        return "The month is over"
    if days_left == 1:
        return "Today is the last day of the month"
    return f"About {fmt(left / days_left)} a day for {days_left} days"


def best_class(class_rows: list[dict]) -> dict | None:
    gains = [r for r in class_rows if r["result"]]
    if not gains:
        return None
    best = max(gains, key=lambda r: r["result"])
    if best["result"] <= 0:
        worst = min(gains, key=lambda r: r["result"])
        return note("attention", f"{worst['label']} lost {fmt(-worst['result'])}", "Its prices fell in this period.")
    return note("good", f"{best['label']} earned the most: {_signed(best['result'])}", "Price changes, sales and dividends in this period.")


def at_cost(items: list[dict]) -> dict | None:
    if not items:
        return None
    names = ", ".join(i["asset"] for i in items[:2]) + (f" and {len(items) - 2} more" if len(items) > 2 else "")
    return note("info", f"{len(items)} holding(s) valued at cost", f"{names}: no price yet, so no gain is shown.",
                "/investments/prices", "Update prices")


def lowest_point(forecast) -> dict | None:
    low = forecast.lowest
    if low is None:
        return None
    if low.closing < 0:
        return note("attention", f"Cash may run short in {low.month}", f"The forecast ends {low.month} at {fmt(low.closing)}.",
                    "#plan-forecast", "See the forecast")
    return note("good", f"Lowest point: {fmt(low.closing)}", f"At the end of {low.month}, in the next three months.",
                "#plan-forecast", "See the forecast")


def next_payment(payments: list) -> dict | None:
    upcoming = [p for p in payments if not p.item.is_income]
    if not upcoming:
        return None
    p = upcoming[0]
    return note("attention" if p.status.value == "DUE" else "info",
                f"{p.item.name}: {fmt(p.amount)} {'due since' if p.status.value == 'DUE' else 'due'} {p.due_date}",
                "Next payment going out.", f"/plan/items/{p.item.id}/pay?due={p.due_date}&back=%2Fplan", "Mark paid", popup=True)


def emergency(months: Decimal | None, target: Decimal | None) -> dict | None:
    if months is None:
        return note("info", "Emergency fund not measured yet", "Set your income categories so months covered can be worked out.",
                    "/settings?section=budget", "Open settings")
    tone = "good" if months >= 6 else "attention" if months < 1 else "info"
    return note(tone, f"Emergency fund covers {months:.1f} months", "Of average monthly income. The aim is six.")


def largest_part(donut: dict, what: str, href: str = "") -> dict | None:
    segments = donut.get("segments") or []
    if not segments:
        return None
    top = max(segments, key=lambda s: s["value"])
    return note("info", f"{top['label']} is {top['share']:.0f}% of {what}", f"{fmt(top['value'])} of {fmt(donut['total'])}.",
                href, "See it" if href else "")


def sale_cost(position) -> dict | None:
    held = position.deposits + position.holdings_value
    if not held or position.unvalued:
        return None
    cost = held - position.investments_after_sale
    return note("info", f"Selling everything would cost about {fmt(cost)}",
                "What your sale factors expect to lose against today's value.")


def cash_share(position) -> dict | None:
    if not position.what_you_own or position.what_you_own <= 0:
        return None
    share = position.cash_you_own / position.what_you_own * 100
    text = f"{fmt(position.cash_you_own)} is ready to use; {fmt(position.free_cash)} of it is free cash." if position.free_cash is not None else f"{fmt(position.cash_you_own)} is ready to use."
    return note("good" if share >= 10 else "attention", f"{share:.0f}% of what you own is cash", text, "/plan/reserves", "See cash")


def recurring_summary(monthly_out: Decimal, monthly_in: Decimal, subscriptions_per_year: Decimal) -> dict | None:
    if not monthly_out:
        return None
    subs = f"Subscriptions come to {fmt(subscriptions_per_year)} a year." if subscriptions_per_year else ""
    if not monthly_in:
        return note("info", "Add your income to see its share", "Bills are measured against scheduled income. " + subs)
    share = monthly_out / monthly_in * 100
    return note("attention" if share > 50 else "info", f"Bills take {share:.0f}% of your {fmt(monthly_in)} income", subs)


def loans_summary(loans: list[dict]) -> dict | None:
    if not loans:
        return None
    left = sum((entry["progress"]["still_to_pay"] for entry in loans), ZERO)
    ends = max((entry["progress"]["last_date"] or "" for entry in loans), default="")
    due = sum(len(entry["progress"]["due"]) for entry in loans)
    if due:
        return note("attention", f"{due} loan payment{'s' if due > 1 else ''} due now",
                    f"{fmt(left)} still to pay in all. The last payment is on {ends}.")
    paid = sum(entry["progress"]["paid"] for entry in loans)
    total = sum(entry["progress"]["total"] for entry in loans)
    return note("good" if paid else "info", f"Paid off on {ends}" if ends else f"{fmt(left)} still to pay",
                f"{paid} of {total} payments made.")


def held_for_others(owners: list[dict], total: Decimal | None) -> dict | None:
    if not owners:
        return note("info", "You hold nothing for anyone", "Money you keep for family or friends shows here, apart from what you own.")
    names = sorted({row["owner"] for row in owners})
    who = ", ".join(names[:2]) + (f" and {len(names) - 2} more" if len(names) > 2 else "")
    amount = f"{fmt(total)} in all. " if total else ""
    return note("info", f"You hold money for {who}", amount + "It stays in your accounts but is not counted as yours.")
