from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from lightning.accounts.domain import AccountType
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import NotFoundError, ValidationError
from lightning.core.money import ZERO, to_decimal, to_e6
from lightning.database.connection import Database

from .domain import (CompoundingFrequency, DepositEvent, DepositTerms, InterestMethod,
                     PayoutFrequency)
from .repository import DepositRepository

_MICRO = Decimal("0.000001")
_MONTHS = {PayoutFrequency.MONTHLY: 1, PayoutFrequency.QUARTERLY: 3,
           PayoutFrequency.YEARLY: 12}
_COMPOUND_MONTHS = {CompoundingFrequency.MONTHLY: 1, CompoundingFrequency.QUARTERLY: 3,
                    CompoundingFrequency.YEARLY: 12}


class DepositService:
    """Store CD terms and produce future cash events without posting ledger entries."""

    def __init__(self, db: Database, accounts):
        self.db = db
        self.accounts = accounts
        self.repo = DepositRepository(db)

    def get(self, account_id: int) -> DepositTerms:
        terms = self.repo.get(account_id)
        if terms is None:
            raise NotFoundError("CD terms were not found.")
        return terms

    def save(self, account_id: int, start_date, maturity_date, principal, annual_rate,
             interest_method, payout_frequency, destination_account_id: int,
             lockup_end_date=None, compounding_frequency="MONTHLY") -> DepositTerms:
        account = self._account(account_id, "DEPOSIT", "deposit account")
        destination = self._account(destination_account_id, None, "destination account")
        if destination.account_type not in {AccountType.BANK, AccountType.CASH}:
            raise ValidationError("Choose an active bank or cash account.", "destination_account_id")
        if destination.id == account.id:
            raise ValidationError("The destination must differ from the CD account.", "destination_account_id")
        if destination.currency != account.currency:
            raise ValidationError("Choose a destination in the same currency as the CD.",
                                  "destination_account_id")

        start = parse_date(start_date, "start_date")
        maturity = parse_date(maturity_date, "maturity_date")
        if start >= maturity:
            raise ValidationError("Maturity must be after the start date.", "maturity_date")
        lockup_end = parse_date(lockup_end_date if lockup_end_date is not None else maturity,
                                "lockup_end_date")
        if not start <= lockup_end <= maturity:
            raise ValidationError("Lockup end must be on or after start and on or before maturity.",
                                  "lockup_end_date")
        amount = to_decimal(principal, "principal")
        if amount <= ZERO:
            raise ValidationError("Enter a principal above zero.", "principal")
        to_e6(amount)
        rate = to_decimal(annual_rate, "annual_rate")
        if not ZERO <= rate <= Decimal("100"):
            raise ValidationError("Annual rate must be between 0 and 100 percent.", "annual_rate")
        try:
            method = InterestMethod(interest_method)
        except (ValueError, TypeError):
            raise ValidationError("Choose SIMPLE or COMPOUND interest.", "interest_method") from None
        try:
            frequency = PayoutFrequency(payout_frequency)
        except (ValueError, TypeError):
            raise ValidationError("Choose a supported payout frequency.", "payout_frequency") from None
        if method == InterestMethod.COMPOUND and frequency != PayoutFrequency.AT_MATURITY:
            raise ValidationError("Compound interest must be paid at maturity.", "payout_frequency")
        try:
            compounding = CompoundingFrequency(compounding_frequency or "MONTHLY")
        except (ValueError, TypeError):
            raise ValidationError("Choose a monthly, quarterly, or yearly compounding frequency.",
                                  "compounding_frequency") from None

        current_owned = Decimal(self.repo.owned_balance_e6(account_id, fmt_date(today()))).scaleb(-6)
        if amount > current_owned:
            raise ValidationError("Principal cannot exceed the CD's currently owned ledger balance.", "principal")
        terms = DepositTerms(account_id, fmt_date(start), fmt_date(lockup_end), fmt_date(maturity),
                             amount, rate, method, frequency, compounding, destination.id)
        with self.db.transaction():
            self.repo.save(terms)
        return terms

    def delete(self, account_id: int) -> None:
        with self.db.transaction():
            self.repo.delete(account_id)

    def future_events(self, as_of, end) -> list[DepositEvent]:
        day, horizon = parse_date(as_of, "as_of"), parse_date(end, "end")
        if horizon <= day:
            return []
        events: list[DepositEvent] = []
        for account in self.accounts.list(active_only=True):
            if account.account_type != AccountType.DEPOSIT:
                continue
            terms = self.repo.get(account.id)
            if terms is None:
                continue
            # The terms are only a cash-flow projection while their principal remains
            # represented by owned ledger cash on the as-of date.
            funded_e6 = self.repo.owned_balance_e6(account.id, fmt_date(day))
            if funded_e6 < to_e6(terms.principal):
                continue
            events.extend(self._events(terms, day, horizon))
        return sorted(events, key=lambda event: (event.date, event.deposit_account_id, event.kind))

    def _events(self, terms: DepositTerms, day: date, horizon: date) -> list[DepositEvent]:
        start = date.fromisoformat(terms.start_date)
        maturity = date.fromisoformat(terms.maturity_date)
        end = min(maturity, horizon)
        if end <= day:
            return []
        principal = terms.principal
        rate = terms.annual_rate / Decimal("100")
        found: list[DepositEvent] = []

        def emit(when: date, amount: Decimal, kind: str) -> None:
            if day < when <= horizon and amount > ZERO:
                found.append(DepositEvent(fmt_date(when), terms.destination_account_id,
                                          amount.quantize(_MICRO, rounding=ROUND_HALF_UP),
                                          kind, terms.account_id))

        if terms.interest_method == InterestMethod.COMPOUND:
            accrued = ZERO
            previous = start
            # Capitalize each selected interval at its anniversary; accrue a final
            # stub to maturity, then round once for the single maturity event.
            index = 1
            months = _COMPOUND_MONTHS[terms.compounding_frequency]
            while True:
                period_end = min(_add_months(start, index * months), maturity)
                accrued += (principal + accrued) * rate * Decimal((period_end - previous).days) / Decimal(365)
                previous = period_end
                if period_end == maturity:
                    break
                index += 1
            emit(maturity, principal + accrued, "MATURITY")
            return found

        previous = start
        if terms.payout_frequency == PayoutFrequency.AT_MATURITY:
            interest = principal * rate * Decimal((maturity - start).days) / Decimal(365)
            emit(maturity, interest, "INTEREST")
        else:
            step = _MONTHS[terms.payout_frequency]
            index = 1
            while True:
                period_end = min(_add_months(start, index * step), maturity)
                interest = principal * rate * Decimal((period_end - previous).days) / Decimal(365)
                emit(period_end, interest, "INTEREST")
                previous = period_end
                if period_end == maturity:
                    break
                index += 1
        emit(maturity, principal, "PRINCIPAL")
        return found

    def _account(self, account_id: int, expected_type: str | None, field: str):
        try:
            account = self.accounts.get(account_id)
        except NotFoundError:
            raise ValidationError("Choose an existing account.", field) from None
        if not account.active:
            raise ValidationError("Choose an active account.", field)
        if expected_type and account.account_type.value != expected_type:
            raise ValidationError("Choose a DEPOSIT account.", field)
        return account


def _add_months(start: date, months: int) -> date:
    month_index = start.year * 12 + start.month - 1 + months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
