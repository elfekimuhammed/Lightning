"""Dummy data only: check native dependencies in an arm64 Android process, one line per check, so a
failure names the module and its error instead of stopping at the first one. Then (04b) run the shared
encrypted round-trip on the committed fixture and compare it line by line with what Windows and Linux give."""

import importlib
import pkgutil
import tempfile
from pathlib import Path


def _check(name, test):
    try:
        return f"OK  {name}: {test()}"
    except BaseException as error:  # noqa: BLE001 - every failure is reported, never raised
        return f"FAIL {name}: {type(error).__name__}: {error}"


def _sqlcipher():
    from sqlcipher3 import dbapi2
    conn = dbapi2.connect(":memory:")
    try:
        version = conn.execute("PRAGMA cipher_version").fetchone()
    finally:
        conn.close()
    if not version or not version[0]:
        raise RuntimeError("SQLCipher is unavailable")
    return "SQLCipher " + version[0]


def _argon2():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    Argon2id(salt=b"0" * 16, length=32, iterations=1, lanes=1, memory_cost=8).derive(b"probe")
    AESGCM(AESGCM.generate_key(bit_length=256))
    return "Argon2id and AES-GCM work"


def _roundtrip():
    """The report lines and timings; every line that differs from expected.json is listed."""
    from lightning.runtime.roundtrip import DB_NAME, EXPECTED_NAME, KEYS_NAME, RECOVERY_NAME, fingerprint, run
    import json

    with tempfile.TemporaryDirectory(prefix="fixture-") as folder:
        for name in (DB_NAME, KEYS_NAME, RECOVERY_NAME, EXPECTED_NAME):
            (Path(folder) / name).write_bytes(pkgutil.get_data("roundtrip_fixture", name))
        lines, seconds = run(folder)
        wanted = json.loads((Path(folder) / EXPECTED_NAME).read_text(encoding="utf-8"))
    if lines != wanted["lines"]:
        wrong = [f"  got {got!r}, expected {want!r}" for got, want in zip(lines, wanted["lines"]) if got != want]
        if len(lines) != len(wanted["lines"]):
            wrong.append(f"  {len(lines)} lines, expected {len(wanted['lines'])}")
        raise AssertionError("differs from Windows/Linux:\n" + "\n".join(wrong))
    timings = ", ".join(f"{name} {value:.2f} s" for name, value in seconds.items())
    return f"same figures, inventory and key recovery as Windows/Linux (fingerprint {fingerprint(lines)}); {timings}"


def run():
    lines = [_check(name, lambda name=name: getattr(importlib.import_module(name), "__version__", "loaded"))
             for name in ("_cffi_backend", "cryptography", "pydantic_core", "fastapi", "jinja2", "uvicorn")]
    lines += [_check("encryption", _argon2), _check("sqlcipher3", _sqlcipher)]
    lines += [_check("04b encrypted round-trip", _roundtrip)]
    return "\n".join(lines)
