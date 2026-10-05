"""One review inbox: every decision Lightning is waiting on, in one ordered list.

The Overview's Needs you shows it. Each item names what needs a decision, gives one line of
detail, and links to the page that settles it, with the action's name. Nothing here changes data.
Reconciliation diagnostics stay in the Integrity checks view; this lists actions a user can take.
"""
from __future__ import annotations

import json
from datetime import date

from lightning.core.dates import fmt_date, month_of
from lightning.core.money import ZERO, fmt as _fmt
from lightning.transactions.domain import TxnFilter
from lightning.workflows.market_prices import missing_prices


def fmt(value, places: int = 0, signed: bool = False) -> str:
    """Reporting text rounds to the nearest unit (stored values keep their decimals)."""
    return _fmt(value, places, signed)


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


class ReviewInbox:
    def __init__(self, container):
        self.c = container

    def items(self, on: date) -> list[dict]:
        """Everything waiting on the user on `on`, most urgent first (priority 0, then 1, then 2)."""
        c = self.c
        items = [{"label": "Missing valuation", "detail": item, "href": "/investments/prices", "priority": 0}
                 for item in c.reporting.net_worth(on).unvalued]
        items.extend(self._statements())
        items.extend(self._uncategorized())
        for reserve in c.reserves.list_active():
            if reserve.get("due_date") and reserve["due_date"] < fmt_date(on) and reserve["effective_allocated"] > ZERO:
                items.append({"label": f"{reserve['name']} is past its date",
                              "detail": f"Due {reserve['due_date']} · {fmt(reserve['effective_allocated'])} {c.base_currency} still set aside.",
                              "href": "/plan/reserves", "priority": 2})
        # Payments that are due and unpaid on this day, whatever period a page shows.
        for payment in c.planning.what_you_owe(on).bills_due_items:
            kind = "Loan payment due" if payment.item.kind.value == "LOAN" else "Bill due"
            items.append({"label": f"{kind}: {payment.item.name}",
                          "detail": f"Due {payment.due_date} · {fmt(payment.amount)} {c.base_currency} · not paid yet.",
                          "href": f"/plan/items/{payment.item.id}/pay?due={payment.due_date}&back=%2F",
                          "popup": True, "action": "Mark paid", "priority": 1})
        lowest = c.forecaster.forecast(on).lowest
        if lowest is not None and lowest.closing < ZERO:
            items.append({"label": "Cash may run short",
                          "detail": f"The cash forecast ends {lowest.month} at {fmt(lowest.closing)} {c.base_currency}.",
                          "href": "/plan", "priority": 1})
        # Honest numbers: a holding priced more than two months ago is shown at an old value.
        # Month-end prices the price files lack (a fund they do not cover, a stock listed later): typed by hand.
        missing = missing_prices(c)
        if missing:
            by_name: dict[str, list[str]] = {}
            for name, day in missing:
                by_name.setdefault(name, []).append(date.fromisoformat(day).strftime("%B %Y"))
            named = "; ".join(f"{name}, {', '.join(months[:3])}{' and more' if len(months) > 3 else ''}"
                              for name, months in list(by_name.items())[:2])
            more = f"; and {len(by_name) - 2} more" if len(by_name) > 2 else ""
            items.append({"label": _plural(len(missing), "price missing", "prices missing"),
                          "detail": f"{named}{more}.", "href": "/investments/prices",
                          "action": "Enter prices", "priority": 2})
        stale = c.reporting.stale_prices(on)
        if stale:
            named = ", ".join(f"{row['name']} ({row['price_date']})" for row in stale[:2])
            more = f" and {len(stale) - 2} more" if len(stale) > 2 else ""
            items.append({"label": "Prices are out of date",
                          "detail": f"Last priced: {named}{more}. Values use these old prices.",
                          "href": "/investments/prices", "action": "Update prices", "priority": 2})
        for section in c.budgets.month_view(month_of(on)).sections:
            if section.planned_actual > section.available:
                items.append({"label": f"{section.name} over plan",
                              "detail": f"{fmt(section.planned_actual - section.available)} {c.base_currency} over this month's plan.",
                              "href": "/budget", "priority": 2})
        # A category's own plan below what is already scheduled in it: the bill will overrun the plan.
        for row in c.budgets.below_scheduled(month_of(on)):
            items.append({"label": f"{row['name']} is planned below its bills",
                          "detail": f"Planned {fmt(row['planned'])} {c.base_currency}; bills and loan payments "
                                    f"scheduled this month come to {fmt(row['scheduled'])}.",
                          "href": f"/budget?month={month_of(on)}", "action": "Change the plan", "priority": 2})
        # The month's plan against the savings target and dated goals (one check: HealthService.plan_check).
        check = c.health.plan_check(month_of(on))
        if check.planned is not None and check.over_by and check.planned_savings_rate is not None:
            if check.short_for == "goals":
                items.append({"label": "This month's plan is short for your goals" if check.goals else
                                       "This month's plan is short for your emergency fund",
                              "detail": f"It leaves {fmt(check.plan_saves)} {c.base_currency}; {check.needs_label} "
                                        f"{fmt(check.needs)}. Plan {fmt(check.over_by)} less.",
                              "href": f"/budget?month={check.month}", "priority": 2})
            else:
                items.append({"label": "This month's plan is below your savings target",
                              "detail": f"It saves {fmt(check.planned_savings_rate)}% of income; your target is "
                                        f"{fmt(check.target_percent)}%. Plan {fmt(check.over_by)} {c.base_currency} less.",
                              "href": f"/budget?month={check.month}", "priority": 2})
        return sorted(items, key=lambda item: item["priority"])

    def _statements(self) -> list[dict]:
        """One item per statement left half reviewed, opening at its first waiting row."""
        found = []
        for batch in self.c.bank_imports.waiting_all():
            try:
                source = json.loads(batch["first_raw_json"])
            except (TypeError, ValueError):
                source = {}
            parsed = source.get("parsed") if isinstance(source, dict) else None
            day = (parsed.get("Date") if isinstance(parsed, dict) else None) or str(batch["created_at"])[:10]
            found.append({"label": "Imported activity needs a decision",
                          "detail": f"{batch['file_name']} · {_plural(batch['waiting'], 'row waits', 'rows wait')}"
                                    f" · from row {batch['first_row_number']} · {day}.",
                          "href": f"/accounts/{batch['account_id']}/import/{batch['batch_id']}"
                                  f"#import-row-{batch['first_row_id']}",
                          "action": "Finish the import", "priority": 1})
        return found

    def _uncategorized(self) -> list[dict]:
        """Posted activity filed as Unaccounted: an import posted it before anyone chose a category."""
        found = []
        for code, one, many in (("EXP.UNACCOUNTED", "payment has no category", "payments have no category"),
                                ("INC.UNACCOUNTED", "incoming amount has no category", "incoming amounts have no category")):
            category = self.c.categories.get_by_code(code)
            _, total = self.c.transactions.find(TxnFilter(category_ids=[category.id], limit=1))
            if total:
                found.append({"label": _plural(total, one, many).capitalize(),
                              "detail": "Choose a category for each, so the budget and reports count it.",
                              "href": f"/transactions?category_id={category.id}",
                              "action": "Sort them out", "priority": 2})
        return found
