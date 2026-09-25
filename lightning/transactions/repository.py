"""SQL for transactions and ledger_entries. Only this module writes them."""

from __future__ import annotations

import re
import sqlite3

from lightning.core.dates import now_iso
from lightning.core.ledger import Effect, PostingLine
from lightning.core.money import from_e6, to_e6
from lightning.core.refs import DocType, parse_ref
from lightning.database.connection import Database

from .domain import LedgerLine, Transaction, TxnFilter, TxnSource, TxnStatus  # noqa: F401


def _line(row: sqlite3.Row) -> LedgerLine:
    return LedgerLine(
        id=row["id"],
        transaction_id=row["transaction_id"],
        line_no=row["line_no"],
        date=row["date"],
        account_id=row["account_id"],
        asset_id=row["asset_id"],
        quantity=from_e6(row["quantity_e6"]),
        unit_price=from_e6(row["unit_price_e6"]),
        amount=from_e6(row["amount_e6"]),
        fx_rate=from_e6(row["fx_rate_e6"]),
        amount_base=from_e6(row["amount_base_e6"]),
        effect=Effect(row["effect"]),
        category_id=row["category_id"],
        claim_id=row["claim_id"],
        memo=row["memo"],
    )


def _header(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        ref=row["ref"],
        type=DocType(row["type"]),
        date=row["date"],
        description=row["description"],
        counterparty=row["counterparty"],
        status=TxnStatus(row["status"]),
        source=TxnSource(row["source"]),
        notes=row["notes"],
        search_text=row["search_text"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def fts_query(text: str) -> str:
    """User text -> safe FTS5 query: every word must match, as a prefix."""
    terms = [t.replace('"', "") for t in re.findall(r"\S+", text or "")]
    return " ".join(f'"{t}"*' for t in terms if t.strip())


class TransactionRepository:
    def __init__(self, db: Database):
        self.db = db
        self._fts: bool | None = None

    @property
    def has_fts(self) -> bool:
        if self._fts is None:
            self._fts = self.db.has_table("transactions_fts")
        return self._fts

    # -- refs --------------------------------------------------------------
    def next_seq(self, prefix: str) -> int:
        rows = self.db.all("SELECT ref FROM transactions WHERE ref LIKE ?", (prefix + "%",))
        return max((parse_ref(r["ref"])[2] for r in rows), default=0) + 1

    # -- writing -----------------------------------------------------------
    def insert(self, t: Transaction, lines: list[PostingLine]) -> int:
        now = now_iso()
        cur = self.db.execute(
            "INSERT INTO transactions(ref, type, date, description, counterparty, status, source,"
            " notes, search_text, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                t.ref,
                t.type.value,
                t.date,
                t.description,
                t.counterparty,
                t.status.value,
                t.source.value,
                t.notes,
                t.search_text,
                now,
                now,
            ),
        )
        txn_id = int(cur.lastrowid)
        self._insert_lines(txn_id, t.date, lines)
        return txn_id

    def update_header(self, t: Transaction) -> None:
        self.db.execute(
            "UPDATE transactions SET date=?, description=?, counterparty=?, status=?, notes=?,"
            " updated_at=? WHERE id=?",
            (t.date, t.description, t.counterparty, t.status.value, t.notes, now_iso(), t.id),
        )

    def replace_lines(self, txn_id: int, date: str, lines: list[PostingLine]) -> None:
        self.db.execute("DELETE FROM ledger_entries WHERE transaction_id = ?", (txn_id,))
        self._insert_lines(txn_id, date, lines)

    def set_status(self, txn_id: int, status: TxnStatus) -> None:
        self.db.execute(
            "UPDATE transactions SET status=?, updated_at=? WHERE id=?", (status.value, now_iso(), txn_id)
        )

    def set_search_text(self, txn_id: int, text: str) -> None:
        self.db.execute("UPDATE transactions SET search_text=? WHERE id=?", (text, txn_id))

    def _insert_lines(self, txn_id: int, date: str, lines: list[PostingLine]) -> None:
        for n, line in enumerate(lines, start=1):
            self.db.execute(
                "INSERT INTO ledger_entries(transaction_id, line_no, date, account_id, asset_id,"
                " quantity_e6, unit_price_e6, amount_e6, fx_rate_e6, amount_base_e6, effect,"
                " category_id, claim_id, memo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    txn_id,
                    n,
                    date,
                    line.account_id,
                    line.asset_id,
                    to_e6(line.quantity),
                    to_e6(line.unit_price),
                    to_e6(line.amount),
                    to_e6(line.fx_rate),
                    to_e6(line.amount_base),
                    line.effect.value,
                    line.category_id,
                    line.claim_id,
                    line.memo,
                ),
            )

    # -- reading -----------------------------------------------------------
    def get(self, txn_id: int) -> Transaction | None:
        row = self.db.one("SELECT * FROM transactions WHERE id = ?", (txn_id,))
        if not row:
            return None
        t = _header(row)
        t.lines = self.lines_for([t.id])[t.id]
        return t

    def get_by_ref(self, ref: str) -> Transaction | None:
        txn_id = self.db.scalar("SELECT id FROM transactions WHERE ref = ?", (ref,))
        return self.get(txn_id) if txn_id else None

    def lines_for(self, txn_ids: list[int]) -> dict[int, list[LedgerLine]]:
        result: dict[int, list[LedgerLine]] = {i: [] for i in txn_ids}
        for start in range(0, len(txn_ids), 500):
            chunk = txn_ids[start : start + 500]
            marks = ",".join("?" * len(chunk))
            for row in self.db.all(
                f"SELECT * FROM ledger_entries WHERE transaction_id IN ({marks}) ORDER BY transaction_id, line_no",
                tuple(chunk),
            ):
                result[row["transaction_id"]].append(_line(row))
        return result

    def list(self, f: TxnFilter) -> tuple[list[Transaction], int]:
        where, params = ["1=1"], []
        if not f.include_void:
            where.append("t.status != 'VOID'")
        if f.account_id is not None:
            where.append("EXISTS (SELECT 1 FROM ledger_entries le WHERE le.transaction_id = t.id AND le.account_id = ?)")
            params.append(f.account_id)
        if f.category_ids:
            marks = ",".join("?" * len(f.category_ids))
            where.append(
                f"EXISTS (SELECT 1 FROM ledger_entries le WHERE le.transaction_id = t.id AND le.category_id IN ({marks}))"
            )
            params.extend(f.category_ids)
        if f.types:
            where.append(f"t.type IN ({','.join('?' * len(f.types))})")
            params.extend(t.value for t in f.types)
        if f.date_from:
            where.append("t.date >= ?")
            params.append(f.date_from)
        if f.date_to:
            where.append("t.date <= ?")
            params.append(f.date_to)
        if f.search.strip():
            query = fts_query(f.search)
            if self.has_fts and query:
                where.append("t.id IN (SELECT rowid FROM transactions_fts WHERE transactions_fts MATCH ?)")
                params.append(query)
            else:
                for term in re.findall(r"\S+", f.search):
                    where.append("t.search_text LIKE ?")
                    params.append(f"%{term}%")
        clause = " AND ".join(where)
        total = self.db.scalar(f"SELECT COUNT(*) FROM transactions t WHERE {clause}", tuple(params)) or 0
        rows = self.db.all(
            f"SELECT t.* FROM transactions t WHERE {clause} ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?",
            (*params, f.limit, f.offset),
        )
        txns = [_header(r) for r in rows]
        lines = self.lines_for([t.id for t in txns])
        for t in txns:
            t.lines = lines[t.id]
        return txns, int(total)

    def ids_touching_accounts(self, account_ids: list[int]) -> list[int]:
        marks = ",".join("?" * len(account_ids))
        rows = self.db.all(
            f"SELECT DISTINCT transaction_id FROM ledger_entries WHERE account_id IN ({marks})", tuple(account_ids)
        )
        return [r[0] for r in rows]

    def ids_touching_categories(self, category_ids: list[int]) -> list[int]:
        marks = ",".join("?" * len(category_ids))
        rows = self.db.all(
            f"SELECT DISTINCT transaction_id FROM ledger_entries WHERE category_id IN ({marks})",
            tuple(category_ids),
        )
        return [r[0] for r in rows]

    def opening_txn_id(self, account_id: int) -> int | None:
        return self.db.scalar(
            "SELECT t.id FROM transactions t JOIN ledger_entries le ON le.transaction_id = t.id"
            " WHERE t.type = 'OPN' AND t.status != 'VOID' AND le.account_id = ? ORDER BY t.id LIMIT 1",
            (account_id,),
        )

    def payee_categories(self) -> dict[str, int]:
        rows = self.db.all(
            "SELECT t.counterparty AS payee, le.category_id, MAX(t.date || printf('%010d', t.id)) AS latest"
            " FROM transactions t JOIN ledger_entries le ON le.transaction_id = t.id"
            " WHERE t.status = 'POSTED' AND t.counterparty != '' AND le.category_id IS NOT NULL"
            " GROUP BY t.counterparty ORDER BY latest DESC LIMIT 500"
        )
        return {r["payee"]: r["category_id"] for r in rows}

    def earliest_activity(self, account_id: int) -> str | None:
        return self.db.scalar(
            "SELECT MIN(le.date) FROM ledger_entries le JOIN transactions t ON t.id = le.transaction_id"
            " WHERE le.account_id = ? AND t.status = 'POSTED' AND t.type != 'OPN'",
            (account_id,),
        )

    def count_for_account(self, account_id: int) -> int:
        return int(
            self.db.scalar(
                "SELECT COUNT(DISTINCT le.transaction_id) FROM ledger_entries le"
                " JOIN transactions t ON t.id = le.transaction_id"
                " WHERE le.account_id = ? AND t.status != 'VOID'",
                (account_id,),
            )
            or 0
        )
