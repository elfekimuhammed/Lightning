"""No financial data: check native dependencies in an arm64 Android process, one line per check, so a
failure names the module and its error instead of stopping at the first one."""

import importlib


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


def run():
    lines = [_check(name, lambda name=name: getattr(importlib.import_module(name), "__version__", "loaded"))
             for name in ("_cffi_backend", "cryptography", "pydantic_core", "fastapi", "jinja2", "uvicorn")]
    lines += [_check("encryption", _argon2), _check("sqlcipher3", _sqlcipher)]
    return "\n".join(lines)
