"""Planned items, their payments, and what you owe."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from lightning.core.dates import fmt_date, parse_date, parse_month, today
from lightning.core.errors import NotFoundError, ValidationError
from lightning.core.money import ZERO, from_e6, to_decimal
from lightning.database.connection import Database

from .domain import (Frequency, Payment, PaymentStatus, PlanKind, PlannedItem, WhatYouOwe)
from .repository import PlanningRepository
from .schedule import payment_dates

# A posted transaction settles a scheduled payment when it lands within this many days of the
# due date and its amount is within the tolerance (loans are fixed instalments).
MATCH_WINDOW_DAYS = 7
SUGGESTION_WINDOW_DAYS = 45
MATCH_TOLERANCE = {PlanKind.LOAN: Decimal("0.01")}
DEFAULT_TOLERANCE = Decimal("0.10")
SUGGESTION_TOLERANCE = Decimal("0.50")
SUGGESTION_MINIMUM = Decimal("50")  # recurring amounts below this are not suggested
LOAN_CATEGORY = "EXP.SYSTEM.LOANS"


class PlanningService:
    def __init__(self, db: Database, accounts, categories, counterparties, transactions):
        self.db = db
        self.repo = PlanningRepository(db)
        self.accounts = accounts
        self.categories = categories
        self.counterparties = counterparties
        self.transactions = transactions

    # ------------------------------------------------------------------ items
    def items(self, kinds: tuple[PlanKind, ...] | None = None, active_only: bool = True) -> list[PlannedItem]:
        items = self.repo.items(active_only)
        return [i for i in items if kinds is None or i.kind in kinds]

    def get(self, item_id: int) -> PlannedItem:
        item = self.repo.item(item_id)
        if not item:
            raise NotFoundError("That planned item was not found.")
        return item

    def create(self, **values) -> int:
        clean = self._validate(values)
        with self.db.transaction():
            return self.repo.insert(clean)

    def update(self, item_id: int, **values) -> None:
        self.get(item_id)
        clean = self._validate(values)
        with self.db.transaction():
            self.repo.update(item_id, clean)

    def start_after_paid(self, item_id: int, as_of: date | None = None) -> str | None:
        """The user says payments dated up to today are already paid: link any posted transaction
        that matches, and start the schedule at the next date instead of showing the rest as due.
        Returns the new first due date, or None when nothing changed. Not for loans."""
        day = as_of or today()
        self.match_payments(day)
        item = self.get(item_id)
        if item.kind == PlanKind.LOAN:
            return None
        payments = self.payments(item, fmt_date(day), day)
        if any(p.status == PaymentStatus.PAID for p in payments) or not any(
                p.status == PaymentStatus.DUE for p in payments):
            return None
        later = [d for _, d in payment_dates(item, fmt_date(day + timedelta(days=400))) if d > fmt_date(day)]
        if not later:
            return None
        with self.db.transaction():
            self.repo.set_start(item_id, later[0])
        return later[0]

    def set_amount(self, item_id: int, amount) -> None:
        """Plan every later payment at a new amount (for example after paying a higher rent)."""
        value = to_decimal(amount, "amount")
        if value <= ZERO:
            raise ValidationError("Enter an amount above zero.", "amount")
        self.get(item_id)
        with self.db.transaction():
            self.repo.set_amount(item_id, value)

    def has_history(self, item_id: int) -> bool:
        return self.repo.has_payments(item_id)

    def remove(self, item_id: int) -> str:
        """Delete an item nobody paid yet; otherwise stop it and keep its history."""
        item = self.get(item_id)
        with self.db.transaction():
            if self.repo.has_payments(item_id):
                self.repo.set_active(item_id, False)
                return f"{item.name} stopped. Its paid history is kept."
            self.repo.delete(item_id)
        return f"{item.name} deleted."

    # --------------------------------------------------------------- payments
    def payments(self, item: PlannedItem, until: str | date, as_of: date | None = None) -> list[Payment]:
        day = as_of or today()
        settled = self.repo.settled()
        original = item
        if item.kind == PlanKind.LOAN and item.payment_count:
            # A skipped loan payment is still owed: it moves to the end of the loan.
            skipped = sum(1 for (item_id, _), row in settled.items()
                          if item_id == item.id and row["status"] == PaymentStatus.SKIPPED.value)
            if skipped:
                item = replace(item, payment_count=item.payment_count + skipped)
        out = []
        for number, due in payment_dates(item, until):
            row = settled.get((item.id, due))
            if row:
                status = PaymentStatus(row["status"])
            else:
                status = PaymentStatus.DUE if due <= fmt_date(day) else PaymentStatus.UPCOMING
            paid = from_e6(row["amount_e6"]) if row and status == PaymentStatus.PAID and row["amount_e6"] else None
            out.append(Payment(original, due, number, status, row["transaction_id"] if row else None, paid))
        return out

    def all_payments(self, until: str | date, as_of: date | None = None,
                     kinds: tuple[PlanKind, ...] | None = None) -> list[Payment]:
        payments = [p for item in self.items(kinds) for p in self.payments(item, until, as_of)]
        return sorted(payments, key=lambda p: (p.due_date, p.item.name.casefold()))

    def match_payments(self, as_of: date | None = None) -> int:
        """Link each due or near-due payment to the one posted transaction that clearly settles it."""
        day = as_of or today()
        linked = self.repo.linked_transaction_ids()
        count = 0
        with self.db.transaction():
            for item in self.items():
                if not (item.category_id or item.counterparty_id):
                    continue  # nothing to recognise a payment by; the user marks it paid
                horizon = day + timedelta(days=MATCH_WINDOW_DAYS)
                for payment in self.payments(item, horizon, day):
                    if payment.status not in (PaymentStatus.DUE, PaymentStatus.UPCOMING):
                        continue
                    found = [c for c in self.candidates(payment, day) if c["id"] not in linked]
                    if len(found) == 1:
                        self.repo.settle(item.id, payment.due_date, "PAID", found[0]["id"], found[0]["amount"])
                        linked.add(found[0]["id"])
                        count += 1
        return count

    def candidates(self, payment: Payment, as_of: date | None = None, loose: bool = False) -> list[dict]:
        """Transactions that could settle ``payment``; ``loose`` widens the search for manual linking."""
        item, day = payment.item, as_of or today()
        due = date.fromisoformat(payment.due_date)
        window = 31 if loose else MATCH_WINDOW_DAYS
        rows = self.repo.candidates(item.is_income, item.account_id,
                                    None if loose else item.category_id,
                                    None if loose else item.counterparty_id,
                                    fmt_date(due - timedelta(days=window)),
                                    fmt_date(min(due + timedelta(days=window), day)))
        if loose:
            # Wider window for manual linking, but only plausible rows: the same counterparty
            # or category, or an amount within 10%. A 2,000 gift is not a 2,500 loan payment.
            return [r for r in rows if abs(r["amount"] - item.amount) <= item.amount * DEFAULT_TOLERANCE
                    or (item.counterparty_id and r["counterparty_id"] == item.counterparty_id)
                    or (item.category_id and item.category_id in r["category_ids"])]
        tolerance = MATCH_TOLERANCE.get(item.kind, DEFAULT_TOLERANCE)
        return [r for r in rows if abs(r["amount"] - item.amount) <= item.amount * tolerance]

    def plausible_candidates(self, payment: Payment, as_of: date | None = None) -> list[dict]:
        """Read-only wider suggestions; a user must explicitly choose one to link it."""
        item, day = payment.item, as_of or today()
        if not (item.counterparty_id or item.category_id):
            return []
        due = date.fromisoformat(payment.due_date)
        rows = self.repo.candidates(
            item.is_income, item.account_id, item.category_id, item.counterparty_id,
            fmt_date(due - timedelta(days=SUGGESTION_WINDOW_DAYS)),
            fmt_date(min(due + timedelta(days=SUGGESTION_WINDOW_DAYS), day)))
        strict = {row["id"] for row in self.candidates(payment, day)}
        return [row for row in rows if row["id"] not in strict
                and abs(row["amount"] - item.amount) <= item.amount * SUGGESTION_TOLERANCE]

    def linked_transaction_ids(self) -> set[int]:
        return self.repo.linked_transaction_ids()

    def mark_paid(self, item_id: int, due_date: str, transaction_id: int) -> None:
        item = self.get(item_id)
        try:
            due = date.fromisoformat(due_date)
        except (TypeError, ValueError):
            raise ValidationError("Choose a scheduled payment date.") from None
        if not any(payment.due_date == due_date for payment in self.payments(item, due)):
            raise ValidationError("That date is not on this payment schedule.")
        if transaction_id in self.repo.linked_transaction_ids():
            raise ValidationError("That transaction already settles another payment.")
        txn = self.repo.payment_transaction(transaction_id, item.is_income, item.account_id,
                                           item.category_id, item.counterparty_id)
        if not txn:
            raise ValidationError("Choose a posted, owned transaction for this account and payment.")
        if abs((date.fromisoformat(txn["date"]) - due).days) > SUGGESTION_WINDOW_DAYS:
            raise ValidationError("That transaction is too far from the scheduled payment date.")
        if abs(txn["amount"] - item.amount) > item.amount * SUGGESTION_TOLERANCE:
            raise ValidationError("That transaction amount is too far from the planned payment.")
        with self.db.transaction():
            self.repo.settle(item.id, due_date, "PAID", transaction_id, txn["amount"])

    def record_payment(self, item_id: int, due_date: str, date_paid: str, amount, account_id: int | None) -> int:
        """Post the payment as a normal transaction and link it."""
        item = self.get(item_id)
        account = account_id or item.account_id
        if not account:
            raise ValidationError("Choose the account the money moved through.", "account_id")
        if not item.category_id:
            raise ValidationError(f"Give {item.name} a category first, so its payments land in the right place.",
                                  "category_id")
        value = to_decimal(amount, "amount")
        if value <= ZERO:
            raise ValidationError("Enter the amount paid.", "amount")
        party = self.counterparties.get(item.counterparty_id)["name"] if item.counterparty_id else item.name
        with self.db.transaction():
            record = self.transactions.record_inflow if item.is_income else self.transactions.record_outflow
            txn = record(fmt_date(parse_date(date_paid)), int(account), value, item.category_id,
                         counterparty=party, notes=f"{item.kind_label} · {item.name}")
            self.repo.settle(item.id, due_date, "PAID", txn.id, value)
        return txn.id

    def skip(self, item_id: int, due_date: str) -> None:
        item = self.get(item_id)
        with self.db.transaction():
            self.repo.settle(item.id, due_date, "SKIPPED", None, ZERO)

    def reopen(self, item_id: int, due_date: str) -> None:
        self.get(item_id)
        with self.db.transaction():
            self.repo.unsettle(item_id, due_date)

    def suggestions(self, as_of: date | None = None) -> list[dict]:
        """Payments that look monthly in the last six months and aren't planned yet.

        Suggestions only: nothing is added until the user chooses to track it.
        """
        from statistics import median
        day = as_of or today()
        start = date(day.year - (1 if day.month <= 6 else 0), (day.month - 7) % 12 + 1, 1)
        groups: dict[tuple, list[dict]] = {}
        for row in self.repo.history(fmt_date(start), fmt_date(day)):
            groups.setdefault((row["counterparty_id"], row["effect"]), []).append(row)
        planned = {i.counterparty_id for i in self.items()} | {
            i.counterparty_id for i in self.items(active_only=False) if not i.active}
        out = []
        for (party, effect), rows in groups.items():
            if party in planned:
                continue
            months = {r["date"][:7] for r in rows}
            if len(months) < 3 or len(rows) > len(months) + 1:
                continue  # repeats monthly, not several times a month
            amounts = [r["amount"] for r in rows]
            typical = median(amounts)
            if typical < SUGGESTION_MINIMUM or any(abs(a - typical) > typical * Decimal("0.2") for a in amounts):
                continue  # too small to plan around (bank fees), or the amount varies too much
            latest = rows[-1]
            out.append({"counterparty_id": party, "name": latest["counterparty"],
                        "kind": "INCOME" if effect == "INFLOW" else "BILL", "amount": Decimal(typical).quantize(Decimal("0.01")),
                        "day": int(median(int(r["date"][8:]) for r in rows)), "months": len(months),
                        "account_id": latest["account_id"], "category_id": latest["category_id"],
                        "last_date": latest["date"]})
        return sorted(out, key=lambda s: (-s["months"], -s["amount"]))

    # -------------------------------------------------------------- what you owe
    def what_you_owe(self, as_of: date | None = None) -> WhatYouOwe:
        """Certain obligations only: unpaid payments already due, and loans still to pay."""
        day = as_of or today()
        outgoing = tuple(k for k in PlanKind if k != PlanKind.INCOME)
        due = [p for p in self.all_payments(day, day, outgoing) if p.status == PaymentStatus.DUE]
        loans_left = ZERO
        for item in self.items((PlanKind.LOAN,)):
            end = item.end_date or "2999-12-31"
            loans_left += sum((p.amount for p in self.payments(item, end, day) if p.outstanding), ZERO)
        return WhatYouOwe(bills_due=sum((p.amount for p in due), ZERO), loans_still_to_pay=loans_left,
                          bills_due_items=due)

    def loan_payments_by_category(self, month: str) -> dict[int, Decimal]:
        """Loan payments scheduled in a month (paid, due or upcoming; not skipped), by category."""
        first, last = parse_month(month)
        out: dict[int, Decimal] = {}
        for item in self.items((PlanKind.LOAN,)):
            if item.category_id is None:
                continue
            for p in self.payments(item, last):
                if p.due_date >= fmt_date(first) and p.status != PaymentStatus.SKIPPED:
                    out[item.category_id] = out.get(item.category_id, ZERO) + p.amount
        return out

    def loan_progress(self, item: PlannedItem, as_of: date | None = None) -> dict:
        payments = self.payments(item, item.end_date or "2999-12-31", as_of)
        paid = [p for p in payments if p.status == PaymentStatus.PAID]
        left = [p for p in payments if p.outstanding]
        skipped = [p for p in payments if p.status == PaymentStatus.SKIPPED]
        return {"total": len(payments) - len(skipped), "paid": len(paid), "left": len(left), "skipped": skipped,
                "still_to_pay": sum((p.amount for p in left), ZERO),
                "paid_amount": sum((p.amount for p in paid), ZERO),
                "total_amount": sum((p.amount for p in paid + left), ZERO),  # paid + still to pay
                "next": next((p for p in payments if p.outstanding), None),
                "due": [p for p in payments if p.status == PaymentStatus.DUE],
                "last_date": payments[-1].due_date if payments else None}

    # --------------------------------------------------------------- validation
    def _validate(self, values: dict) -> dict:
        try:
            kind = PlanKind(str(values.get("kind", "")).upper())
        except ValueError:
            raise ValidationError("Choose bill, subscription, income or loan.", "kind") from None
        name = str(values.get("name", "")).strip()
        if not name:
            raise ValidationError("Give it a name, like Rent or Car loan.", "name")
        amount = to_decimal(values.get("amount"), "amount")
        if amount <= ZERO:
            raise ValidationError("Enter the amount of each payment.", "amount")
        try:
            frequency = Frequency(str(values.get("frequency", "MONTHLY")).upper())
        except ValueError:
            raise ValidationError("Choose how often it repeats.", "frequency") from None
        interval = int(str(values.get("interval_count") or 1))
        if not 1 <= interval <= 52:
            raise ValidationError("Repeat every 1 to 52 periods.", "interval_count")
        start = fmt_date(parse_date(values.get("start_date"), "start_date"))
        end_raw = str(values.get("end_date") or "").strip()
        end = fmt_date(parse_date(end_raw, "end_date")) if end_raw else None
        if end and end < start:
            raise ValidationError("The last date must be on or after the first date.", "end_date")
        count_raw = str(values.get("payment_count") or "").strip()
        count = int(count_raw) if count_raw else None
        if count is not None and not 1 <= count <= 600:
            raise ValidationError("Enter 1 to 600 payments.", "payment_count")
        if kind == PlanKind.LOAN and count is None and end is None:
            raise ValidationError("Enter how many payments are left, or the last payment date.", "payment_count")
        principal_raw = str(values.get("principal") or "").strip()
        principal = to_decimal(principal_raw, "principal") if principal_raw else None
        account_id = self._id(values.get("account_id"))
        if account_id:
            self.accounts.get(account_id)
        category_id = self._id(values.get("category_id"))
        if category_id:
            self.categories.get(category_id)
        elif kind == PlanKind.LOAN:
            # Loan payments count as spending; without a choice they land in Loan payments.
            try:
                category_id = self.categories.get_by_code(LOAN_CATEGORY).id
            except NotFoundError:
                category_id = None
        counterparty_id = self._id(values.get("counterparty_id"))
        if counterparty_id:
            self.counterparties.get(counterparty_id)
        return {"kind": kind.value, "name": name, "amount": amount, "frequency": frequency.value,
                "interval_count": interval, "start_date": start, "end_date": end, "payment_count": count,
                "account_id": account_id, "category_id": category_id, "counterparty_id": counterparty_id,
                "principal": principal, "notes": str(values.get("notes") or "").strip()}

    @staticmethod
    def _id(value) -> int | None:
        text = str(value or "").strip()
        return int(text) if text.isdigit() else None
