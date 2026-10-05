"""Focused tests for recovery/password primitives and the synthetic self-check."""

from copy import deepcopy

import pytest

from lightning.security import create_key_file, key_id, new_data_key, new_recovery_key, open_with_recovery, unwrap_key, wrap_key
from lightning.security.keys import (normalize_answer, normalize_recovery_key, proof_kind, suggest_password,
                                     validate_key_file, with_password, with_question, with_recovery_key)
from lightning.security.selfcheck import run_checks

QUESTION = "What was the name of your first school?"


def _key_file(answer="El Orman"):
    key, recovery = new_data_key(), new_recovery_key()
    return key, recovery, create_key_file(key, "a synthetic passphrase", recovery, QUESTION, answer)


def test_the_recovery_key_is_twelve_digits_typed_any_way():
    recovery = new_recovery_key()
    assert len(recovery) == 14 and recovery[4] == recovery[9] == "-"
    digits = recovery.replace("-", "")
    assert normalize_recovery_key(digits) == normalize_recovery_key(" ".join(digits)) == digits
    arabic = digits.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    assert normalize_recovery_key(arabic) == digits
    for wrong in ("1234-5678-901", "1234-5678-90123", "1234-5678-901a", ""):
        with pytest.raises(ValueError):
            normalize_recovery_key(wrong)


def test_answers_ignore_case_spaces_punctuation_and_arabic_variants():
    assert normalize_answer("  El   Orman ") == normalize_answer("el orman") == normalize_answer("EL ORMAN.")
    assert normalize_answer("مدرسة الأورمان") == normalize_answer("مدرسه الاورمان")
    assert normalize_answer("مُصْطَفَى") == normalize_answer("مصطفي")
    assert normalize_answer("٤٢ street") == normalize_answer("42 Street")
    with pytest.raises(ValueError):
        normalize_answer("  ...  ")


def test_the_key_file_has_two_locks_and_neither_secret_alone_opens_lock_two():
    key, recovery, document = _key_file()
    validate_key_file(document)
    assert unwrap_key(document, "a synthetic passphrase") == key
    assert open_with_recovery(document, recovery.replace("-", " "), "el ORMAN") == key
    with pytest.raises(ValueError):
        open_with_recovery(document, recovery, "Another school")
    other = new_recovery_key()
    with pytest.raises(ValueError):
        open_with_recovery(document, other if other != recovery else "0000-0000-0001", "El Orman")
    assert key_id(key) == document["key_id"] and document["password"]["key_id"] == document["recovery"]["key_id"]
    # The question is bound to lock 2: swapping it in the file breaks recovery instead of misleading.
    swapped = deepcopy(document)
    swapped["question"] = "What is your favourite colour?"
    with pytest.raises(ValueError):
        open_with_recovery(swapped, recovery, "El Orman")


def test_lock_two_is_the_slower_one():
    _, _, document = _key_file()
    password, recovery = document["password"], document["recovery"]
    assert recovery["memory_kib"] * recovery["iterations"] > password["memory_kib"] * password["iterations"]


def test_checks_tell_the_answer_from_the_recovery_key_only_with_the_data_key():
    key, recovery, document = _key_file()
    assert proof_kind(document, key, "el orman") == "answer"
    assert proof_kind(document, key, recovery) == "recovery"
    assert proof_kind(document, key, "guess") is None
    with pytest.raises(ValueError):
        proof_kind(document, new_data_key(), "el orman")


def test_changes_keep_the_same_data_key():
    key, recovery, document = _key_file()
    changed = with_password(document, key, "x")
    assert unwrap_key(changed, "x") == key and open_with_recovery(changed, recovery, "El Orman") == key
    changed = with_question(document, key, recovery, "Where did you grow up?", "Heliopolis")
    assert open_with_recovery(changed, recovery, "heliopolis") == key and changed["question"] == "Where did you grow up?"
    with pytest.raises(ValueError):
        with_question(document, key, "0000-0000-0000", "Where?", "Here")
    fresh = new_recovery_key()
    changed = with_recovery_key(document, key, "El Orman", fresh)
    assert open_with_recovery(changed, fresh, "El Orman") == key
    with pytest.raises(ValueError):
        open_with_recovery(changed, recovery, "El Orman")
    with pytest.raises(ValueError):
        with_recovery_key(document, key, "wrong answer", fresh)


def test_suggested_passwords_are_four_words():
    words = suggest_password().split()
    assert len(words) == 4 and all(word.isalpha() and word.islower() for word in words)
    assert len({suggest_password() for _ in range(20)}) == 20


def test_password_slot_roundtrip_and_authenticated_metadata():
    key = new_data_key()
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
    key = new_data_key()
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
