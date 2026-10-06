"""Encrypted round-trip on any device (multiple devices, task 04b), with dummy data only.

Copy one committed encrypted profile (`tests/fixtures/roundtrip`), open it with its password, read its figures,
write one expense, close, reopen and read them again, then open it with the recovery key and set a new
password. The report holds no timing or path, so Android, Windows and Linux must produce exactly the same
lines; `expected.json` beside the fixture holds them. Timings are returned separately (for task 04d).

    python -m lightning.runtime.roundtrip tests/fixtures/roundtrip           # print the report
    python -m lightning.runtime.roundtrip --make tests/fixtures/roundtrip    # rebuild fixture and expected

Rebuild only when a change to the schema or seed changes the expected lines, and say so in the changelog.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path
from time import perf_counter

from lightning.bootstrap import build
from lightning.database.connection import Database
from lightning.security.keys import (create_key_file, new_data_key, new_recovery_key, open_with_recovery,
                                     unwrap_key, with_password)

PASSWORD = "dummy round-trip password"
NEW_PASSWORD = "dummy password after recovery"
QUESTION = "Dummy question?"
ANSWER = "Dummy answer"
AS_OF = date(2026, 6, 30)
DB_NAME, KEYS_NAME, RECOVERY_NAME, EXPECTED_NAME = "profile.db", "keys.json", "recovery.txt", "expected.json"


def _figures(container, label: str) -> list[str]:
    worth = container.reporting.net_worth(AS_OF)
    flow = container.reporting.cash_flow(AS_OF.replace(day=1), AS_OF)
    lines = [f"{label} net worth: {worth.total}", f"{label} unvalued: {len(worth.unvalued)}"]
    lines += [f"{label} account {account.name}: {value}" for account, value in worth.by_account]
    lines += [f"{label} June money in: {flow.inflows}", f"{label} June money out: {flow.outflows}"]
    return lines


def _inventory(db: Database) -> list[str]:
    tables = [row[0] for row in db.all(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return [f"rows {name}: " + str(db.scalar(f'SELECT count(*) FROM "{name}"')) for name in tables]


def _rejected(open_rows) -> bool:
    try:
        open_rows()
    except Exception:  # noqa: BLE001 - any refusal counts; reading rows does not
        return True
    return False


def _stdlib_rows(path: Path) -> None:
    plain = sqlite3.connect(path)
    try:
        plain.execute("SELECT count(*) FROM sqlite_master").fetchone()
    finally:
        plain.close()


def _wrong_key_rows(path: Path) -> None:
    db = Database(path, key=bytes(32))
    try:
        db.conn
    finally:
        db.close()


def run(fixture: str | Path, recovery_key: str | None = None) -> tuple[list[str], dict[str, float]]:
    """(report lines, seconds per step). Works on a temporary copy; the fixture is never changed."""
    fixture = Path(fixture)
    document = json.loads((fixture / KEYS_NAME).read_text(encoding="utf-8"))
    recovery = recovery_key or (fixture / RECOVERY_NAME).read_text(encoding="utf-8").strip()
    lines: list[str] = []
    seconds: dict[str, float] = {}

    def timed(name, step):
        started = perf_counter()
        result = step()
        seconds[name] = round(perf_counter() - started, 3)
        return result

    with tempfile.TemporaryDirectory(prefix="lightning-roundtrip-") as folder:
        path = Path(folder) / DB_NAME
        shutil.copyfile(fixture / DB_NAME, path)
        backups = Path(folder) / "backups"
        key = timed("unlock (password)", lambda: unwrap_key(document, PASSWORD))
        container = timed("open", lambda: build(path, key=key, backup_dir=backups))
        try:
            lines.append(f"schema: {container.db.scalar('SELECT max(version) FROM schema_migrations')}")
            lines += _figures(container, "before")
            account = next(a for a, _ in container.reporting.net_worth(AS_OF).by_account if a.name == "CIB Payroll")
            food = container.categories.get_by_code("EXP.PERSONAL.FOOD").id
            timed("write", lambda: container.transactions.record_outflow(
                AS_OF.isoformat(), account.id, "123.45", food, counterparty="Round-trip grocer"))
        finally:
            container.db.close()

        lines.append(f"plain SQLite refused: {_rejected(lambda: _stdlib_rows(path))}")
        lines.append(f"wrong key refused: {_rejected(lambda: _wrong_key_rows(path))}")
        recovered = timed("unlock (recovery key)", lambda: open_with_recovery(document, recovery, ANSWER))
        lines.append(f"recovery key opens the data key: {recovered == key}")
        renewed = with_password(document, recovered, NEW_PASSWORD)
        lines.append(f"new password opens: {unwrap_key(renewed, NEW_PASSWORD) == key}")
        lines.append(f"old password refused: {_rejected(lambda: unwrap_key(renewed, PASSWORD))}")

        container = timed("reopen", lambda: build(path, key=unwrap_key(renewed, NEW_PASSWORD), backup_dir=backups))
        try:
            db = container.db
            lines.append(f"integrity: {db.scalar('PRAGMA integrity_check')}")
            lines.append(f"cipher integrity problems: {len(db.all('PRAGMA cipher_integrity_check'))}")
            lines += _figures(container, "after")
            lines += _inventory(db)
        finally:
            container.db.close()
    return lines, seconds


def fingerprint(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def expected(fixture: str | Path) -> list[str]:
    return json.loads((Path(fixture) / EXPECTED_NAME).read_text(encoding="utf-8"))["lines"]


def make(fixture: str | Path) -> None:
    """Build a new encrypted dummy profile (the demo household up to AS_OF) and its expected report."""
    from lightning.demo import build_demo

    fixture = Path(fixture)
    fixture.mkdir(parents=True, exist_ok=True)
    key, recovery = new_data_key(), new_recovery_key()
    document = create_key_file(key, PASSWORD, recovery, QUESTION, ANSWER)
    (fixture / DB_NAME).unlink(missing_ok=True)
    container = build(fixture / DB_NAME, key=key, backup_dir=Path(tempfile.mkdtemp()))
    try:
        build_demo(container, as_of=AS_OF)
        container.db.execute("VACUUM")
    finally:
        container.db.close()
    (fixture / KEYS_NAME).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    (fixture / RECOVERY_NAME).write_text(recovery + "\n", encoding="utf-8")  # dummy profile only
    lines, _ = run(fixture)
    (fixture / EXPECTED_NAME).write_text(json.dumps({"fingerprint": fingerprint(lines), "lines": lines},
                                                    indent=1) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if argv[:1] == ["--make"]:
        make(argv[1])
        return 0
    lines, seconds = run(argv[0])
    print("\n".join(lines))
    print("fingerprint", fingerprint(lines), "matches" if lines == expected(argv[0]) else "DIFFERS")
    print(seconds)
    return 0 if lines == expected(argv[0]) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
