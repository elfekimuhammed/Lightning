"""Public API of the transactions module: record, edit, void, find.

Every write goes through ``validate_posting`` (core/ledger.py) before it is saved.
Edits happen in place — the ref never changes — and the audit log keeps before/after.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal

from lightning.accounts.domain import Account
from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.categories.domain import Movement
from lightning.categories.service import CategoryService
from lightning.core.dates import fmt_date, parse_date
from lightning.core.errors import NotFoundError, ValidationError
from lightning.core.ledger import Effect, PostingLine, validate_posting
from lightning.core.money import ONE, ZERO, check_places, fmt, to_decimal
from lightning.core.refs import DOC_LABELS, DocType, format_ref, ref_prefix
from lightning.database.audit import AuditLog
from lightning.database.connection import Database

from .domain import Transaction, TxnFilter, TxnSource, TxnStatus, TxnSummary
from .repository import TransactionRepository

EDITABLE_TYPES = {DocType.IN, DocType.OUT, DocType.TRF}


class TransactionService:
    def __init__(
        self,
        db: Database,
        accounts: AccountService,
        assets: AssetService,
        categories: CategoryService,
        audit: AuditLog,
        base_currency: str,
    ):
        self.db = db
        self.repo = TransactionRepository(db)
        self.accounts = accounts
        self.assets = assets
        self.categories = categories
        self.audit = audit
        self.base_currency = base_currency

    # ======================================================================
    # Recording
    # ======================================================================
    def record_inflow(self, date: str, account_id: int, amount, category_id: int, description: str = "",
                      counterparty: str = "", notes: str = "", source: TxnSource = TxnSource.MANUAL) -> Transaction:
        """Money in: salary, interest, a gift."""
        day, lines = self._money_lines(Movement.INFLOW, date, account_id, amount, category_id)
        return self._create(DocType.IN, day, lines, description, counterparty, notes, source)

    def record_outflow(self, date: str, account_id: int, amount, category_id: int, description: str = "",
                       counterparty: str = "", notes: str = "", source: TxnSource = TxnSource.MANUAL) -> Transaction:
        """Money out: groceries, fees, tax. On a credit card this increases what you owe."""
        day, lines = self._money_lines(Movement.OUTFLOW, date, account_id, amount, category_id)
        return self._create(DocType.OUT, day, lines, description, counterparty, notes, source)

    def record_transfer(self, date: str, from_account_id: int, to_account_id: int, amount,
                        description: str = "", notes: str = "",
                        source: TxnSource = TxnSource.MANUAL) -> Transaction:
        """Money moving between your own accounts. Never income, expense or revaluation."""
        day, lines = self._transfer_lines(date, from_account_id, to_account_id, amount)
        return self._create(DocType.TRF, day, lines, description, "", notes, source)

    def record_in_account(self, account_id: int, date: str, payment: object = "", deposit: object = "",
                          category_id: int | None = None, other_account_id: int | None = None,
                          payee: str = "", notes: str = "") -> Transaction:
        """One register row (Actual-style) -> the right transaction.

        Fill Payment (money leaves this account) or Deposit (money arrives), and choose either a
        category (money out / money in) or another account (a transfer).
        """
        pay, dep = str(payment or "").strip(), str(deposit or "").strip()
        if bool(pay) == bool(dep):
            raise ValidationError("Enter the amount under Payment or under Deposit — one of them.", "amount")
        if (category_id is None) == (other_account_id is None):
            raise ValidationError("Choose a category, or an account for a transfer.", "category")
        if other_account_id is not None:
            if pay:
                return self.record_transfer(date, account_id, other_account_id, pay, payee, notes)
            return self.record_transfer(date, other_account_id, account_id, dep, payee, notes)
        category = self.categories.get(category_id)
        name = self.categories.display_name(category.id)
        if pay:
            if category.movement != Movement.OUTFLOW:
                raise ValidationError(f"{name} is money in — put the amount under Deposit.", "amount")
            return self.record_outflow(date, account_id, pay, category.id, counterparty=payee, notes=notes)
        if category.movement != Movement.INFLOW:
            raise ValidationError(f"{name} is money out — put the amount under Payment.", "amount")
        return self.record_inflow(date, account_id, dep, category.id, counterparty=payee, notes=notes)

    def update_in_account(self, txn_id: int, account_id: int, date: str, payment: object = "", deposit: object = "",
                          category_id: int | None = None, other_account_id: int | None = None,
                          payee: str = "", notes: str = "") -> Transaction:
        """Edit a register row in place. Seen from ``account_id`` (the register it was edited in).

        If the kind of transaction changes (e.g. a transfer becomes money out), the old one is voided and
        a new one recorded, because a ref's prefix (TRF/OUT/IN) must always tell the truth.
        """
        current = self.get(txn_id)
        if current.is_void:
            raise ValidationError("Restore this transaction before editing it.")
        if current.type == DocType.OPN:
            raise ValidationError("Change an opening balance from the account's edit page.")
        if current.type not in EDITABLE_TYPES:
            raise ValidationError(f"{current.type_label} transactions cannot be edited here.")
        pay, dep = str(payment or "").strip(), str(deposit or "").strip()
        if bool(pay) == bool(dep):
            raise ValidationError("Enter the amount under Payment or under Deposit — one of them.", "amount")
        if (category_id is None) == (other_account_id is None):
            raise ValidationError("Choose a category, or an account for a transfer.", "category")
        if other_account_id is not None:
            new_type = DocType.TRF
        else:
            new_type = DocType.OUT if pay else DocType.IN
            category = self.categories.get(category_id)
            wanted = Movement.OUTFLOW if pay else Movement.INFLOW
            if category.movement != wanted:
                name = self.categories.display_name(category.id)
                column = "Deposit" if pay else "Payment"
                kind = "money in" if pay else "money out"
                raise ValidationError(f"{name} is {kind} — put the amount under {column}.", "amount")
        with self.db.transaction():
            if new_type != current.type:
                self.void(current.id, f"Replaced when edited ({current.type_label} → {DOC_LABELS[new_type]})")
                return self.record_in_account(account_id, date, pay, dep, category_id, other_account_id, payee, notes)
            if new_type == DocType.TRF:
                src, dst = (account_id, other_account_id) if pay else (other_account_id, account_id)
                return self.update_transfer(current.id, date, src, dst, pay or dep, payee, notes)
            return self.update_money(current.id, date, account_id, pay or dep, category_id, "", payee, notes)

    def search_ids(self, text: str) -> set[int]:
        """Transaction ids matching a search (posted ones)."""
        txns, _ = self.repo.list(TxnFilter(search=text, limit=100000))
        return {t.id for t in txns}

    def payee_suggestions(self) -> dict[str, int]:
        """Payees used before -> the category used with them last time (for the register)."""
        return self.repo.payee_categories()

    def set_opening_balance(self, account_id: int, amount: Decimal, date: str) -> Transaction | None:
        """Create, change or remove an account's opening balance (signed: liabilities are negative).

        Called by the workflow layer when an account is opened or edited.
        """
        account = self.accounts.get(account_id)
        day = parse_date(date, "opening_date")
        asset = self.assets.cash_asset(account.currency)
        amount = check_places(to_decimal(amount, "opening_balance"), asset.quantity_decimals, "opening_balance")
        existing_id = self.repo.opening_txn_id(account_id)
        with self.db.transaction():
            if amount == ZERO:
                if existing_id:
                    self.void(existing_id, "Opening balance set to zero")
                return None
            lines = [PostingLine.cash(account.id, asset.id, amount, Effect.OPENING,
                                      fx_rate=self._fx(account), memo="Opening balance")]
            validate_posting(lines)
            if existing_id:
                current = self.get(existing_id)
                return self._update(current, day, lines, current.description, "", current.notes)
            return self._create(DocType.OPN, day, lines, f"Opening balance — {account.name}", "", "",
                                TxnSource.SYSTEM)

    def opening_balance(self, account_id: int) -> Decimal:
        txn_id = self.repo.opening_txn_id(account_id)
        if not txn_id:
            return ZERO
        return sum((ln.quantity for ln in self.get(txn_id).lines if ln.account_id == account_id), ZERO)

    # ======================================================================
    # Editing, voiding
    # ======================================================================
    def update_money(self, txn_id: int, date: str, account_id: int, amount, category_id: int,
                     description: str = "", counterparty: str = "", notes: str = "") -> Transaction:
        current = self._editable(txn_id, {DocType.IN, DocType.OUT})
        movement = Movement.INFLOW if current.type == DocType.IN else Movement.OUTFLOW
        day, lines = self._money_lines(movement, date, account_id, amount, category_id)
        return self._update(current, day, lines, description, counterparty, notes)

    def update_transfer(self, txn_id: int, date: str, from_account_id: int, to_account_id: int, amount,
                        description: str = "", notes: str = "") -> Transaction:
        current = self._editable(txn_id, {DocType.TRF})
        day, lines = self._transfer_lines(date, from_account_id, to_account_id, amount)
        return self._update(current, day, lines, description, "", notes)

    def void(self, txn_id: int, reason: str = "") -> Transaction:
        """Cancel a transaction. It stays visible (greyed out) and can be restored."""
        t = self.get(txn_id)
        if t.is_void:
            return t
        with self.db.transaction():
            self.repo.set_status(t.id, TxnStatus.VOID)
            self.audit.record("transaction", t.id, "void", reason or f"Voided {t.ref}")
            self._refresh_search(t.id)
        return self.get(txn_id)

    def restore(self, txn_id: int) -> Transaction:
        t = self.get(txn_id)
        if not t.is_void:
            return t
        if t.type == DocType.OPN:
            for line in t.lines:
                if self.repo.opening_txn_id(line.account_id):
                    raise ValidationError("This account already has another opening balance.")
        with self.db.transaction():
            # re-validate against today's rules (accounts may have been deactivated)
            for line in t.lines:
                self.accounts.require_usable(line.account_id)
            self.repo.set_status(t.id, TxnStatus.POSTED)
            self.audit.record("transaction", t.id, "restore", f"Restored {t.ref}")
            self._refresh_search(t.id)
        return self.get(txn_id)

    # ======================================================================
    # Reading
    # ======================================================================
    def get(self, txn_id: int) -> Transaction:
        found = self.repo.get(txn_id)
        if not found:
            raise NotFoundError("Transaction not found.")
        return found

    def get_by_ref(self, ref: str) -> Transaction:
        found = self.repo.get_by_ref((ref or "").strip().upper())
        if not found:
            raise NotFoundError(f"Transaction {ref} not found.")
        return found

    def find(self, f: TxnFilter) -> tuple[list[TxnSummary], int]:
        txns, total = self.repo.list(f)
        return [self.summarize(t) for t in txns], total

    def count_for_account(self, account_id: int) -> int:
        return self.repo.count_for_account(account_id)

    def earliest_activity(self, account_id: int) -> str | None:
        """Date of the account's first posted transaction other than its opening balance."""
        return self.repo.earliest_activity(account_id)

    @property
    def full_text_search(self) -> bool:
        return self.repo.has_fts

    def history(self, txn_id: int) -> list[dict]:
        return self.audit.history("transaction", txn_id)

    def summarize(self, t: Transaction) -> TxnSummary:
        account_id = to_account_id = category_id = None
        amount = ZERO
        if t.type == DocType.TRF:
            out_line = next((ln for ln in t.lines if ln.quantity < 0), None)
            in_line = next((ln for ln in t.lines if ln.quantity > 0), None)
            account_id = out_line.account_id if out_line else None
            to_account_id = in_line.account_id if in_line else None
            amount = in_line.quantity if in_line else ZERO
        elif t.lines:
            first = t.lines[0]
            account_id, category_id = first.account_id, first.category_id
            amount = sum((ln.quantity for ln in t.lines), ZERO)
        currency = self.accounts.get(account_id).currency if account_id else self.base_currency
        return TxnSummary(
            id=t.id,
            ref=t.ref,
            date=t.date,
            type=t.type,
            type_label=DOC_LABELS[t.type],
            status=t.status,
            description=t.description,
            counterparty=t.counterparty,
            notes=t.notes,
            amount=amount,
            currency=currency,
            account_label=self.accounts.get(account_id).label if account_id else "",
            to_account_label=self.accounts.get(to_account_id).label if to_account_id else "",
            category_label=self.categories.display_name(category_id) if category_id else "",
            category_code=self.categories.get(category_id).code if category_id else "",
            account_id=account_id,
            to_account_id=to_account_id,
            category_id=category_id,
        )

    # ======================================================================
    # Search text
    # ======================================================================
    def rebuild_search(self, txn_ids: list[int]) -> None:
        with self.db.transaction():
            for txn_id in txn_ids:
                self._refresh_search(txn_id)

    def rebuild_search_for_accounts(self, account_ids: list[int]) -> None:
        self.rebuild_search(self.repo.ids_touching_accounts(account_ids))

    def rebuild_search_for_categories(self, category_ids: list[int]) -> None:
        self.rebuild_search(self.repo.ids_touching_categories(category_ids))

    def build_search_text(self, t: Transaction) -> str:
        """2026-09-25 · OUT-2026-09-25-003 · CIB-CUR-EGP CIB Current · EXP.PERSONAL.FOOD Food · -450.00 EGP · ..."""
        s = self.summarize(t)
        parts = [t.date, t.ref, s.type_label]
        parts.append(s.account_label + (f" → {s.to_account_label}" if s.to_account_label else ""))
        if s.category_id:
            parts.append(f"{s.category_code} {s.category_label}")
        plain = f"{abs(s.amount):.2f}"  # without thousands separators, so "10000" matches too
        parts.append(f"{fmt(s.amount, signed=t.type in (DocType.IN, DocType.OUT))} {s.currency} {plain}")
        parts.extend(p for p in (t.counterparty, t.description, t.notes) if p)
        if t.is_void:
            parts.append("VOID")
        return " · ".join(p for p in parts if p)

    # ======================================================================
    # Internals
    # ======================================================================
    def _money_lines(self, movement: Movement, date: str, account_id: int, amount, category_id: int):
        account = self.accounts.require_usable(account_id)
        day = self._check_date(date, [account])
        asset = self.assets.cash_asset(account.currency)
        value = self._positive_amount(amount, asset.quantity_decimals)
        category = self.categories.require(category_id, movement)
        signed = value if movement == Movement.INFLOW else -value
        effect = Effect.INFLOW if movement == Movement.INFLOW else Effect.OUTFLOW
        lines = [PostingLine.cash(account.id, asset.id, signed, effect, category.id, fx_rate=self._fx(account))]
        validate_posting(lines)
        return day, lines

    def _transfer_lines(self, date: str, from_id: int, to_id: int, amount):
        src = self.accounts.require_usable(from_id, "from_account")
        dst = self.accounts.require_usable(to_id, "to_account")
        if src.id == dst.id:
            raise ValidationError("Choose two different accounts.", "to_account")
        if src.currency != dst.currency:
            raise ValidationError("Both accounts must use the same currency (exchanges arrive in M4).", "to_account")
        day = self._check_date(date, [src, dst])
        asset = self.assets.cash_asset(src.currency)
        value = self._positive_amount(amount, asset.quantity_decimals)
        lines = [
            PostingLine.cash(src.id, asset.id, -value, Effect.INTERNAL, fx_rate=self._fx(src), memo="Transfer out"),
            PostingLine.cash(dst.id, asset.id, value, Effect.INTERNAL, fx_rate=self._fx(dst), memo="Transfer in"),
        ]
        validate_posting(lines)
        return day, lines

    def _create(self, doc_type: DocType, day, lines: list[PostingLine], description: str, counterparty: str,
                notes: str, source: TxnSource) -> Transaction:
        with self.db.transaction():
            ref = format_ref(doc_type, day, self.repo.next_seq(ref_prefix(doc_type, day)))
            header = Transaction(
                id=0, ref=ref, type=doc_type, date=fmt_date(day),
                description=(description or "").strip(), counterparty=(counterparty or "").strip(),
                status=TxnStatus.POSTED, source=source, notes=(notes or "").strip(),
                search_text="", created_at="", updated_at="",
            )
            txn_id = self.repo.insert(header, lines)
            self._refresh_search(txn_id)
        return self.get(txn_id)

    def _update(self, current: Transaction, day, lines: list[PostingLine], description: str, counterparty: str,
                notes: str) -> Transaction:
        with self.db.transaction():
            updated = replace(
                current, date=fmt_date(day), description=(description or "").strip(),
                counterparty=(counterparty or "").strip(), notes=(notes or "").strip(),
            )
            self.repo.update_header(updated)
            self.repo.replace_lines(current.id, updated.date, lines)
            after = self.get(current.id)
            self.audit.record("transaction", current.id, "edit", f"Edited {current.ref}",
                              before=self._snapshot(current), after=self._snapshot(after))
            self._refresh_search(current.id)
        return self.get(current.id)

    def _editable(self, txn_id: int, allowed: set[DocType]) -> Transaction:
        t = self.get(txn_id)
        if t.is_void:
            raise ValidationError("Restore this transaction before editing it.")
        if t.type not in allowed:
            if t.type == DocType.OPN:
                raise ValidationError("Change an opening balance from the account's edit page.")
            raise ValidationError(f"{t.type_label} transactions cannot be edited here.")
        return t

    def _refresh_search(self, txn_id: int) -> None:
        self.repo.set_search_text(txn_id, self.build_search_text(self.get(txn_id)))

    def _check_date(self, date: str, accounts: list[Account]):
        day = parse_date(date)
        for account in accounts:
            if fmt_date(day) < account.opening_date:
                raise ValidationError(
                    f"{fmt_date(day)} is before {account.label} was opened ({account.opening_date}). "
                    "Its opening balance already covers that period — or move the opening date earlier.",
                    "date",
                )
        return day

    @staticmethod
    def _positive_amount(amount, places: int) -> Decimal:
        value = check_places(to_decimal(amount), places)
        if value <= ZERO:
            raise ValidationError("Enter an amount greater than zero.", "amount")
        return value

    def _fx(self, account: Account) -> Decimal:
        if account.currency == self.base_currency:
            return ONE
        raise ValidationError(f"Exchange rates for {account.currency} arrive in M4.", "currency")

    @staticmethod
    def _snapshot(t: Transaction) -> dict:
        data = asdict(t)
        data.pop("search_text", None)
        return data
