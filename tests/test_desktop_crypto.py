"""Focused tests for recovery/password primitives and the synthetic self-check."""

from copy import deepcopy

import pytest

from lightning.security import generate_recovery, key_id, recover_key, unwrap_key, wrap_key
from lightning.security.selfcheck import run_checks


def test_recovery_key_roundtrip_and_typo_detection():
    phrase, key = generate_recovery()
    assert len(key) == 32
    assert recover_key(phrase.lower().replace("-", " ")) == key
    assert key_id(key) == key_id(recover_key(phrase))
    # Flip one checksum bit, not random secret bits (which can collide 1/4096).
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    changed = phrase[:-1] + alphabet[alphabet.index(phrase[-1]) ^ 1]
    with pytest.raises(ValueError):
        recover_key(changed)


def test_password_slot_roundtrip_and_authenticated_metadata():
    _, key = generate_recovery()
    slot = wrap_key(key, "a synthetic passphrase")
    assert slot["version"] == 1
    assert slot["type"] == "password"
    assert unwrap_key(slot, "a synthetic passphrase") == key
    with pytest.raises(ValueError):
        unwrap_key(slot, "a different passphrase")

    changed = deepcopy(slot)
    changed["iterations"] += 1
    with pytest.raises(ValueError):
        unwrap_key(changed, "a synthetic passphrase")

    changed = deepcopy(slot)
    changed["ciphertext"] = ("A" if changed["ciphertext"][0] != "A" else "B") + changed["ciphertext"][1:]
    with pytest.raises(ValueError):
        unwrap_key(changed, "a synthetic passphrase")


@pytest.mark.parametrize("field,value", [
    ("version", 999),
    ("type", "dpapi"),
    ("memory_kib", 1_000_000_000),
    ("iterations", True),
    ("lanes", 0),
])
def test_password_slot_rejects_unsupported_or_unbounded_parameters(field, value):
    _, key = generate_recovery()
    slot = wrap_key(key, "a synthetic passphrase")
    slot[field] = value
    with pytest.raises(ValueError):
        unwrap_key(slot, "a synthetic passphrase")


def test_selfcheck_reports_only_aggregate_results():
    result = run_checks()
    assert result["ok"] is True
    assert all(isinstance(value, bool) for value in result.values())
    assert result["recovery_roundtrip"]
    assert result["password_roundtrip"]
    assert result["password_tamper_rejected"]
    assert result["sqlcipher_raw_key"]
    assert result["synthetic_database"]
    assert result["encrypted_backup"]
    assert result["wrong_key_rejected"]
    assert result["stdlib_sqlite_rejected"]
    assert result["integrity_check"]
    assert result["cipher_integrity_check"]
