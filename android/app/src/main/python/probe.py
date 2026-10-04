"""No financial data: check native dependencies in an arm64 Android process."""

import fastapi
import jinja2
import uvicorn
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from sqlcipher3 import dbapi2


def run():
    conn = dbapi2.connect(":memory:")
    try:
        version = conn.execute("PRAGMA cipher_version").fetchone()
        if not version or not version[0]:
            raise RuntimeError("SQLCipher is unavailable")
    finally:
        conn.close()
    assert AESGCM and Argon2id and fastapi and jinja2 and uvicorn
    return "Python and Lightning's native dependencies loaded; SQLCipher " + version[0]
