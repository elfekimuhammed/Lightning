from __future__ import annotations

from decimal import Decimal

from lightning.core.money import from_e6, to_e6
from lightning.database.connection import Database

from .domain import CompoundingFrequency, DepositTerms, InterestMethod, PayoutFrequency


class DepositRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, account_id: int) -> DepositTerms | None:
        row = self.db.one("SELECT * FROM cd_terms WHERE account_id=?", (account_id,))
        if row is None:
            return None
        return DepositTerms(
            account_id=row["account_id"], start_date=row["start_date"],
            lockup_end_date=row["lockup_end_date"],
            maturity_date=row["maturity_date"], principal=from_e6(row["principal_e6"]),
            annual_rate=Decimal(row["annual_rate"]),
            interest_method=InterestMethod(row["interest_method"]),
            payout_frequency=PayoutFrequency(row["payout_frequency"]),
            compounding_frequency=CompoundingFrequency(row["compounding_frequency"]),
            destination_account_id=row["destination_account_id"],
        )

    def save(self, terms: DepositTerms) -> None:
        self.db.execute(
            "INSERT INTO cd_terms(account_id,start_date,lockup_end_date,maturity_date,principal_e6,annual_rate,"
            "interest_method,payout_frequency,compounding_frequency,destination_account_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(account_id) DO UPDATE SET start_date=excluded.start_date,"
            "lockup_end_date=excluded.lockup_end_date,"
            "maturity_date=excluded.maturity_date,principal_e6=excluded.principal_e6,"
            "annual_rate=excluded.annual_rate,interest_method=excluded.interest_method,"
            "payout_frequency=excluded.payout_frequency,"
            "compounding_frequency=excluded.compounding_frequency,"
            "destination_account_id=excluded.destination_account_id",
            (terms.account_id, terms.start_date, terms.lockup_end_date, terms.maturity_date, to_e6(terms.principal),
             str(terms.annual_rate), terms.interest_method.value, terms.payout_frequency.value,
             terms.compounding_frequency.value, terms.destination_account_id),
        )

    def delete(self, account_id: int) -> None:
        self.db.execute("DELETE FROM cd_terms WHERE account_id=?", (account_id,))

    def owned_balance_e6(self, account_id: int, as_of: str) -> int:
        value = self.db.scalar(
            "SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id AND t.status='POSTED' "
            "JOIN financial_assets fa ON fa.id=le.asset_id AND fa.is_cash=1 "
            "WHERE le.account_id=? AND le.owner_id IS NULL AND le.date<=?",
            (account_id, as_of),
        )
        return int(value or 0)
