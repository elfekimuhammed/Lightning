"""Reviewed, idempotent bank CSV imports into the transaction ledger."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation

from lightning.categories.domain import Movement
from lightning.core.dates import now_iso, parse_date
from lightning.core.errors import ConflictError, NotFoundError, ValidationError
from lightning.core.refs import DocType
from lightning.transactions.domain import TxnSource

REQUIRED = ("Date", "Amount")
OPTIONAL = ("Counterparty", "Category", "Notes", "Reference")
SEPARATE_AMOUNT_FIELDS = ("Inflow", "Outflow")
MAX_BYTES = 5 * 1024 * 1024


def _date(value: str) -> str:
    try:
        return parse_date(value).isoformat()
    except ValidationError as exc:
        raise ValueError(exc.message) from None


def _decimal_amount(value: str) -> Decimal:
    try:
        text = (value or "").strip().replace(" ", "")
        if not text:
            return Decimal("0")
        if "," in text and ("." not in text or text.rfind(",") > text.rfind(".")):
            tail = text.rsplit(",", 1)[1]
            text = text.replace(".", "").replace(",", ".") if len(tail) == 2 else text.replace(",", "")
        else:
            text = text.replace(",", "")
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidOperation
        return amount
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid number.") from None


def _amount(value: str) -> str:
    amount = _decimal_amount(value)
    if amount == 0:
        raise ValueError("Enter a non-zero amount; use a minus sign for money out.")
    return format(amount, "f")


def _separate_amount(inflow: str, outflow: str) -> str:
    incoming, outgoing = _decimal_amount(inflow), _decimal_amount(outflow)
    if incoming and outgoing:
        raise ValueError("A row cannot have both an inflow and an outflow amount.")
    if not incoming and not outgoing:
        raise ValueError("Enter an amount in either the inflow or outflow column.")
    signed = abs(incoming) if incoming else -abs(outgoing)
    return format(signed, "f")


def decode_csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    if len(data) > MAX_BYTES:
        raise ValidationError("CSV files must be 5 MB or smaller.", "file")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError("Save the statement as a UTF-8 CSV file.", "file") from None
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
        reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
        headers = [str(h or "").strip() for h in (reader.fieldnames or [])]
        if not headers or any(not h for h in headers):
            raise ValidationError("The CSV needs a header row with column names.", "file")
        if len(set(headers)) != len(headers):
            raise ValidationError("CSV headers must be unique; rename duplicate columns and try again.", "file")
        rows = []
        for line, row in enumerate(reader, start=2):
            rows.append({h: str(row.get(h, "") or "").strip() for h in headers} | {"__line__": str(line)})
        return headers, rows
    except csv.Error as exc:
        raise ValidationError(f"Could not read this CSV: {exc}", "file") from None


class BankImportService:
    def __init__(self, db, accounts, categories, counterparties, transactions, money_from_others=None, reserves=None):
        self.db, self.accounts, self.categories = db, accounts, categories
        self.counterparties, self.transactions = counterparties, transactions
        self.money_from_others = money_from_others
        self.reserves = reserves

    def suggested_mapping(self, account_id: int, headers: list[str]) -> dict[str, str]:
        """Return saved or best-effort column matches for the reviewable map step."""
        signature = hashlib.sha256(json.dumps(headers, ensure_ascii=False).encode()).hexdigest()
        saved = self.db.one("SELECT mapping_json,invert_amount FROM bank_import_column_maps WHERE account_id=? AND header_signature=?",
                            (account_id, signature))
        if saved:
            return json.loads(saved["mapping_json"]) | {"amount_sign": "invert" if saved["invert_amount"] else "normal"}
        normalized = {header: " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in header).split())
                      for header in headers}
        aliases = {
            "Date": ("date", "transaction date", "posting date", "booking date", "value date"),
            "Amount": ("amount", "transaction amount", "net amount", "value"),
            "Inflow": ("inflow", "money in", "credit", "credits", "deposit", "deposits"),
            "Outflow": ("outflow", "money out", "debit", "debits", "withdrawal", "withdrawals"),
            "Counterparty": ("counterparty", "merchant", "payee", "beneficiary", "party", "name"),
            "Category": ("category", "type"),
            "Notes": ("notes", "memo", "narrative", "details", "description"),
            "Reference": ("reference", "ref", "transaction id", "transaction reference"),
        }
        result = {}
        for target, names in aliases.items():
            found = next((header for header, name in normalized.items() if name in names), None)
            if found:
                result[target] = found
        if "Amount" in result:
            result["amount_model"] = "SINGLE"
        elif "Inflow" in result and "Outflow" in result and result["Inflow"] != result["Outflow"]:
            result["amount_model"] = "SEPARATE"
        else:
            result["amount_model"] = "SINGLE"
        return result

    def stage(self, account_id: int, filename: str, data: bytes, mapping: dict[str, str] | None = None, invert_amount: bool = False):
        self.accounts.require_usable(account_id)
        digest = hashlib.sha256(data).hexdigest()
        attempts = self.db.all("SELECT id,status,file_hash FROM bank_import_batches WHERE account_id=? "
                               "AND (file_hash=? OR file_hash LIKE ?) ORDER BY id DESC",
                               (account_id, digest, digest + "#%"))
        file_hash = digest
        if attempts:
            old = attempts[0]
            if old["status"] == "REVIEW":
                file_hash = old["file_hash"]
            else:
                # Preserve every posted import attempt, but let an intentional
                # re-upload go through review again (including duplicate flags).
                file_hash = f"{digest}#{len(attempts) + 1}"
            if old["status"] == "REVIEW":
                with self.db.transaction():
                    self.db.execute("DELETE FROM bank_import_rows WHERE batch_id=?", (old["id"],))
                    self.db.execute("DELETE FROM bank_import_batches WHERE id=?", (old["id"],))
        headers, raw_rows = decode_csv(data)
        header_signature = hashlib.sha256(json.dumps(headers, ensure_ascii=False).encode()).hexdigest()
        saved = self.db.one("SELECT mapping_json,invert_amount FROM bank_import_column_maps WHERE account_id=? AND header_signature=?",
                            (account_id, header_signature))
        if mapping is None and saved:
            mapping = json.loads(saved["mapping_json"])
        if mapping is None:
            if all(key in headers for key in SEPARATE_AMOUNT_FIELDS) and "Amount" not in headers:
                mapping = {"amount_model": "SEPARATE", "Date": "Date", "Inflow": "Inflow", "Outflow": "Outflow"}
            else:
                mapping = {"amount_model": "SINGLE"} | {key: key for key in (*REQUIRED, *OPTIONAL) if key in headers}
        amount_model = str(mapping.get("amount_model") or
                           ("SEPARATE" if any(mapping.get(key) for key in SEPARATE_AMOUNT_FIELDS) else "SINGLE"))
        if amount_model not in {"SINGLE", "SEPARATE"}:
            raise ValidationError("Choose one amount column or separate inflow/outflow columns.", "mapping")
        fields = ("Date", *SEPARATE_AMOUNT_FIELDS, *OPTIONAL) if amount_model == "SEPARATE" else (*REQUIRED, *OPTIONAL)
        missing = [key for key in (("Date", *SEPARATE_AMOUNT_FIELDS) if amount_model == "SEPARATE" else REQUIRED)
                   if mapping.get(key) not in headers]
        if amount_model == "SEPARATE" and mapping.get("Inflow") == mapping.get("Outflow"):
            missing.append("different inflow and outflow columns")
        if missing:
            raise ValidationError(
                "Map Date and either a signed Amount column or two different columns for Inflow and Outflow.", "mapping")
        stored = []
        for raw in raw_rows:
            parsed = {key: raw.get(mapping.get(key, ""), "") for key in fields}
            for key in ("Amount", *SEPARATE_AMOUNT_FIELDS):
                parsed.setdefault(key, "")
            errors = []
            try:
                parsed["Date"] = _date(parsed["Date"])
                parsed["Amount"] = (_separate_amount(parsed["Inflow"], parsed["Outflow"])
                                     if amount_model == "SEPARATE" else _amount(parsed["Amount"]))
                if invert_amount:
                    parsed["Amount"] = format(-Decimal(parsed["Amount"]), "f")
            except ValueError as exc:
                errors.append(str(exc))
            parsed["_line"] = raw["__line__"]
            parsed["_errors"] = errors
            stored.append((raw, parsed))
        now = now_iso()
        with self.db.transaction():
            canonical_fields = ("Date", *SEPARATE_AMOUNT_FIELDS, *OPTIONAL) if amount_model == "SEPARATE" else (*REQUIRED, *OPTIONAL)
            if mapping and (saved is not None or amount_model == "SEPARATE"
                            or any(mapping.get(key) != key for key in canonical_fields if mapping.get(key)) or invert_amount):
                self.db.execute("INSERT INTO bank_import_column_maps(account_id,header_signature,mapping_json,invert_amount,created_at,updated_at) "
                                "VALUES (?,?,?,?,?,?) ON CONFLICT(account_id,header_signature) DO UPDATE SET "
                                "mapping_json=excluded.mapping_json,invert_amount=excluded.invert_amount,updated_at=excluded.updated_at",
                                (account_id, header_signature, json.dumps(mapping | {"amount_model": amount_model}),
                                 int(invert_amount), now, now))
            cur = self.db.execute(
                "INSERT INTO bank_import_batches(account_id,file_hash,file_name,status,created_at) "
                "VALUES (?,?,?,'REVIEW',?)", (account_id, file_hash, filename[:255], now)
            )
            batch_id = int(cur.lastrowid)
            for raw, parsed in stored:
                ref = parsed["Reference"].strip() or None
                self.db.execute(
                    "INSERT INTO bank_import_rows(batch_id,row_number,raw_json,bank_reference,status) "
                    "VALUES (?,?,?,?,?)", (batch_id, int(raw["__line__"]),
                    json.dumps({"raw": raw, "parsed": parsed}, ensure_ascii=False), ref, "REVIEW")
                )
        return batch_id, False

    def preview(self, batch_id: int):
        batch = self.db.one("SELECT * FROM bank_import_batches WHERE id=?", (batch_id,))
        if not batch:
            raise NotFoundError("Import batch not found.")
        rows = self.db.all("SELECT * FROM bank_import_rows WHERE batch_id=? ORDER BY row_number", (batch_id,))
        result = []
        seen_refs = set()
        for row in rows:
            record = json.loads(row["raw_json"])
            parsed = record["parsed"]
            ref_duplicate = bool(row["bank_reference"] and (row["bank_reference"] in seen_refs or self.db.scalar(
                "SELECT 1 FROM bank_import_rows r JOIN bank_import_batches b ON b.id=r.batch_id "
                "JOIN transactions t ON t.id=r.transaction_id AND t.status='POSTED' "
                "WHERE b.account_id=? AND r.bank_reference=? AND b.id<>? AND r.status='POSTED' LIMIT 1",
                (batch["account_id"], row["bank_reference"], batch_id))))
            if row["bank_reference"]:
                seen_refs.add(row["bank_reference"])
            cp = self.counterparties.resolve(parsed["Counterparty"])
            parsed["_counterparty_id"] = cp["id"] if cp else None
            parsed["_suggestions"] = self.counterparties.suggestions(parsed["Counterparty"])
            parsed["_reference_duplicate"] = ref_duplicate
            parsed["_similarity_warning"] = self._similarity_warning(batch["account_id"], parsed)
            parsed["_category_id"] = self._category_for(parsed, cp)
            parsed["_import_row_id"] = row["id"]
            parsed["_status"] = row["status"]
            parsed["_transaction_id"] = row["transaction_id"]
            result.append(parsed)
        return batch, result

    def _category_for(self, parsed, counterparty):
        if parsed["Category"]:
            try:
                return self.categories.find_by_text(parsed["Category"]).id
            except ValidationError:
                pass
        if counterparty and counterparty["default_category_id"]:
            return counterparty["default_category_id"]
        recent = self.transactions.counterparty_suggestions()
        return recent.get(parsed["Counterparty"])

    def _similarity_warning(self, account_id, parsed):
        if parsed["Reference"] or parsed["_errors"]:
            return False
        amount = Decimal(parsed["Amount"])
        targets = self.db.all("SELECT id FROM accounts WHERE active=1 AND lower(name)=lower(?)",
                              (parsed["Counterparty"].strip(),))
        target = targets[0] if len(targets) == 1 else None
        if target:
            transfer = self.db.scalar(
                "SELECT 1 FROM transactions t "
                "JOIN ledger_entries mine ON mine.transaction_id=t.id AND mine.account_id=? "
                "JOIN ledger_entries other ON other.transaction_id=t.id AND other.account_id=? "
                "WHERE t.status='POSTED' AND t.type='TRF' AND t.date=? "
                "AND mine.amount_e6=? AND other.amount_e6=? LIMIT 1",
                # The imported row is from this account's point of view. If it
                # is the other side of an existing transfer, its signed amount
                # must match this account's existing ledger line exactly.
                (account_id, target["id"], parsed["Date"], int(amount * 1_000_000), int(-amount * 1_000_000)),
            )
            if transfer:
                return True
        row = self.db.one(
            "SELECT 1 FROM transactions t JOIN ledger_entries l ON l.transaction_id=t.id "
            "WHERE t.status='POSTED' AND t.date=? AND t.counterparty=? AND l.account_id=? "
            "AND l.amount_e6=? LIMIT 1",
            (parsed["Date"], parsed["Counterparty"], account_id, int(amount * 1_000_000)),
        )
        return bool(row)

    def confirm(self, batch_id: int, decisions: dict[int, dict]):
        batch = self.db.one("SELECT * FROM bank_import_batches WHERE id=?", (batch_id,))
        if not batch:
            raise NotFoundError("Import batch not found.")
        if batch["status"] == "POSTED":
            raise ConflictError("This statement has already been posted.")
        _, rows = self.preview(batch_id)
        row_by_id = {r["_import_row_id"]: r for r in rows}
        accounts = self.accounts.list(active_only=True)
        with self.db.transaction():
            for row_id, decision in decisions.items():
                row = row_by_id.get(int(row_id))
                if not row:
                    continue
                if decision.get("skip"):
                    skip_status = "DUPLICATE" if row["_reference_duplicate"] or row["_similarity_warning"] else "SKIPPED"
                    self.db.execute("UPDATE bank_import_rows SET status=? WHERE id=?", (skip_status, row_id))
                    continue
                if self.db.scalar("SELECT status FROM bank_import_rows WHERE id=?", (row_id,)) != "REVIEW":
                    continue
                cp_text = str(decision.get("counterparty", row["Counterparty"])).strip()
                try:
                    day = _date(str(decision.get("date", row["Date"])))
                    amount = Decimal(_amount(str(decision.get("amount", row["Amount"]))))
                except ValueError as exc:
                    raise ValidationError(f"CSV row {row['_line']}: {exc}", "row") from None
                notes = str(decision.get("notes", row["Notes"])).strip()
                account_matches = [a for a in accounts if a.name.casefold() == cp_text.casefold()]
                if len(account_matches) > 1:
                    raise ValidationError(f"CSV row {row['_line']}: account name is ambiguous; use a unique name.",
                                          "counterparty")
                target = account_matches[0] if account_matches else None
                counterparty_id = decision.get("counterparty_id") or (row["_counterparty_id"] if cp_text == row["Counterparty"] else None)
                if cp_text and not counterparty_id:
                    exact = self.counterparties.resolve(cp_text)
                    counterparty_id = exact["id"] if exact else None
                similar = self.counterparties.suggestions(cp_text) if cp_text and not counterparty_id else []
                choice = str(decision.get("counterparty_choice", ""))
                if choice.startswith("existing:"):
                    counterparty_id = int(choice.split(":", 1)[1])
                elif choice == "unlinked":
                    counterparty_id = None
                elif choice == "new":
                    name = str(decision.get("new_counterparty", cp_text)).strip()
                    if name:
                        counterparty_id = self.counterparties.create(name, alias=cp_text or None)
                if counterparty_id and cp_text and not target:
                    self.counterparties.add_alias(int(counterparty_id), cp_text)
                category_id = None if decision.get("force_uncategorized") else (decision.get("category_id") or row["_category_id"])
                if category_id:
                    category_id = int(category_id)
                else:
                    fallback_code = "EXP.UNACCOUNTED" if amount < 0 else "INC.UNACCOUNTED"
                    category_id = self.categories.repo.get_by_code(fallback_code).id
                if decision.get("remember_category") and counterparty_id and category_id:
                    self.counterparties.set_default_category(int(counterparty_id), int(category_id))
                if target:
                    txn = self.transactions.record_transfer(
                        day, batch["account_id"] if amount < 0 else target.id,
                        target.id if amount < 0 else batch["account_id"], abs(amount),
                        notes=notes, source=TxnSource.IMPORT,
                    )
                else:
                    movement = Movement.OUTFLOW if amount < 0 else Movement.INFLOW
                    self.categories.require(int(category_id), movement, allow_system=True)
                    category = self.categories.get(int(category_id))
                    owner = None
                    if category.code == "EXP.PERSONAL.CUSTODY":
                        whom = str(decision.get("whom", "")).strip()
                        if whom.casefold() in {"self", "me", "my money", "my own money"}:
                            party = None
                        else:
                            party = self.counterparties.resolve(whom)
                        if not party or not party["active"]:
                            if whom.casefold() not in {"self", "me", "my money", "my own money"}:
                                raise ValidationError(f"CSV row {row['_line']}: choose a saved active Counterparty in Whom.", "whom")
                        else:
                            owner = party["name"]
                    canonical = self.counterparties.get(int(counterparty_id)) if counterparty_id else None
                    linked_name = canonical["name"] if canonical else ("" if similar or choice == "unlinked" else cp_text)
                    kwargs = {"source": TxnSource.IMPORT, "counterparty": linked_name, "notes": notes}
                    if amount < 0:
                        txn = self.transactions.record_outflow(day, batch["account_id"], abs(amount), int(category_id),
                                                              allow_system_category=True, **kwargs)
                    elif category.movement == Movement.OUTFLOW:
                        txn = self.transactions.record_refund(day, batch["account_id"], amount, int(category_id), **kwargs)
                    else:
                        txn = self.transactions.record_inflow(day, batch["account_id"], amount, int(category_id),
                                                             allow_system_category=True, **kwargs)
                    if owner and self.money_from_others:
                        self.money_from_others.sync_transaction(txn.id, txn.date, owner, batch["account_id"], amount, notes)
                    if counterparty_id:
                        self.db.execute("UPDATE transactions SET counterparty_id=? WHERE id=?",
                                        (int(counterparty_id), txn.id))
                self.db.execute("UPDATE bank_import_rows SET status='POSTED',transaction_id=? WHERE id=?",
                                (txn.id, row_id))
                if self.reserves:
                    self.reserves.auto_link_transaction(txn.id)
            self.db.execute("UPDATE bank_import_rows SET status='SKIPPED' WHERE batch_id=? AND status='REVIEW'", (batch_id,))
            self.db.execute("UPDATE bank_import_batches SET status='POSTED',posted_at=? WHERE id=?",
                            (now_iso(), batch_id))
        return self.summary(batch_id)

    def summary(self, batch_id: int) -> dict[str, int]:
        counts = {row["status"]: row["n"] for row in self.db.all(
            "SELECT status,COUNT(*) AS n FROM bank_import_rows WHERE batch_id=? GROUP BY status", (batch_id,))}
        return {"posted": counts.get("POSTED", 0), "skipped": counts.get("SKIPPED", 0),
                "duplicates": counts.get("DUPLICATE", 0)}
