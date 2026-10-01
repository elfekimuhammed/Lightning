"""Recovery keys and authenticated password slots for the SQLCipher data key."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {char: value for value, char in enumerate(_CROCKFORD)}
_DECODE.update({"O": 0, "I": 1, "L": 1})
_RECOVERY_CHECK_DOMAIN = b"lightning-rk-v1"
_KEY_ID_DOMAIN = b"lightning/key-id/v1"
_KEY_INFO = b"lightning/db-key/v1"
_KEY_SALT = b"lightning/v1"

# 64 MiB is the fixed normal profile. The parser accepts only bounded profiles so
# malformed documents cannot request unbounded memory or CPU before authentication.
ARGON2_MEMORY_KIB = 65536
ARGON2_ITERATIONS = 3
ARGON2_LANES = 4
_ARGON2_MEMORY_MIN_KIB = 32768
_ARGON2_MEMORY_MAX_KIB = 262144
_ARGON2_ITERATIONS_MIN = 2
_ARGON2_ITERATIONS_MAX = 6
_ARGON2_LANES_MIN = 1
_ARGON2_LANES_MAX = 4
_PASSWORD_MAX_BYTES = 4096
_MAX_DOCUMENT_BYTES = 16384
_SLOT_METADATA_KEYS = {"version", "type", "key_id", "kdf", "cipher", "salt", "nonce",
                       "memory_kib", "iterations", "lanes"}
_SLOT_KEYS = _SLOT_METADATA_KEYS | {"ciphertext"}


def _b32(value: int, bit_count: int) -> str:
    return "".join(
        _CROCKFORD[(value >> (bit_count - 5 * (index + 1))) & 31]
        for index in range(bit_count // 5)
    )


def _data_key(secret: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=_KEY_SALT, info=_KEY_INFO).derive(secret)


def generate_recovery() -> tuple[str, bytes]:
    """Create a printable 128-bit recovery key and its derived 32-byte data key."""
    secret = os.urandom(16)
    checksum = int.from_bytes(hashlib.sha256(_RECOVERY_CHECK_DOMAIN + secret).digest()[:2], "big") >> 4
    encoded = _b32((int.from_bytes(secret, "big") << 12) | checksum, 140)
    return "-".join(encoded[index:index + 4] for index in range(0, 28, 4)), _data_key(secret)


def recover_key(text: str) -> bytes:
    """Validate a recovery phrase and derive the corresponding SQLCipher key."""
    if not isinstance(text, str) or len(text) > 128:
        raise ValueError("Invalid recovery key.")
    chars = [char for char in text.upper() if char not in " -\t\r\n"]
    if len(chars) != 28 or any(char not in _DECODE for char in chars):
        raise ValueError("Invalid recovery key.")
    number = 0
    for char in chars:
        number = (number << 5) | _DECODE[char]
    secret, checksum = (number >> 12).to_bytes(16, "big"), number & 0xFFF
    expected = int.from_bytes(hashlib.sha256(_RECOVERY_CHECK_DOMAIN + secret).digest()[:2], "big") >> 4
    if not hmac.compare_digest(checksum.to_bytes(2, "big"), expected.to_bytes(2, "big")):
        raise ValueError("Invalid recovery key.")
    return _data_key(secret)


def key_id(key: bytes) -> str:
    """Return a non-secret 64-bit identifier for matching encrypted data and slots."""
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("The data key must be exactly 32 bytes.")
    return hmac.new(key, _KEY_ID_DOMAIN, hashlib.sha256).hexdigest()[:16]


def _password_bytes(password: str) -> bytes:
    if not isinstance(password, str):
        raise ValueError("Password must be text.")
    try:
        encoded = password.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Password is not valid UTF-8 text.") from exc
    if not 1 <= len(encoded) <= _PASSWORD_MAX_BYTES:
        raise ValueError("Password must be between 1 and 4096 UTF-8 bytes.")
    return encoded


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _decode_b64(value: Any, expected_length: int, label: str) -> bytes:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError(f"Invalid {label} encoding.")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {label} encoding.") from exc
    if len(decoded) != expected_length:
        raise ValueError(f"Invalid {label} length.")
    return decoded


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    return {name: document[name] for name in _SLOT_METADATA_KEYS}


def _validate_document(document: dict[str, Any]) -> tuple[bytes, bytes, bytes]:
    if not isinstance(document, dict) or set(document) != _SLOT_KEYS:
        raise ValueError("Invalid password slot fields.")
    try:
        encoded_size = len(_canonical(document))
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Invalid password slot document.") from exc
    if encoded_size > _MAX_DOCUMENT_BYTES:
        raise ValueError("Password slot document is too large.")
    if document["version"] != 1 or type(document["version"]) is not int:
        raise ValueError("Unsupported password slot version.")
    if document["type"] != "password" or document["cipher"] != "aes-256-gcm" or document["kdf"] != "argon2id":
        raise ValueError("Unsupported password slot type or algorithm.")
    kid = document["key_id"]
    if not isinstance(kid, str) or not re.fullmatch(r"[0-9a-f]{16}", kid):
        raise ValueError("Invalid key identifier.")
    memory, iterations, lanes = document["memory_kib"], document["iterations"], document["lanes"]
    if type(memory) is not int or not _ARGON2_MEMORY_MIN_KIB <= memory <= _ARGON2_MEMORY_MAX_KIB:
        raise ValueError("Argon2 memory cost is outside the supported bounds.")
    if type(iterations) is not int or not _ARGON2_ITERATIONS_MIN <= iterations <= _ARGON2_ITERATIONS_MAX:
        raise ValueError("Argon2 iteration count is outside the supported bounds.")
    if type(lanes) is not int or not _ARGON2_LANES_MIN <= lanes <= _ARGON2_LANES_MAX:
        raise ValueError("Argon2 lane count is outside the supported bounds.")
    salt = _decode_b64(document["salt"], 16, "salt")
    nonce = _decode_b64(document["nonce"], 12, "nonce")
    ciphertext = _decode_b64(document["ciphertext"], 48, "ciphertext")
    return salt, nonce, ciphertext


def wrap_key(key: bytes, password: str) -> dict[str, Any]:
    """Wrap a 32-byte data key in a password-authenticated, versioned JSON document."""
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("The data key must be exactly 32 bytes.")
    passphrase = _password_bytes(password)
    salt, nonce = os.urandom(16), os.urandom(12)
    document: dict[str, Any] = {
        "version": 1,
        "type": "password",
        "key_id": key_id(key),
        "kdf": "argon2id",
        "cipher": "aes-256-gcm",
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "memory_kib": ARGON2_MEMORY_KIB,
        "iterations": ARGON2_ITERATIONS,
        "lanes": ARGON2_LANES,
    }
    kek = Argon2id(salt=salt, length=32, iterations=ARGON2_ITERATIONS,
                   lanes=ARGON2_LANES, memory_cost=ARGON2_MEMORY_KIB).derive(passphrase)
    document["ciphertext"] = base64.b64encode(
        AESGCM(kek).encrypt(nonce, key, _canonical(document))
    ).decode("ascii")
    return document


def unwrap_key(document: dict[str, Any], password: str) -> bytes:
    """Validate and authenticate a password slot, returning its 32-byte data key."""
    passphrase = _password_bytes(password)
    salt, nonce, ciphertext = _validate_document(document)
    kek = Argon2id(salt=salt, length=32, iterations=document["iterations"],
                   lanes=document["lanes"], memory_cost=document["memory_kib"]).derive(passphrase)
    try:
        key = AESGCM(kek).decrypt(nonce, ciphertext, _canonical(_metadata(document)))
    except InvalidTag as exc:
        raise ValueError("Password slot authentication failed.") from exc
    if len(key) != 32 or not hmac.compare_digest(key_id(key), document["key_id"]):
        raise ValueError("Password slot key identifier does not match.")
    return key
