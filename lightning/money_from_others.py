"""Custody balances: other people's funds held in the user's accounts."""

from __future__ import annotations

from decimal import Decimal

from lightning.accounts.service import AccountService
from lightning.core.dates import now_iso, parse_date
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, check_places, from_e6, to_decimal, to_e6
from lightning.database.connection import Database


class MoneyFromOthersService:
    def __init__(self, db: Database, accounts: AccountService):
        self.db, self.accounts = db, accounts

    def record(self, day: str, owner: str, account_id: int, amount: Decimal, notes: str = "",
               transaction_id: int | None = None) -> None:
        amount = check_places(to_decimal(amount, "amount"), 2, "amount")
        account = self.accounts.require_usable(account_id)
        parsed = parse_date(day).isoformat()
        if not owner.strip():
            raise ValidationError("Enter whose money this is.", "owner")
        if amount == ZERO:
            raise ValidationError("Enter a non-zero amount.", "amount")
        self.db.execute(
            "INSERT INTO money_from_others(date,owner,account_id,amount_e6,notes,created_at,transaction_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (parsed, owner.strip(), account.id, to_e6(amount), notes.strip(), now_iso(), transaction_id))

    def sync_transaction(self, transaction_id: int, day: str, owner: str | None, account_id: int,
                         amount: Decimal, notes: str = "") -> None:
        """Keep the exclusion entry in step with a tagged register transaction."""
        amount = check_places(to_decimal(amount, "amount"), 2, "amount")
        self.db.execute("DELETE FROM money_from_others WHERE transaction_id=?", (transaction_id,))
        if not owner or amount == ZERO:
            return
        self.accounts.require_usable(account_id)
        balance = self.db.scalar(
            "SELECT COALESCE(SUM(amount_e6),0) FROM money_from_others WHERE owner=? AND account_id=? "
            "AND date<=? AND transaction_id IS NOT ? AND (transaction_id IS NULL OR transaction_id IN "
            "(SELECT id FROM transactions WHERE status='POSTED'))",
            (owner.strip(), account_id, parse_date(day).isoformat(), transaction_id))
        if int(balance or 0) + to_e6(amount) < 0:
            raise ValidationError(f"This is more than the money currently held for {owner} in this account.", "amount")
        self.db.execute(
            "INSERT INTO money_from_others(date,owner,account_id,amount_e6,notes,created_at,transaction_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (parse_date(day).isoformat(), owner.strip(), account_id, to_e6(amount), notes.strip(), now_iso(), transaction_id))

    def cash_owners_for_account(self, account_id: int, as_of: str) -> list[dict]:
        rows = self.db.all(
            "SELECT owner,SUM(amount_e6) AS amount_e6 FROM money_from_others WHERE account_id=? AND date<=? "
            "AND (transaction_id IS NULL OR transaction_id IN (SELECT id FROM transactions WHERE status='POSTED')) "
            "GROUP BY owner HAVING SUM(amount_e6)>0 ORDER BY owner", (account_id, parse_date(as_of).isoformat()))
        return [dict(row) | {"amount": from_e6(row["amount_e6"])} for row in rows]

    def sync_transfer(self, transaction_id: int, day: str, owner: str | None, source_id: int, target_id: int,
                      amount: Decimal, notes: str = "") -> None:
        """Move custody cash alongside an internal account transfer, without changing its total."""
        self.db.execute("DELETE FROM money_from_others WHERE transaction_id=?", (transaction_id,))
        if not owner or amount <= ZERO:
            return
        self.accounts.require_usable(source_id)
        self.accounts.require_usable(target_id)
        day = parse_date(day).isoformat()
        balance = self.cash_balance(owner, source_id, day)
        moved = min(balance, amount)
        if moved <= ZERO:
            return
        stamp = now_iso()
        self.db.execute(
            "INSERT INTO money_from_others(date,owner,account_id,amount_e6,notes,created_at,transaction_id) "
            "VALUES(?,?,?,?,?,?,?),(?,?,?,?,?,?,?)",
            (day, owner, source_id, -to_e6(moved), notes.strip(), stamp, transaction_id,
             day, owner, target_id, to_e6(moved), notes.strip(), stamp, transaction_id))

    def cash_balance(self, owner: str, account_id: int, as_of: str) -> Decimal:
        total = self.db.scalar("SELECT COALESCE(SUM(amount_e6),0) FROM money_from_others "
                               "WHERE owner=? AND account_id=? AND date<=? AND (transaction_id IS NULL OR transaction_id IN "
                               "(SELECT id FROM transactions WHERE status='POSTED'))",
                               (owner, account_id, parse_date(as_of).isoformat()))
        return from_e6(total or 0)

    def cash_total_for_account(self, account_id: int, as_of: str) -> Decimal:
        row = self.db.scalar("SELECT COALESCE(SUM(amount_e6),0) FROM money_from_others "
                             "WHERE account_id=? AND date<=? AND (transaction_id IS NULL OR transaction_id IN "
                             "(SELECT id FROM transactions WHERE status='POSTED'))",
                             (account_id, parse_date(as_of).isoformat()))
        return from_e6(row or 0)

    def transaction_owner(self, transaction_id: int) -> str:
        row = self.db.one("SELECT owner FROM money_from_others WHERE transaction_id=?", (transaction_id,))
        return row["owner"] if row else ""

    def investment_transaction_owner(self, transaction_id: int) -> str:
        row = self.db.one("SELECT owner FROM investment_custody_events WHERE transaction_id=?", (transaction_id,))
        return row["owner"] if row else ""

    def sync_investment(self, transaction_id: int, day: str, owner: str | None, account_id: int,
                        asset_id: int, units: Decimal) -> None:
        if not owner or units == ZERO:
            self.db.execute("DELETE FROM investment_custody_events WHERE transaction_id=?", (transaction_id,))
            return
        units_e6 = to_e6(units)
        existing = self.db.one("SELECT owner,account_id,asset_id,units_e6 FROM investment_custody_events WHERE transaction_id=?",
                               (transaction_id,))
        current = self.db.scalar(
            "SELECT COALESCE(SUM(units_e6),0) FROM investment_custody_events "
            "WHERE owner=? AND account_id=? AND asset_id=? AND date<=? AND transaction_id<>?",
            (owner.strip(), account_id, asset_id, parse_date(day).isoformat(), transaction_id))
        if int(current or 0) + units_e6 < 0:
            raise ValidationError(f"There are not enough units owned by {owner} to record this sale.", "units")
        custody_units = self.db.scalar(
            "SELECT COALESCE(SUM(e.units_e6),0) FROM investment_custody_events e "
            "JOIN transactions t ON t.id=e.transaction_id WHERE e.account_id=? AND e.asset_id=? "
            "AND e.date<=? AND t.status='POSTED' AND e.transaction_id<>?",
            (account_id, asset_id, parse_date(day).isoformat(), transaction_id))
        total_units = self.db.scalar(
            "SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le JOIN transactions t "
            "ON t.id=le.transaction_id WHERE le.account_id=? AND le.asset_id=? AND le.date<=? "
            "AND t.status='POSTED'",
            (account_id, asset_id, parse_date(day).isoformat()))
        if int(custody_units or 0) + units_e6 > int(total_units or 0):
            raise ValidationError("The total marked for others cannot exceed the investment units held.", "units")
        self.db.execute(
            "INSERT INTO investment_custody_events(transaction_id,date,owner,account_id,asset_id,units_e6,created_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET date=excluded.date,owner=excluded.owner,"
            "account_id=excluded.account_id,asset_id=excluded.asset_id,units_e6=excluded.units_e6",
            (transaction_id, parse_date(day).isoformat(), owner.strip(), account_id, asset_id, units_e6, now_iso()))

    def totals_by_account(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        return [dict(row) for row in self.db.all(
            "SELECT account_id,SUM(amount_e6) AS amount_e6 FROM money_from_others "
            "WHERE date<=? AND (transaction_id IS NULL OR transaction_id IN "
            "(SELECT id FROM transactions WHERE status='POSTED')) GROUP BY account_id", (day,))]

    def by_owner(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        rows = self.db.all(
            "SELECT m.owner,m.account_id,a.name AS account_name,a.currency,SUM(m.amount_e6) AS amount_e6 "
            "FROM money_from_others m JOIN accounts a ON a.id=m.account_id WHERE m.date<=? "
            "AND (m.transaction_id IS NULL OR m.transaction_id IN (SELECT id FROM transactions WHERE status='POSTED')) "
            "GROUP BY m.owner,m.account_id ORDER BY m.owner,a.name", (day,))
        return [dict(row) | {"amount": from_e6(row["amount_e6"])} for row in rows]

    def history(self, limit: int = 100) -> list[dict]:
        rows = self.db.all(
            "SELECT m.*,a.name AS account_name,a.currency FROM money_from_others m JOIN accounts a ON a.id=m.account_id "
            "WHERE m.transaction_id IS NULL OR m.transaction_id IN (SELECT id FROM transactions WHERE status='POSTED') "
            "ORDER BY m.date DESC,m.id DESC LIMIT ?", (limit,))
        return [dict(row) | {"amount": from_e6(row["amount_e6"])} for row in rows]

    def investment_positions(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        rows = self.db.all(
            "SELECT e.owner,e.account_id,e.asset_id,SUM(e.units_e6) AS units_e6 FROM investment_custody_events e "
            "JOIN transactions t ON t.id=e.transaction_id WHERE e.date<=? AND t.status='POSTED' "
            "GROUP BY e.owner,e.account_id,e.asset_id HAVING SUM(e.units_e6)<>0 "
            "ORDER BY owner,account_id,asset_id", (day,))
        return [dict(row) | {"units": from_e6(row["units_e6"])} for row in rows]

    def investment_history(self, limit: int = 100) -> list[dict]:
        rows = self.db.all(
            "SELECT e.date,e.owner,e.account_id,e.asset_id,e.units_e6,a.name AS account_name,"
            "f.name AS asset_name,f.unit,t.ref FROM investment_custody_events e "
            "JOIN transactions t ON t.id=e.transaction_id JOIN accounts a ON a.id=e.account_id "
            "JOIN financial_assets f ON f.id=e.asset_id WHERE t.status='POSTED' "
            "ORDER BY e.date DESC,e.id DESC LIMIT ?", (limit,))
        return [dict(row) | {"units": from_e6(row["units_e6"])} for row in rows]
