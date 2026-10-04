"""Cash planning: Plan · Recurring · Loans · Reserves."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Request

from lightning.categories.domain import Movement
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import LightningError
from lightning.core.figures import label
from lightning.core.money import ZERO, fmt, to_decimal
from lightning.planning.domain import (FREQUENCY_LABELS, KIND_LABELS, RECURRING_KINDS, Frequency, PaymentStatus,
                                       PlanKind)
from lightning.planning.schedule import describe
from lightning.planning.service import LOAN_CATEGORY

from .. import charts, keynotes, visuals
from ..web import container, redirect, render
from . import reserves as reserve_routes

router = APIRouter(prefix="/plan")

FIELDS = ("kind", "name", "amount", "frequency", "interval_count", "start_date", "end_date", "payment_count",
          "account_id", "category_id", "counterparty", "principal", "notes")
TABS = (("plan", "Plan", "/plan"), ("recurring", "Recurring", "/plan/recurring"),
        ("loans", "Loans", "/plan/loans"), ("reserves", "Reserves", "/plan/reserves"))


def _category_options(c, movement: Movement) -> list[dict]:
    by_id = {cat.id: cat for cat in c.categories.tree()}
    options = []
    for cat in by_id.values():
        if not cat.active or cat.is_system or cat.movement != movement or cat.depth != 2:
            continue
        parent = by_id.get(cat.parent_id)
        options.append({"id": cat.id, "label": f"{parent.name} › {cat.name}" if parent else cat.name})
    return sorted(options, key=lambda o: o["label"].casefold())


def _labels(c) -> dict:
    accounts = {a.id: a.name for a in c.accounts.list()}
    categories = {cat.id: cat.name for cat in c.categories.tree()}
    return {"accounts": accounts, "categories": categories}


def _row(c, item, labels, as_of, linked):
    horizon = as_of + timedelta(days=400)
    payments = c.planning.payments(item, item.end_date or fmt_date(horizon), as_of)
    upcoming = next((p for p in payments if p.outstanding), None)
    due = [p for p in payments if p.status == PaymentStatus.DUE]
    last = next((p for p in reversed(payments) if p.status == PaymentStatus.PAID), None)
    review_next = bool(upcoming and upcoming.status == PaymentStatus.UPCOMING and any(
        candidate["id"] not in linked for candidate in c.planning.plausible_candidates(upcoming, as_of)))
    per_year = _per_year(item)
    recent = fmt_date(as_of - timedelta(days=62))
    skipped = [p for p in payments if p.status == PaymentStatus.SKIPPED and p.due_date >= recent]
    reserve_links = c.reserves.links_for_transaction(last.transaction_id) if last and last.transaction_id else []
    return {"item": item, "schedule": describe(item), "next": upcoming, "due": due, "last_paid": last, "skipped": skipped,
            "account": labels["accounts"].get(item.account_id), "category": labels["categories"].get(item.category_id),
            "per_year": per_year, "reserve_links": reserve_links, "review_next": review_next}


def _per_year(item) -> Decimal:
    times = {Frequency.ONCE: 0, Frequency.WEEKLY: Decimal(52), Frequency.MONTHLY: Decimal(12),
             Frequency.QUARTERLY: Decimal(4), Frequency.YEARLY: Decimal(1)}[item.frequency]
    return (item.amount * times / item.interval_count).quantize(Decimal("0.01")) if times else ZERO


def _form_values(form) -> dict:
    return {k: str(form.get(k, "")).strip() for k in FIELDS}


def _save_values(c, values: dict) -> dict:
    """Form fields → service values; a typed "paid to" name becomes a saved Counterparty."""
    name = values.get("counterparty", "")
    party = None
    if name:
        found = c.counterparties.resolve(name)
        party = found["id"] if found else c.counterparties.create(name)
    return {k: v for k, v in values.items() if k != "counterparty"} | {"counterparty_id": party}


def _back(form, default: str) -> str:
    back = str(form.get("back", ""))
    return back if back.startswith("/plan") else default


def _paying_accounts(c):
    """Accounts a bill is paid from or income is paid into: banks and wallets first, then brokerage."""
    order = {"BANK": 0, "CASH": 1, "BROKERAGE": 2}
    return sorted((a for a in c.accounts.list(active_only=True) if a.account_type.value in order),
                  key=lambda a: order[a.account_type.value])


# ------------------------------------------------------------------- tabs
@router.get("")
async def plan_page(request: Request):
    c = container(request)
    day = today()
    forecast = c.forecaster.forecast(day)
    owe = c.planning.what_you_owe(day)
    window_end = day + timedelta(days=30)
    next_payments = [p for p in c.planning.all_payments(window_end, day)
                     if p.status in (PaymentStatus.DUE, PaymentStatus.UPCOMING)]
    plan = visuals.cash_plan(c, forecast, day)
    # Honest numbers (A01): with no income planned there is nothing to forecast from.
    has_income = bool(c.planning.items((PlanKind.INCOME,)))
    stats = _plan_stats(forecast, plan, day, has_income)
    return render(request, "planning/plan.html", tabs=TABS, plan_tab="plan", forecast=forecast, owe=owe, has_income=has_income,
                  notes=[], plan=plan, stats=stats, forecast_chart=visuals.forecast_trend(forecast),
                  next_payments=next_payments, as_of=fmt_date(day), window_end=fmt_date(window_end),
                  has_items=bool(c.planning.items()), labels=_labels(c))


def _plan_stats(f, plan, day, has_income: bool = True) -> list[dict]:
    """Four cards: safe to spend, free cash, what is due before the next income, the lowest point ahead."""
    until = f.next_income_date
    days = (parse_date(until) - day).days if until else 90
    per_day = f.safe_to_spend / days if days > 0 and f.safe_to_spend > 0 else None
    low = f.lowest if has_income else None
    nxt = plan["before_income"][0] if plan["before_income"] else None
    return [
        {"key": "safe", "surface": "hold", "label": label("safe_to_spend"), "value": f.safe_to_spend, "kind": "money",
         "badge": {"tone": "over" if f.safe_to_spend < 0 else "flat", "text": f"until {until}" if until else "3 months"},
         # A per-day figure only helps over a week or more; the day before payday it reads as "404,567 a day".
         "sub": (f"About {fmt(per_day, 0)} a day for {days} days" if per_day is not None and days >= 7
                 else f"Until your next income on {until}" if per_day is not None and until
                 else "Promised payments are larger than your free cash" if f.safe_to_spend < 0 else "Nothing left to spend safely"),
         "href": "#plan-build"},
        {"key": "free", "surface": "hold", "label": label("free_cash"), "value": f.free_cash, "kind": "money",
         "sub": "Cash you own after reserves and bills due · today", "href": "/"},
        {"key": "before", "surface": "out", "label": label("payments_before_next_income"), "value": plan["before_total"], "kind": "money",
         "badge": {"tone": "flat", "text": f"{len(plan['before_income'])} payment{'s' if len(plan['before_income']) != 1 else ''}"},
         "sub": f"Next: {nxt.item.name} · {nxt.due_date}" if nxt else "Nothing is due before then",
         "href": "#plan-next"},
        {"key": "low", "surface": "over" if low and low.closing < 0 else "hold", "label": "Lowest point ahead", "value": low.closing if low else None, "kind": "money",
         "empty": "—", "badge": {"tone": "over" if low and low.closing < 0 else "flat", "text": low.month if low else "—"},
         "sub": "Cash at its lowest month end in the forecast" if low else "Add your bills and income to see it",
         "spark": plan["forecast_spark"], "spark_tone": "over" if low and low.closing < 0 else "hold", "href": "#plan-forecast"},
    ]


@router.get("/recurring")
async def recurring_page(request: Request):
    c = container(request)
    day = today()
    c.planning.match_payments(day)
    labels = _labels(c)
    linked = c.planning.linked_transaction_ids()
    rows = [_row(c, item, labels, day, linked) for item in c.planning.items(RECURRING_KINDS)]
    stopped = c.planning.items(RECURRING_KINDS, active_only=False)
    stopped = [i for i in stopped if not i.active]
    subscriptions = sum((r["per_year"] for r in rows if r["item"].kind == PlanKind.SUBSCRIPTION), ZERO)
    monthly_out = sum((r["per_year"] for r in rows if not r["item"].is_income), ZERO) / 12
    monthly_in = sum((r["per_year"] for r in rows if r["item"].is_income), ZERO) / 12
    notes = [n for n in (keynotes.recurring_summary(monthly_out, monthly_in, subscriptions),) if n]
    bill_bars = charts.bars([{"label": r["item"].name, "value": r["per_year"] / 12,
                              "note": r["item"].kind_label + (" · " + r["category"] if r["category"] else "")}
                             for r in rows if not r["item"].is_income])
    return render(request, "planning/recurring.html", tabs=TABS, plan_tab="recurring", rows=rows, stopped=stopped,
                  notes=notes, bill_bars=bill_bars,
                  suggestions=c.planning.suggestions(day), subscriptions_per_year=subscriptions,
                  monthly_out=monthly_out, monthly_in=monthly_in, labels=labels, as_of=fmt_date(day))


@router.get("/loans")
async def loans_page(request: Request):
    c = container(request)
    day = today()
    c.planning.match_payments(day)
    labels = _labels(c)
    loans = [{"item": item, "progress": c.planning.loan_progress(item, day), "schedule": describe(item),
              "account": labels["accounts"].get(item.account_id)} for item in c.planning.items((PlanKind.LOAN,))]
    for entry in loans:
        entry["meter"] = charts.meter(entry["progress"]["paid_amount"], entry["progress"]["total_amount"])
    notes = [n for n in (keynotes.loans_summary(loans),) if n]
    return render(request, "planning/loans.html", tabs=TABS, plan_tab="loans", loans=loans, notes=notes,
                  still_to_pay=sum((l["progress"]["still_to_pay"] for l in loans), ZERO), as_of=fmt_date(day))


@router.get("/reserves")
async def reserves_page(request: Request):
    return render(request, "reserves.html", tabs=TABS, plan_tab="reserves", **reserve_routes._context(request))


# ------------------------------------------------------------------ items
def _item_form(request: Request, c, values: dict, item=None, error: str = "", error_field: str = "",
               status_code: int = 200, back: str = "/plan/recurring"):
    kind = values.get("kind") or PlanKind.BILL.value
    movement = Movement.INFLOW if kind == PlanKind.INCOME.value else Movement.OUTFLOW
    kinds = [(PlanKind.LOAN.value, "Loan or installment plan")] if kind == PlanKind.LOAN.value else [
        (k.value, KIND_LABELS[k]) for k in RECURRING_KINDS]
    return render(request, "planning/item_form.html", status_code=status_code, values=values, item=item,
                  has_history=bool(item) and c.planning.has_history(item.id),
                  kinds=kinds, is_loan=kind == PlanKind.LOAN.value,
                  frequencies=[(f.value, FREQUENCY_LABELS[f]) for f in Frequency],
                  accounts=_paying_accounts(c),
                  categories=_category_options(c, movement), counterparties=c.counterparties.list_active(),
                  error=error, error_field=error_field, back=back)


@router.get("/items/new")
async def new_item(request: Request):
    c = container(request)
    q = request.query_params
    values = {k: str(q.get(k, "")) for k in FIELDS}
    values["kind"] = (values["kind"] or "BILL").upper()
    values["frequency"] = values["frequency"] or "MONTHLY"
    values["interval_count"] = values["interval_count"] or "1"
    values["start_date"] = values["start_date"] or fmt_date(today())
    if values["kind"] == "LOAN" and not values["category_id"]:
        try:
            values["category_id"] = str(c.categories.get_by_code(LOAN_CATEGORY).id)
        except LightningError:
            pass
    back = "/plan/loans" if values["kind"] == "LOAN" else "/plan/recurring"
    return _item_form(request, c, values, back=str(q.get("back", back)))


@router.post("/items")
async def create_item(request: Request):
    c = container(request)
    form = await request.form()
    values = _form_values(form)
    back = _back(form, "/plan/loans" if values["kind"] == "LOAN" else "/plan/recurring")
    try:
        item_id = c.planning.create(**_save_values(c, values))
    except LightningError as exc:
        return _item_form(request, c, values, error=exc.message, error_field=exc.field or "", status_code=400, back=back)
    message = f"{values['name']} added."
    if str(form.get("past_due", "paid")) == "paid":
        moved = c.planning.start_after_paid(item_id)
        if moved:
            message = f"{values['name']} added. Already paid, so the next one is due {moved}."
    return redirect(back, message)


@router.get("/items/{item_id:int}/edit")
async def edit_item(request: Request, item_id: int):
    c = container(request)
    item = c.planning.get(item_id)
    party = c.counterparties.get(item.counterparty_id)["name"] if item.counterparty_id else ""
    values = {"kind": item.kind.value, "name": item.name, "amount": f"{item.amount:.2f}",
              "frequency": item.frequency.value, "interval_count": str(item.interval_count),
              "start_date": item.start_date, "end_date": item.end_date or "",
              "payment_count": str(item.payment_count or ""), "account_id": str(item.account_id or ""),
              "category_id": str(item.category_id or ""), "counterparty": party,
              "principal": f"{item.principal:.2f}" if item.principal else "", "notes": item.notes}
    back = "/plan/loans" if item.kind == PlanKind.LOAN else "/plan/recurring"
    return _item_form(request, c, values, item=item, back=back)


@router.post("/items/{item_id:int}/edit")
async def update_item(request: Request, item_id: int):
    c = container(request)
    item = c.planning.get(item_id)
    form = await request.form()
    values = _form_values(form)
    back = _back(form, "/plan/loans" if item.kind == PlanKind.LOAN else "/plan/recurring")
    try:
        c.planning.update(item_id, **_save_values(c, values))
    except LightningError as exc:
        return _item_form(request, c, values, item=item, error=exc.message, error_field=exc.field or "",
                          status_code=400, back=back)
    return redirect(back, f"{values['name']} saved.")


@router.post("/items/{item_id:int}/amount")
async def set_item_amount(request: Request, item_id: int):
    c = container(request)
    form = await request.form()
    item = c.planning.get(item_id)
    try:
        c.planning.set_amount(item_id, str(form.get("amount", "")))
    except LightningError as exc:
        return redirect(_back(form, "/plan/recurring"), exc.message)
    return redirect(_back(form, "/plan/recurring"), f"{item.name} is now planned at {fmt(to_decimal(str(form.get('amount')), 'amount'))}.")


@router.post("/items/{item_id:int}/delete")
async def delete_item(request: Request, item_id: int):
    c = container(request)
    form = await request.form()
    item = c.planning.get(item_id)
    message = c.planning.remove(item_id)
    return redirect(_back(form, "/plan/loans" if item.kind == PlanKind.LOAN else "/plan/recurring"), message)


# --------------------------------------------------------------- payments
@router.get("/items/{item_id:int}/pay")
async def pay_form(request: Request, item_id: int, error: str = ""):
    c = container(request)
    item = c.planning.get(item_id)
    due = str(request.query_params.get("due", ""))
    payment = next((p for p in c.planning.payments(item, due or fmt_date(today()), today()) if p.due_date == due), None)
    if not payment:
        return redirect("/plan", "That payment is not on the schedule.")
    exact = c.planning.candidates(payment)
    others = c.planning.plausible_candidates(payment)
    linked = c.planning.linked_transaction_ids()
    return render(request, "planning/pay.html", item=item, payment=payment,
                  exact=[r for r in exact if r["id"] not in linked], others=[r for r in others if r["id"] not in linked][:8],
                  accounts=_paying_accounts(c),
                  back=str(request.query_params.get("back", "/plan")), today=fmt_date(today()), error=error)


@router.post("/items/{item_id:int}/pay")
async def settle_payment(request: Request, item_id: int):
    c = container(request)
    form = await request.form()
    due = str(form.get("due", ""))
    action = str(form.get("outcome", ""))
    back = _back(form, "/plan")
    item = c.planning.get(item_id)
    try:
        if action == "link":
            c.planning.mark_paid(item_id, due, int(str(form.get("transaction_id", "0"))))
            message = f"{item.name} · {due} marked paid."
        elif action == "record":
            c.planning.record_payment(item_id, due, str(form.get("date_paid", "")), str(form.get("amount", "")),
                                      int(str(form.get("account_id"))) if str(form.get("account_id", "")).isdigit() else None)
            message = f"{item.name} · {due} recorded and marked paid."
            paid = to_decimal(str(form.get("amount", "")), "amount")
            if paid != item.amount and item.frequency != Frequency.ONCE:
                message += (f" You paid {fmt(paid)} instead of {fmt(item.amount)}; Recurring offers to use "
                            f"{fmt(paid)} from now on.")
        elif action == "skip":
            c.planning.skip(item_id, due)
            message = (f"{item.name} · {due} moved to the end of the loan." if item.kind == PlanKind.LOAN
                       else f"{item.name} · {due} skipped.")
        elif action == "reopen":
            was_skipped = any(p.due_date == due and p.status == PaymentStatus.SKIPPED
                              for p in c.planning.payments(item, due, today()))
            c.planning.reopen(item_id, due)
            message = f"{item.name} · {due} is " + ("back on the schedule." if was_skipped else "unpaid again.")
        else:
            raise LightningError("Choose how this payment was settled.")
    except LightningError as exc:
        return redirect(f"/plan/items/{item_id}/pay?due={due}&back={back}", exc.message)
    return redirect(back, message)
