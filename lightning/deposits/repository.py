from __future__ import annotations

from decimal import Decimal

from lightning.core.money import from_e6, to_e6
from lightning.database.connection import Database

from .domain import (Certificate, CertificateTerms, CompoundingFrequency, DepositTerms, InterestMethod,
                     PayoutFrequency)


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

    def owned_cash_deltas_after(self, account_id: int, after: str):
        """Posted, user-owned cash movements after a proposed CD purchase date."""
        return self.db.all(
            "SELECT le.date,SUM(le.quantity_e6) AS delta_e6 FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id AND t.status='POSTED' "
            "JOIN financial_assets fa ON fa.id=le.asset_id AND fa.is_cash=1 "
            "WHERE le.account_id=? AND le.owner_id IS NULL AND le.date>? "
            "GROUP BY le.date ORDER BY le.date",
            (account_id, after),
        )

    def save_certificate(self, terms: CertificateTerms) -> int:
        cursor = self.db.execute(
            "INSERT INTO cd_certificates(account_id,asset_id,name,start_date,lockup_end_date,maturity_date,"
            "principal_e6,annual_rate,interest_method,payout_frequency,compounding_frequency,"
            "destination_account_id,purchase_transaction_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (terms.account_id, terms.asset_id, terms.name, terms.start_date, terms.lockup_end_date,
             terms.maturity_date, to_e6(terms.principal), str(terms.annual_rate), terms.interest_method.value,
             terms.payout_frequency.value, terms.compounding_frequency.value,
             terms.destination_account_id, terms.purchase_transaction_id),
        )
        return int(cursor.lastrowid)

    def get_certificate(self, certificate_id: int) -> Certificate | None:
        row = self.db.one(
            "SELECT cd.*,COALESCE((SELECT SUM(le.quantity_e6) FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id WHERE t.status='POSTED' AND le.owner_id IS NULL "
            "AND le.account_id=cd.account_id AND le.asset_id=cd.asset_id),0) AS units_e6,"
            "EXISTS(SELECT 1 FROM cd_redemptions r JOIN transactions rt ON rt.id=r.transaction_id "
            "WHERE rt.status='POSTED' AND r.certificate_id=cd.id) AS redeemed "
            "FROM cd_certificates cd WHERE cd.id=?", (certificate_id,),
        )
        return self._certificate(row) if row else None

    def get_certificate_by_asset(self, asset_id: int) -> Certificate | None:
        row = self.db.one(
            "SELECT cd.*,COALESCE((SELECT SUM(le.quantity_e6) FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id WHERE t.status='POSTED' AND le.owner_id IS NULL "
            "AND le.account_id=cd.account_id AND le.asset_id=cd.asset_id),0) AS units_e6,"
            "EXISTS(SELECT 1 FROM cd_redemptions r JOIN transactions rt ON rt.id=r.transaction_id "
            "WHERE rt.status='POSTED' AND r.certificate_id=cd.id) AS redeemed "
            "FROM cd_certificates cd WHERE cd.asset_id=?", (asset_id,),
        )
        return self._certificate(row) if row else None

    def list_certificates(self, account_id: int) -> list[Certificate]:
        rows = self.db.all(
            "SELECT cd.*,COALESCE((SELECT SUM(le.quantity_e6) FROM ledger_entries le "
            "JOIN transactions t ON t.id=le.transaction_id WHERE t.status='POSTED' AND le.owner_id IS NULL "
            "AND le.account_id=cd.account_id AND le.asset_id=cd.asset_id),0) AS units_e6,"
            "EXISTS(SELECT 1 FROM cd_redemptions r JOIN transactions rt ON rt.id=r.transaction_id "
            "WHERE rt.status='POSTED' AND r.certificate_id=cd.id) AS redeemed "
            "FROM cd_certificates cd WHERE cd.account_id=? ORDER BY cd.maturity_date,cd.id", (account_id,),
        )
        return [self._certificate(row) for row in rows]

    def set_certificate_terms(self, certificate_id: int, *, name: str, lockup_end_date: str,
                              maturity_date: str, annual_rate: Decimal, interest_method: InterestMethod,
                              payout_frequency: PayoutFrequency, compounding_frequency: CompoundingFrequency,
                              destination_account_id: int) -> None:
        self.db.execute(
            "UPDATE cd_certificates SET name=?,lockup_end_date=?,maturity_date=?,annual_rate=?,"
            "interest_method=?,payout_frequency=?,compounding_frequency=?,destination_account_id=?,"
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (name, lockup_end_date, maturity_date, str(annual_rate), interest_method.value,
             payout_frequency.value, compounding_frequency.value, destination_account_id, certificate_id),
        )

    def record_redemption(self, transaction_id: int, certificate_id: int, destination_account_id: int) -> None:
        self.db.execute("INSERT INTO cd_redemptions(transaction_id,certificate_id,destination_account_id) "
                        "VALUES(?,?,?)", (transaction_id, certificate_id, destination_account_id))

    def _certificate(self, row) -> Certificate:
        terms = CertificateTerms(
            id=row["id"], account_id=row["account_id"], asset_id=row["asset_id"], name=row["name"],
            start_date=row["start_date"], lockup_end_date=row["lockup_end_date"],
            maturity_date=row["maturity_date"], principal=from_e6(row["principal_e6"]),
            annual_rate=Decimal(row["annual_rate"]), interest_method=InterestMethod(row["interest_method"]),
            payout_frequency=PayoutFrequency(row["payout_frequency"]),
            compounding_frequency=CompoundingFrequency(row["compounding_frequency"]),
            destination_account_id=row["destination_account_id"],
            purchase_transaction_id=row["purchase_transaction_id"],
        )
        return Certificate(terms, from_e6(row["units_e6"]), bool(row["redeemed"]))
