"""Monthly investment return checkpoints and their linked account-level journal entries."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from lightning.accounts.service import AccountService
from lightning.core.dates import fmt_date, now_iso, parse_date, parse_month, today
from lightning.core.errors import ValidationError
from lightning.core.ledger import PostingLine
from lightning.core.money import ONE, ZERO, from_e6, to_e6
from lightning.core.refs import DocType
from lightning.database.connection import Database
from lightning.reporting.service import ReportingService
from lightning.transactions.domain import TxnSource
from lightning.transactions.service import TransactionService


class ReevaluationService:
    def __init__(self, db: Database, accounts: AccountService, transactions: TransactionService,
                 reporting: ReportingService):
        self.db, self.accounts, self.transactions, self.reporting = db, accounts, transactions, reporting

    def process_due(self, fetch_price=None) -> int:
        """Record every elapsed month-end in chronological order; incomplete periods await user prices."""
        first = self.db.scalar(
            "SELECT MIN(le.date) FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
            "JOIN financial_assets a ON a.id=le.asset_id WHERE t.status='POSTED' AND a.is_cash=0")
        if not first:
            return 0
        first_day = parse_date(first)
        last_day = today()
        cursor = date(first_day.year, first_day.month, 1)
        events: set[tuple[str, str]] = set()
        while cursor <= last_day:
            month_end = date(cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1])
            if month_end <= last_day:
                events.add((fmt_date(month_end), "MONTH_END"))
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        events.update((row["date"], row["reason"]) for row in self.db.all(
            "SELECT date,reason FROM reevaluation_periods WHERE status='PENDING'"))
        completed = 0
        for day, reason in sorted(events, key=lambda item: (item[0], item[1] != "SALE")):
            if reason == "MONTH_END" and self.db.scalar(
                    "SELECT 1 FROM reevaluation_periods WHERE date=? AND reason='SALE' AND status='POSTED'", (day,)):
                continue
            focus = forced = None
            if reason == "SALE":
                sale_rows = self.db.all(
                    "SELECT le.account_id,le.asset_id,le.unit_price_e6 FROM ledger_entries le "
                    "JOIN transactions t ON t.id=le.transaction_id JOIN financial_assets a ON a.id=le.asset_id "
                    "WHERE t.status='POSTED' AND t.type='SEL' AND t.date=? AND a.is_cash=0 AND le.quantity_e6<0",
                    (day,))
                focus = {(r["account_id"], r["asset_id"]) for r in sale_rows}
                forced = {r["asset_id"]: from_e6(r["unit_price_e6"]) for r in sale_rows}
                if not focus:
                    continue
            if self.process_date(day, reason, fetch_price=fetch_price, focus=focus, forced_prices=forced):
                completed += 1
            else:
                break
        return completed

    def process_sale(self, day: str, account_id: int, asset_id: int, price: Decimal) -> bool:
        """Force an asset checkpoint at its sale price on the sale date."""
        if self.db.scalar("SELECT 1 FROM reevaluation_periods WHERE status='PENDING' AND date<? LIMIT 1", (day,)):
            with self.db.transaction():
                self.db.execute("INSERT INTO reevaluation_periods(date,reason,status,created_at) "
                                "VALUES(?,'SALE','PENDING',?) ON CONFLICT(date,reason) DO NOTHING",
                                (day, now_iso()))
            return False
        return self.process_date(day, "SALE", fetch_price=None, focus={(account_id, asset_id)},
                                 forced_prices={asset_id: price})

    def process_date(self, day: str | date, reason: str, fetch_price=None,
                     focus: set[tuple[int, int]] | None = None,
                     forced_prices: dict[int, Decimal] | None = None) -> bool:
        day = fmt_date(parse_date(day))
        if reason not in {"MONTH_END", "SALE"}:
            raise ValidationError("Unknown reevaluation checkpoint.")
        with self.db.transaction():
            self.db.execute("INSERT INTO reevaluation_periods(date,reason,status,created_at) VALUES(?,?, 'PENDING',?) "
                            "ON CONFLICT(date,reason) DO NOTHING", (day, reason, now_iso()))
            period_id = self.db.scalar("SELECT id FROM reevaluation_periods WHERE date=? AND reason=?", (day, reason))
            if self.db.scalar("SELECT status FROM reevaluation_periods WHERE id=?", (period_id,)) == "POSTED":
                return True
            self.db.execute("DELETE FROM reevaluation_entries WHERE period_id=?", (period_id,))
            rows = self.reporting.q.holdings(day)
            positions = {(r["account_id"], r["asset_id"]): int(r["quantity_e6"])
                         for r in rows if int(r["quantity_e6"] or 0)}
            if focus:
                for key in focus:
                    positions.setdefault(key, 0)
                positions = {k: v for k, v in positions.items() if k in focus}
            incomplete = False
            account_returns: dict[int, Decimal] = {}
            for (account_id, asset_id), units_e6 in sorted(positions.items()):
                asset = self.reporting.assets.get_asset(asset_id)
                if asset.is_cash:
                    continue
                forced = (forced_prices or {}).get(asset_id)
                found = (forced, "TRADE") if forced is not None else self._price(asset_id, day)
                if found is None and fetch_price:
                    found = fetch_price(asset, day)
                    if found:
                        price, source = found
                        self.reporting.assets.set_price(asset_id, day, price, source=source)
                if not found:
                    incomplete = True
                    self.db.execute(
                        "INSERT INTO reevaluation_entries(period_id,account_id,asset_id,units_e6,currency,needs_price) "
                        "VALUES(?,?,?,?,?,1)", (period_id, account_id, asset_id, units_e6, asset.currency))
                    continue
                price, source = found
                units = from_e6(units_e6)
                valuation = self.reporting.value_of(asset_id, units, day)
                if valuation.value is None:
                    incomplete = True
                    self.db.execute(
                        "INSERT INTO reevaluation_entries(period_id,account_id,asset_id,units_e6,price_e6,currency,"
                        "price_source,needs_price) VALUES(?,?,?,?,?,?,?,1)",
                        (period_id, account_id, asset_id, units_e6, to_e6(price), asset.currency, source))
                    continue
                prior = self.db.one(
                    "SELECT e.value_base_e6,p.date FROM reevaluation_entries e JOIN reevaluation_periods p "
                    "ON p.id=e.period_id WHERE e.account_id=? AND e.asset_id=? AND p.date<? AND e.needs_price=0 "
                    "ORDER BY p.date DESC,p.id DESC LIMIT 1", (account_id, asset_id, day))
                flow_start = fmt_date(parse_date(prior["date"]) + timedelta(days=1)) if prior else None
                flow_sql = "SELECT COALESCE(SUM(amount_base_e6),0) FROM ledger_entries le JOIN transactions t " \
                           "ON t.id=le.transaction_id WHERE t.status='POSTED' AND le.account_id=? AND le.asset_id=? " \
                           "AND le.date<=?"
                params: list = [account_id, asset_id, day]
                if flow_start:
                    flow_sql += " AND le.date>=?"
                    params.append(flow_start)
                flows = from_e6(self.db.scalar(flow_sql, tuple(params)) or 0)
                prior_value = from_e6(prior["value_base_e6"]) if prior else ZERO
                ret = valuation.value - prior_value - flows
                self.db.execute(
                    "INSERT INTO reevaluation_entries(period_id,account_id,asset_id,units_e6,price_e6,currency,"
                    "value_base_e6,return_base_e6,price_source,needs_price) VALUES(?,?,?,?,?,?,?,?,?,0)",
                    (period_id, account_id, asset_id, units_e6, to_e6(price), asset.currency,
                     to_e6(valuation.value), to_e6(ret), source))
                account_returns[account_id] = account_returns.get(account_id, ZERO) + ret
            if incomplete:
                return False
            for account_id, amount_base in sorted(account_returns.items()):
                account = self.accounts.get(account_id)
                cash_asset = self.reporting.assets.cash_asset(account.currency)
                fx = self.reporting.valuer._fx(account.currency, day)
                if fx is None:
                    return False
                amount = amount_base / fx
                journal = self.transactions.post(
                    DocType.VAL, day,
                    [PostingLine.revaluation(account_id, cash_asset.id, amount, fx,
                                             f"Investment revaluation · {reason.lower()}")],
                    description="Investment revaluation", counterparty="", notes=f"System-generated · {reason}",
                    source=TxnSource.SYSTEM)
                self.db.execute("INSERT INTO reevaluation_account_posts(period_id,account_id,transaction_id,"
                                "amount_base_e6) VALUES(?,?,?,?)",
                                (period_id, account_id, journal.id, to_e6(amount_base)))
                self.db.execute("UPDATE reevaluation_entries SET journal_transaction_id=? "
                                "WHERE period_id=? AND account_id=?",
                                (journal.id, period_id, account_id))
            self.db.execute("UPDATE reevaluation_periods SET status='POSTED' WHERE id=?", (period_id,))
        return True

    def _price(self, asset_id: int, day: str):
        found = self.reporting.valuer._price(self.reporting.assets.get_asset(asset_id), day)
        if not found or found[2] == "COST":
            return None
        price, price_date, source = found
        if (parse_date(day) - parse_date(price_date)).days > 10:
            return None
        return price, source

    def pending_prices(self) -> list[dict]:
        return [dict(row) for row in self.db.all(
            "SELECT DISTINCT p.date,e.asset_id,a.name AS asset_name,a.code AS asset_code,e.currency "
            "FROM reevaluation_entries e JOIN reevaluation_periods p ON p.id=e.period_id "
            "JOIN financial_assets a ON a.id=e.asset_id WHERE e.needs_price=1 AND p.status='PENDING' "
            "ORDER BY p.date,a.name")]

    def history(self, limit: int = 300) -> list[dict]:
        rows = self.db.all(
            "SELECT p.date,p.reason,p.status,e.account_id,a.name AS account_name,e.asset_id,f.name AS asset_name,"
            "e.units_e6,e.price_e6,e.currency,e.value_base_e6,e.return_base_e6,e.price_source,e.needs_price,"
            "e.journal_transaction_id,t.ref FROM reevaluation_entries e "
            "JOIN reevaluation_periods p ON p.id=e.period_id JOIN accounts a ON a.id=e.account_id "
            "JOIN financial_assets f ON f.id=e.asset_id LEFT JOIN transactions t ON t.id=e.journal_transaction_id "
            "ORDER BY p.date DESC,a.name,f.name LIMIT ?", (limit,))
        return [dict(row) | {key: (from_e6(row[key]) if row[key] is not None else None)
                             for key in ("units_e6", "price_e6", "value_base_e6", "return_base_e6")}
                for row in rows]

    def record_manual_price(self, asset_id: int, day: str, price: Decimal, fetch_price=None) -> int:
        self.reporting.assets.set_price(asset_id, day, price, source="REEVALUATION_MANUAL")
        periods = self.db.all("SELECT DISTINCT p.date,p.reason FROM reevaluation_periods p "
                              "JOIN reevaluation_entries e ON e.period_id=p.id WHERE e.asset_id=? AND p.date>=? "
                              "AND p.status='PENDING' ORDER BY p.date,p.id", (asset_id, day))
        done = 0
        for period in periods:
            done += bool(self.process_date(period["date"], period["reason"], fetch_price))
            if not self.db.scalar("SELECT status FROM reevaluation_periods WHERE date=? AND reason=?",
                                  (period["date"], period["reason"])) == "POSTED":
                break
        return done
