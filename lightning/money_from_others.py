"""Custody balances: other people's funds held in the user's accounts."""

from __future__ import annotations

from decimal import Decimal

from lightning.accounts.service import AccountService
from lightning.core.dates import now_iso, parse_date
from lightning.core.errors import ValidationError
from lightning.core.money import ZERO, check_places, from_e6, to_decimal, to_e6
from lightning.counterparties import CounterpartyService
from lightning.ownership_migration import post_cash_owner_adjustment
from lightning.database.connection import Database


class MoneyFromOthersService:
    def __init__(self, db: Database, accounts: AccountService):
        self.db, self.accounts = db, accounts

    def _tag_exact_line(self, transaction_id: int, owner: str | None, account_id: int, asset_id: int,
                        quantity_e6: int) -> None:
        if not owner:
            return
        party = CounterpartyService(self.db).resolve(owner.strip())
        if not party:
            party_id = CounterpartyService(self.db).create(owner.strip())
            party = {"id": party_id}
        if not party:
            return
        line = self.db.one("SELECT * FROM ledger_entries WHERE transaction_id=? AND account_id=? AND asset_id=? "
                           "AND quantity_e6*?>0 AND owner_id IS NULL ORDER BY line_no LIMIT 1",
                           (transaction_id, account_id, asset_id, quantity_e6))
        if not line:
            return
        take = min(abs(quantity_e6), abs(line["quantity_e6"]))
        if take == abs(line["quantity_e6"]):
            self.db.execute("UPDATE ledger_entries SET owner_id=? WHERE id=?", (party["id"], line["id"]))
            self._validate_owner_partition(account_id, asset_id, party["id"])
            return
        total = abs(line["quantity_e6"])
        def proportional(value):
            sign = -1 if value < 0 else 1
            return sign * (abs(value) * take // total)
        owned_amount, owned_base = proportional(line["amount_e6"]), proportional(line["amount_base_e6"])
        sign = -1 if line["quantity_e6"] < 0 else 1
        self.db.execute("UPDATE ledger_entries SET quantity_e6=?,amount_e6=?,amount_base_e6=? WHERE id=?",
                        (line["quantity_e6"]-sign*take, line["amount_e6"]-owned_amount,
                         line["amount_base_e6"]-owned_base, line["id"]))
        self.db.execute("""INSERT INTO ledger_entries(transaction_id,line_no,date,account_id,asset_id,
                     quantity_e6,unit_price_e6,amount_e6,fx_rate_e6,amount_base_e6,effect,category_id,memo,
                     cleared,owner_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (line["transaction_id"], line["line_no"]+10000, line["date"], line["account_id"],
                         line["asset_id"], sign*take, line["unit_price_e6"], owned_amount,
                         line["fx_rate_e6"], owned_base, line["effect"], line["category_id"], line["memo"],
                         line["cleared"], party["id"]))
        self._validate_owner_partition(account_id, asset_id, party["id"])

    def _validate_owner_partition(self, account_id: int, asset_id: int, owner_id: int) -> None:
        for balance_owner in (owner_id, None):
            rows = self.db.all("""SELECT le.date,SUM(le.quantity_e6) quantity FROM ledger_entries le
                                 JOIN transactions t ON t.id=le.transaction_id
                                 WHERE t.status='POSTED' AND le.account_id=? AND le.asset_id=? AND le.owner_id IS ?
                                 GROUP BY le.date ORDER BY le.date""",
                               (account_id, asset_id, balance_owner))
            running = 0
            for row in rows:
                running += int(row["quantity"])
                if running < 0:
                    label = "selected owner" if balance_owner is not None else "user"
                    raise ValidationError(f"The {label}'s balance would become negative on {row['date']}.", "owner")

    def record(self, day: str, owner: str, account_id: int, amount: Decimal, notes: str = "",
               transaction_id: int | None = None) -> None:
        amount = check_places(to_decimal(amount, "amount"), 2, "amount")
        account = self.accounts.require_usable(account_id)
        parsed = parse_date(day).isoformat()
        if not owner.strip():
            raise ValidationError("Enter whose money this is.", "owner")
        if amount == ZERO:
            raise ValidationError("Enter a non-zero amount.", "amount")
        owner = owner.strip()
        as_of = parsed
        if transaction_id is None:
            if amount > ZERO:
                cash_asset = self.accounts.assets.cash_asset(account.currency)
                own_balance = self.db.scalar("""SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le
                                               JOIN transactions t ON t.id=le.transaction_id
                                               WHERE le.account_id=? AND le.asset_id=? AND le.owner_id IS NULL
                                               AND le.date<=? AND t.status='POSTED'""",
                                              (account.id, cash_asset.id, as_of)) or 0
                if int(own_balance) < to_e6(amount):
                    raise ValidationError("There is not enough of your own cash in this account to assign.", "amount")
            elif self.cash_balance(owner, account.id, as_of) + amount < ZERO:
                raise ValidationError(f"This is more than the money currently held for {owner} in this account.",
                                      "amount")
        with self.db.transaction():
            if transaction_id is None:
                parties = CounterpartyService(self.db)
                party = parties.resolve(owner)
                if not party:
                    party_id = parties.create(owner)
                    party = {"id": party_id, "name": owner}
                else:
                    owner = party["name"]
                cash_asset = self.accounts.assets.cash_asset(account.currency)
                transaction_id = post_cash_owner_adjustment(self.db, parsed, owner, party["id"], account.id,
                                                             cash_asset.id, to_e6(amount))
            self.db.execute(
                "INSERT INTO money_from_others(date,owner,account_id,amount_e6,notes,created_at,transaction_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (parsed, owner, account.id, to_e6(amount), notes.strip(), now_iso(), transaction_id))

    def sync_transaction(self, transaction_id: int, day: str, owner: str | None, account_id: int,
                         amount: Decimal, notes: str = "") -> None:
        """Keep the exclusion entry in step with a tagged register transaction."""
        amount = check_places(to_decimal(amount, "amount"), 2, "amount")
        self.db.execute("DELETE FROM money_from_others WHERE transaction_id=?", (transaction_id,))
        if not owner or amount == ZERO:
            return
        account = self.accounts.require_usable(account_id)
        # The posted ledger line may already carry this owner (investment buys
        # do). Read that balance once instead of subtracting the payment twice.
        tagged = self.db.scalar(
            "SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le "
            "JOIN counterparties p ON p.id=le.owner_id WHERE le.transaction_id=? "
            "AND le.account_id=? AND lower(p.name)=lower(?)",
            (transaction_id, account_id, owner.strip())) or 0
        balance_after = self.cash_balance(owner, account_id, day)
        if not tagged:
            balance_after += amount
        if balance_after < ZERO:
            raise ValidationError(f"This is more than the money currently held for {owner} in this account.", "amount")
        self.db.execute(
            "INSERT INTO money_from_others(date,owner,account_id,amount_e6,notes,created_at,transaction_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (parse_date(day).isoformat(), owner.strip(), account_id, to_e6(amount), notes.strip(), now_iso(), transaction_id))
        asset = self.accounts.assets.cash_asset(account.currency)
        self._tag_exact_line(transaction_id, owner, account_id, asset.id, to_e6(amount))

    def cash_owners_for_account(self, account_id: int, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        totals = {}
        rows = self.db.all("""SELECT p.name AS owner,SUM(le.quantity_e6) AS amount_e6
                             FROM ledger_entries le JOIN counterparties p ON p.id=le.owner_id
                             JOIN transactions t ON t.id=le.transaction_id
                             JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=1
                             WHERE le.account_id=? AND le.date<=? AND t.status='POSTED'
                             GROUP BY p.id HAVING SUM(le.quantity_e6)<>0""", (account_id, day))
        totals.update({row["owner"]: int(row["amount_e6"]) for row in rows})
        for row in self.db.all("""SELECT owner,SUM(amount_e6) amount_e6 FROM money_from_others
                                 WHERE account_id=? AND date<=? AND transaction_id IS NULL GROUP BY owner""",
                               (account_id, day)):
            totals[row["owner"]] = totals.get(row["owner"], 0) + int(row["amount_e6"])
        return [{"owner": name, "amount_e6": amount, "amount": from_e6(amount)}
                for name, amount in sorted(totals.items()) if amount > 0]

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
        source = self.accounts.require_usable(source_id)
        target = self.accounts.require_usable(target_id)
        self._tag_exact_line(transaction_id, owner, source_id,
                             self.accounts.assets.cash_asset(source.currency).id, -to_e6(moved))
        self._tag_exact_line(transaction_id, owner, target_id,
                             self.accounts.assets.cash_asset(target.currency).id, to_e6(moved))

    def cash_balance(self, owner: str, account_id: int, as_of: str) -> Decimal:
        day = parse_date(as_of).isoformat()
        total = self.db.scalar("""SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le
                                JOIN transactions t ON t.id=le.transaction_id
                                JOIN counterparties p ON p.id=le.owner_id
                                JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=1
                                WHERE lower(p.name)=lower(?) AND le.account_id=? AND le.date<=?
                                AND t.status='POSTED'""", (owner.strip(), account_id, day)) or 0
        legacy = self.db.scalar("""SELECT COALESCE(SUM(amount_e6),0) FROM money_from_others
                                WHERE lower(owner)=lower(?) AND account_id=? AND date<=? AND transaction_id IS NULL""",
                                (owner.strip(), account_id, day)) or 0
        return from_e6(int(total) + int(legacy))

    def cash_total_for_account(self, account_id: int, as_of: str) -> Decimal:
        day = parse_date(as_of).isoformat()
        ledger = self.db.scalar("""SELECT COALESCE(SUM(le.quantity_e6),0) FROM ledger_entries le
                                JOIN transactions t ON t.id=le.transaction_id
                                JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=1
                                WHERE le.account_id=? AND le.owner_id IS NOT NULL AND le.date<=? AND t.status='POSTED'""",
                                (account_id, day)) or 0
        legacy = self.db.scalar("SELECT COALESCE(SUM(amount_e6),0) FROM money_from_others WHERE account_id=? AND date<=? AND transaction_id IS NULL",
                                (account_id, day)) or 0
        return from_e6(int(ledger) + int(legacy))

    def transaction_owner(self, transaction_id: int) -> str:
        row = self.db.one("SELECT p.name owner FROM ledger_entries le JOIN counterparties p ON p.id=le.owner_id WHERE le.transaction_id=? AND le.owner_id IS NOT NULL LIMIT 1", (transaction_id,))
        if row:
            return row["owner"]
        row = self.db.one("SELECT owner FROM money_from_others WHERE transaction_id=?", (transaction_id,))
        return row["owner"] if row else ""

    def investment_transaction_owner(self, transaction_id: int) -> str:
        row = self.db.one("SELECT p.name owner FROM ledger_entries le JOIN counterparties p ON p.id=le.owner_id JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=0 WHERE le.transaction_id=? AND le.owner_id IS NOT NULL LIMIT 1", (transaction_id,))
        if row:
            return row["owner"]
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
        self._tag_exact_line(transaction_id, owner, account_id, asset_id, units_e6)

    def totals_by_account(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        totals = {}
        for row in self.db.all("""SELECT le.account_id,SUM(le.quantity_e6) amount_e6 FROM ledger_entries le
                                JOIN transactions t ON t.id=le.transaction_id
                                JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=1
                                WHERE le.owner_id IS NOT NULL AND le.date<=? AND t.status='POSTED'
                                GROUP BY le.account_id""", (day,)):
            totals[row["account_id"]] = int(row["amount_e6"])
        for row in self.db.all("""SELECT account_id,SUM(amount_e6) amount_e6 FROM money_from_others
                                WHERE date<=? AND transaction_id IS NULL GROUP BY account_id""", (day,)):
            totals[row["account_id"]] = totals.get(row["account_id"], 0) + int(row["amount_e6"])
        return [{"account_id": account_id, "amount_e6": amount} for account_id, amount in totals.items()]

    def by_owner(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        sums = {}
        rows = self.db.all("""SELECT p.name owner,le.account_id,SUM(le.quantity_e6) amount_e6
                             FROM ledger_entries le JOIN counterparties p ON p.id=le.owner_id
                             JOIN transactions t ON t.id=le.transaction_id
                             JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=1
                             WHERE le.date<=? AND t.status='POSTED' GROUP BY p.id,le.account_id""", (day,))
        for row in rows:
            sums[(row["owner"], row["account_id"])] = int(row["amount_e6"])
        for row in self.db.all("""SELECT owner,account_id,SUM(amount_e6) amount_e6 FROM money_from_others
                                 WHERE date<=? AND transaction_id IS NULL GROUP BY owner,account_id""", (day,)):
            key = (row["owner"], row["account_id"])
            sums[key] = sums.get(key, 0) + int(row["amount_e6"])
        return [dict(owner=owner, account_id=account_id,
                     account_name=self.accounts.get(account_id).name,
                     currency=self.accounts.get(account_id).currency, amount_e6=amount_e6,
                     amount=from_e6(amount_e6))
                for (owner, account_id), amount_e6 in sorted(sums.items())]

    def history(self, limit: int = 100) -> list[dict]:
        rows = self.db.all(
            "SELECT m.*,a.name AS account_name,a.currency FROM money_from_others m JOIN accounts a ON a.id=m.account_id "
            "WHERE m.transaction_id IS NULL OR m.transaction_id IN (SELECT id FROM transactions WHERE status='POSTED') "
            "ORDER BY m.date DESC,m.id DESC LIMIT ?", (limit,))
        return [dict(row) | {"amount": from_e6(row["amount_e6"])} for row in rows]

    def investment_positions(self, as_of: str) -> list[dict]:
        day = parse_date(as_of).isoformat()
        rows = self.db.all(
            "SELECT p.name owner,le.account_id,le.asset_id,SUM(le.quantity_e6) AS units_e6 FROM ledger_entries le "
            "JOIN counterparties p ON p.id=le.owner_id JOIN transactions t ON t.id=le.transaction_id "
            "JOIN financial_assets f ON f.id=le.asset_id AND f.is_cash=0 "
            "WHERE le.date<=? AND t.status='POSTED' GROUP BY p.id,le.account_id,le.asset_id "
            "HAVING SUM(le.quantity_e6)<>0 ORDER BY owner,account_id,asset_id", (day,))
        return [dict(row) | {"units": from_e6(row["units_e6"])} for row in rows]

    def investment_history(self, limit: int = 100) -> list[dict]:
        rows = self.db.all(
            "SELECT e.date,e.owner,e.account_id,e.asset_id,e.units_e6,a.name AS account_name,"
            "f.name AS asset_name,f.unit,t.ref FROM investment_custody_events e "
            "JOIN transactions t ON t.id=e.transaction_id JOIN accounts a ON a.id=e.account_id "
            "JOIN financial_assets f ON f.id=e.asset_id WHERE t.status='POSTED' "
            "ORDER BY e.date DESC,e.id DESC LIMIT ?", (limit,))
        return [dict(row) | {"units": from_e6(row["units_e6"])} for row in rows]
