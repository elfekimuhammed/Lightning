"""Read-only SQL for reports.

Reporting owns no tables; it reads the ledger (and later prices/FX) directly for speed.
Only POSTED transactions count. All sums are over exact integer (_e6) columns.
"""

from __future__ import annotations

from lightning.database.connection import Database

POSTED = "JOIN transactions t ON t.id = le.transaction_id AND t.status = 'POSTED'"
CASH_ONLY = "le.asset_id IN (SELECT id FROM financial_assets WHERE is_cash = 1)"


class ReportQueries:
    def __init__(self, db: Database):
        self.db = db

    def holdings(self, as_of: str) -> list[dict]:
        rows = self.db.all(
            f"SELECT le.account_id, le.asset_id, SUM(le.quantity_e6) AS quantity_e6,"
            f" SUM(le.amount_base_e6) AS cost_base_e6"
            f" FROM ledger_entries le {POSTED} WHERE le.date <= ?"
            f" GROUP BY le.account_id, le.asset_id",
            (as_of,),
        )
        return [dict(r) for r in rows]

    def flows_by_holding(self, date_from: str, date_to: str) -> list[dict]:
        rows = self.db.all(
            f"SELECT le.account_id, le.asset_id, SUM(le.quantity_e6) AS quantity_e6,"
            f" SUM(le.amount_base_e6) AS amount_base_e6"
            f" FROM ledger_entries le {POSTED} WHERE le.date BETWEEN ? AND ? AND le.effect<>'REVALUATION'"
            f" GROUP BY le.account_id, le.asset_id",
            (date_from, date_to),
        )
        return [dict(r) for r in rows]

    def effect_totals(self, date_from: str, date_to: str) -> dict[str, int]:
        rows = self.db.all(
            f"SELECT le.effect, SUM(le.amount_base_e6) AS total"
            f" FROM ledger_entries le {POSTED} WHERE le.date BETWEEN ? AND ?"
            " GROUP BY le.effect",
            (date_from, date_to),
        )
        return {r["effect"]: int(r["total"] or 0) for r in rows}

    def category_totals(self, date_from: str, date_to: str) -> list[dict]:
        rows = self.db.all(
            f"SELECT le.category_id, le.effect, SUM(le.amount_base_e6) AS total"
            f" FROM ledger_entries le {POSTED}"
            f" WHERE le.date BETWEEN ? AND ? AND le.category_id IS NOT NULL"
            f" AND le.effect IN ('INFLOW','OUTFLOW')"
            " AND COALESCE(le.category_id,0) NOT IN (SELECT id FROM categories WHERE code='EXP.SYSTEM.CUSTODY')"
            " AND le.owner_id IS NULL"
            " GROUP BY le.category_id, le.effect",
            (date_from, date_to),
        )
        return [dict(r) for r in rows]

    def category_totals_by_date(self, date_from: str, date_to: str, key_length: int = 10) -> list[dict]:
        """The same totals as category_totals, split by day (key_length 10, yyyy-mm-dd) or month (7)."""
        rows = self.db.all(
            f"SELECT substr(le.date, 1, ?) AS key, le.category_id, le.effect, SUM(le.amount_base_e6) AS total"
            f" FROM ledger_entries le {POSTED}"
            f" WHERE le.date BETWEEN ? AND ? AND le.category_id IS NOT NULL"
            f" AND le.effect IN ('INFLOW','OUTFLOW')"
            " AND COALESCE(le.category_id,0) NOT IN (SELECT id FROM categories WHERE code='EXP.SYSTEM.CUSTODY')"
            " AND le.owner_id IS NULL"
            " GROUP BY key, le.category_id, le.effect",
            (key_length, date_from, date_to),
        )
        return [dict(r) for r in rows]

    def spending_lines(self, date_from: str, date_to: str) -> list[dict]:
        """Categorised money in and out lines with their transaction, account and counterparty: the
        same lines as category_totals, one row per line."""
        rows = self.db.all(
            f"SELECT le.transaction_id, le.date, le.account_id, le.category_id, le.effect, le.amount_base_e6 AS amount,"
            f" t.ref, t.counterparty, t.description"
            f" FROM ledger_entries le {POSTED}"
            f" WHERE le.date BETWEEN ? AND ? AND le.category_id IS NOT NULL"
            f" AND le.effect IN ('INFLOW','OUTFLOW')"
            " AND COALESCE(le.category_id,0) NOT IN (SELECT id FROM categories WHERE code='EXP.SYSTEM.CUSTODY')"
            " AND le.owner_id IS NULL",
            (date_from, date_to),
        )
        return [dict(r) for r in rows]

    def monthly_effects(self, date_from: str, date_to: str) -> list[dict]:
        rows = self.db.all(
            f"SELECT substr(le.date, 1, 7) AS month, le.effect, SUM(le.amount_base_e6) AS total"
            f" FROM ledger_entries le {POSTED} WHERE le.date BETWEEN ? AND ?"
            " AND COALESCE(le.category_id,0) NOT IN (SELECT id FROM categories WHERE code='EXP.SYSTEM.CUSTODY')"
            " AND le.owner_id IS NULL"
            f" GROUP BY month, le.effect ORDER BY month",
            (date_from, date_to),
        )
        return [dict(r) for r in rows]

    def account_quantity(self, account_id: int, as_of: str | None = None, before: str | None = None) -> int:
        sql = f"SELECT SUM(le.quantity_e6) FROM ledger_entries le {POSTED} WHERE le.account_id = ? AND {CASH_ONLY}"
        params: list = [account_id]
        if as_of:
            sql += " AND le.date <= ?"
            params.append(as_of)
        if before:
            sql += " AND le.date < ?"
            params.append(before)
        return int(self.db.scalar(sql, tuple(params)) or 0)

    def category_transaction_ids(self, category_ids: set[int]) -> set[int]:
        if not category_ids:
            return set()
        marks = ",".join("?" for _ in category_ids)
        return {int(row["id"]) for row in self.db.all(
            f"SELECT DISTINCT t.id FROM transactions t JOIN ledger_entries le ON le.transaction_id=t.id "
            f"WHERE t.status='POSTED' AND le.category_id IN ({marks})", tuple(sorted(category_ids)))}

    def statement_lines(self, account_id: int | None, date_from: str, date_to: str) -> list[dict]:
        """Posted cash lines for one account (or every account when account_id is None) — the register."""
        where = f"le.date BETWEEN ? AND ? AND {CASH_ONLY}"
        params: list = [date_from, date_to]
        if account_id is not None:
            where = "le.account_id = ? AND " + where
            params.insert(0, account_id)
        rows = self.db.all(
            f"SELECT le.date, le.account_id, SUM(le.quantity_e6) AS quantity_e6, SUM(le.amount_e6) AS amount_e6,"
            f" MAX(le.effect) AS effect, CASE WHEN COUNT(*)=1 THEN MAX(le.category_id) END AS category_id,"
            f" CASE WHEN COUNT(*)=1 THEN MAX(le.memo) ELSE 'Split · ' || COUNT(DISTINCT le.category_id) || ' categories' END AS memo,"
            f" t.id AS txn_id, t.ref, t.type, t.description, t.counterparty, t.notes,"
            f" (SELECT o.account_id FROM ledger_entries o WHERE o.transaction_id = t.id"
            f"  AND o.account_id != le.account_id LIMIT 1) AS other_account_id"
            f" FROM ledger_entries le {POSTED}"
            f" WHERE {where}"
            f" GROUP BY le.date,le.account_id,t.id ORDER BY le.date, t.id",
            tuple(params),
        )
        return [dict(r) for r in rows]

    def latest_price(self, asset_id: int, as_of: str) -> dict | None:
        row = self.db.one(
            "SELECT price_e6, currency, date, source FROM price_history WHERE asset_id = ? AND date <= ?"
            " ORDER BY date DESC, CASE WHEN source IN ('MANUAL','REEVALUATION_MANUAL') THEN 0 ELSE 1 END LIMIT 1",
            (asset_id, as_of),
        )
        return dict(row) if row else None

    def latest_trade_price(self, asset_id: int, as_of: str) -> dict | None:
        """The price of the most recent buy or sell on or before the date."""
        row = self.db.one(
            f"SELECT le.unit_price_e6 AS price_e6, le.date FROM ledger_entries le {POSTED}"
            " WHERE le.asset_id = ? AND le.date <= ? AND t.type IN ('BUY', 'SEL')"
            " ORDER BY le.date DESC, t.id DESC LIMIT 1",
            (asset_id, as_of),
        )
        return dict(row) if row else None

    def average_opening_cost(self, asset_id: int, as_of: str) -> dict | None:
        """Cost per unit of holdings entered as already owned — the last resort for a value."""
        row = self.db.one(
            f"SELECT SUM(le.amount_e6) AS amount, SUM(le.quantity_e6) AS qty, MAX(le.date) AS date"
            f" FROM ledger_entries le {POSTED} WHERE le.asset_id = ? AND le.date <= ? AND t.type = 'OPN'",
            (asset_id, as_of),
        )
        return dict(row) if row and row["qty"] else None

    def investment_lines(self, as_of: str, account_id: int | None = None) -> list[dict]:
        """Every posted line of a non-cash asset (and dividend lines), oldest first — for positions."""
        where = "le.date <= ? AND (le.asset_id NOT IN (SELECT id FROM financial_assets WHERE is_cash = 1)" \
                " OR t.type = 'DIV')"
        params: list = [as_of]
        if account_id is not None:
            where += " AND le.account_id = ?"
            params.append(account_id)
        rows = self.db.all(
            f"SELECT le.date, le.account_id, le.asset_id, le.quantity_e6, le.amount_base_e6, le.memo,"
            f" da.asset_id AS dividend_asset_id,"
            f" t.id AS txn_id, t.type, t.ref FROM ledger_entries le {POSTED} "
            f"LEFT JOIN investment_dividend_assets da ON da.transaction_id=t.id WHERE {where}"
            f" ORDER BY le.date, t.id, le.line_no",
            tuple(params),
        )
        return [dict(r) for r in rows]

    def latest_fx(self, base: str, quote: str, as_of: str) -> dict | None:
        row = self.db.one(
            "SELECT rate_e6, date, source FROM fx_rates WHERE base = ? AND quote = ? AND date <= ?"
            " ORDER BY date DESC, CASE source WHEN 'MANUAL' THEN 0 ELSE 1 END LIMIT 1",
            (base, quote, as_of),
        )
        return dict(row) if row else None

    def first_entry_date(self) -> str | None:
        # Opening balances anchor an account; they are not activity for the All time view.
        return self.db.scalar(f"SELECT MIN(le.date) FROM ledger_entries le {POSTED} WHERE t.type<>'OPN'")
