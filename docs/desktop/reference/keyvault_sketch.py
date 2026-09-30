"""Reference sketch (not production) for Lightning key management, design C' (recovery-key-rooted).

DEK = HKDF-SHA256(recovery_secret_128bit, info="lightning/db-key/v1")   -> SQLCipher raw key
Local unlock slots (keys.json in %LOCALAPPDATA%\\Lightning): DPAPI-wrapped DEK, or Argon2id(password)-wrapped DEK.
"""
from __future__ import annotations
import base64, hashlib, json, os, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {c: i for i, c in enumerate(CROCKFORD)} | {"O": 0, "I": 1, "L": 1}

def _b32(bits: int, nbits: int) -> str:
    return "".join(CROCKFORD[(bits >> (nbits - 5 * (i + 1))) & 31] for i in range(nbits // 5))

def new_recovery_key() -> tuple[str, bytes]:
    """128 random bits + 12-bit check = 140 bits = 28 chars, shown as 7 groups of 4."""
    secret = os.urandom(16)
    check = int.from_bytes(hashlib.sha256(b"lightning-rk-v1" + secret).digest()[:2], "big") >> 4
    n = (int.from_bytes(secret, "big") << 12) | check
    s = _b32(n, 140)
    return "-".join(s[i:i + 4] for i in range(0, 28, 4)), secret

def parse_recovery_key(text: str) -> bytes:
    chars = [c for c in text.upper() if c not in " -\t\r\n"]
    if len(chars) != 28 or any(c not in _DECODE for c in chars):
        raise ValueError("A recovery key has 28 letters and digits.")
    n = 0
    for c in chars:
        n = (n << 5) | _DECODE[c]
    secret, check = (n >> 12).to_bytes(16, "big"), n & 0xFFF
    if int.from_bytes(hashlib.sha256(b"lightning-rk-v1" + secret).digest()[:2], "big") >> 4 != check:
        raise ValueError("That recovery key has a typo.")
    return secret

def dek_from_recovery(secret: bytes) -> bytearray:
    return bytearray(HKDF(hashes.SHA256(), 32, salt=b"lightning/v1", info=b"lightning/db-key/v1").derive(secret))

def key_id(dek: bytes) -> str:  # non-secret fingerprint: which recovery-key generation this file uses
    import hmac
    return hmac.new(bytes(dek), b"lightning/key-id/v1", "sha256").hexdigest()[:16]

def wrap_with_password(dek: bytes, password: str, aad: bytes, m_kib=262144, t=3, p=4) -> dict:
    salt, nonce = os.urandom(16), os.urandom(12)
    kek = Argon2id(salt=salt, length=32, iterations=t, lanes=p, memory_cost=m_kib).derive(password.encode("utf-8"))
    ct = AESGCM(kek).encrypt(nonce, bytes(dek), aad)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"kdf": "argon2id", "m_kib": m_kib, "t": t, "p": p, "salt": b64(salt), "nonce": b64(nonce), "ct": b64(ct)}

def unwrap_with_password(slot: dict, password: str, aad: bytes) -> bytearray:
    d = base64.b64decode
    kek = Argon2id(salt=d(slot["salt"]), length=32, iterations=slot["t"], lanes=slot["p"],
                   memory_cost=slot["m_kib"]).derive(password.encode("utf-8"))
    return bytearray(AESGCM(kek).decrypt(d(slot["nonce"]), d(slot["ct"]), aad))  # InvalidTag -> wrong password

# --- Windows DPAPI via ctypes (no pywin32). Untested here (Linux); API per dpapi.h -------------
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    _crypt32, _kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    CRYPTPROTECT_UI_FORBIDDEN = 0x1          # never CRYPTPROTECT_LOCAL_MACHINE (0x4): any local user could decrypt
    _ENTROPY = b"Lightning/dpapi/db-key/v1"  # domain separation, NOT a secret

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _take(out: DATA_BLOB) -> bytearray:
        try:
            return bytearray(ctypes.string_at(out.pbData, out.cbData))
        finally:
            ctypes.memset(out.pbData, 0, out.cbData)
            _kernel32.LocalFree(out.pbData)

    def dpapi_protect(secret: bytes) -> bytes:
        out, ent = DATA_BLOB(), _blob(_ENTROPY)
        if not _crypt32.CryptProtectData(ctypes.byref(_blob(secret)), "Lightning database key", ctypes.byref(ent),
                                         None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
            raise ctypes.WinError()
        return bytes(_take(out))

    def dpapi_unprotect(blob: bytes) -> bytearray:
        out, ent = DATA_BLOB(), _blob(_ENTROPY)
        if not _crypt32.CryptUnprotectData(ctypes.byref(_blob(blob)), None, ctypes.byref(ent),
                                           None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
            raise ctypes.WinError()   # new PC / reinstalled Windows / forced password reset -> ask for recovery key
        return _take(out)

def wipe(buf: bytearray) -> None:
    import ctypes
    ctypes.memset((ctypes.c_char * len(buf)).from_buffer(buf), 0, len(buf))

if __name__ == "__main__":
    shown, secret = new_recovery_key()
    print("recovery key:", shown)
    assert parse_recovery_key(shown.lower().replace("-", " ")) == secret
    typo = ("X" if shown[0] != "X" else "Y") + shown[1:]
    try: parse_recovery_key(typo); print("typo not caught (1/4096 chance)")
    except ValueError as e: print("typo ->", e)
    dek = dek_from_recovery(secret); print("key id:", key_id(dek))
    aad = json.dumps({"format": "lightning-keys/1", "key_id": key_id(dek)}, sort_keys=True).encode()
    slot = wrap_with_password(dek, "tiger lantern orbit 42", aad)
    assert unwrap_with_password(slot, "tiger lantern orbit 42", aad) == dek
    print("password slot json bytes:", len(json.dumps(slot)))
    wipe(dek); print("wiped:", bytes(dek) == bytes(32))
