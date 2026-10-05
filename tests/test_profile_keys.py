"""Owner decision 2026-10-05: password, 12-digit recovery key and security question.

One thing opens a profile; two things change one. While a profile is open, being open counts as the
password. Any two of password, recovery key and answer restore the third. Wrong tries wait, never lock.
"""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from lightning.runtime.session import FREE_TRIES, AttemptGuard, ProfileError, ProfileSession, key_file_copy

PASSWORD = "mango river taxi falcon"
QUESTION = "What was the name of your first school?"
ANSWER = "El Orman"


def _created(tmp_path):
    session = ProfileSession(tmp_path / "Documents" / "Lightning")
    pending = session.prepare("Home", PASSWORD, PASSWORD, QUESTION, ANSWER)
    session.confirm(pending.recovery)
    session.container.settings.set("marker", "mine")
    return session, pending.recovery, str(session.paths.db_path)


def test_setup_creates_the_profile_only_once_the_key_is_typed_back(tmp_path):
    session = ProfileSession(tmp_path / "Documents" / "Lightning")
    pending = session.prepare("Home", "x", "x", QUESTION, ANSWER)  # any length is allowed
    assert re.fullmatch(r"\d{4}-\d{4}-\d{4}", pending.recovery)
    wrong = "0000-0000-0000" if pending.recovery != "0000-0000-0000" else "1111-1111-1111"
    with pytest.raises(ProfileError, match="recovery key shown"):
        session.confirm(wrong)
    assert session.pending is pending and session.container is None  # a typo keeps the setup open
    session.confirm(pending.recovery.replace("-", " "))
    keys = json.loads(session.paths.keys_path.read_text())
    assert keys["version"] == 2 and keys["question"] == QUESTION
    assert json.loads(key_file_copy(session.paths).read_text()) == keys
    assert ANSWER.encode() not in session.paths.keys_path.read_bytes()
    session.close()


def test_setup_needs_a_question_and_answer(tmp_path):
    session = ProfileSession(tmp_path / "Documents" / "Lightning")
    with pytest.raises(ProfileError, match="question"):
        session.prepare("Home", PASSWORD, PASSWORD, "", ANSWER)
    with pytest.raises(ProfileError, match="answer"):
        session.prepare("Home", PASSWORD, PASSWORD, QUESTION, " ")


def test_forgot_the_password_the_key_and_answer_set_a_new_one(tmp_path):
    session, recovery, path = _created(tmp_path)
    session.close()
    with pytest.raises(ProfileError, match="do not open"):
        session.recover(path, recovery, "Another school", "new one", "new one")
    session.recover(path, recovery, "el orman", "new one", "new one")
    session.unlock(path, "new one")
    assert session.container.settings.get("marker") == "mine"
    session.close()


def test_an_open_profile_changes_the_password_with_the_answer_or_the_key(tmp_path):
    session, recovery, path = _created(tmp_path)
    with pytest.raises(ProfileError, match="not your security answer or your recovery key"):
        session.change_password("a guess", "second", "second")
    session.change_password("EL ORMAN", "second", "second")
    session.change_password(recovery, "third", "third")
    session.close()
    with pytest.raises(ProfileError, match="incorrect"):
        session.unlock(path, PASSWORD)
    session.unlock(path, "third")
    session.close()


def test_forgot_the_answer_an_open_profile_and_the_key_set_a_new_question(tmp_path):
    session, recovery, path = _created(tmp_path)
    with pytest.raises(ProfileError, match="not your recovery key"):
        session.change_question(ANSWER, "Where did you grow up?", "Heliopolis")  # the answer is not enough
    session.change_question(recovery, "Where did you grow up?", "Heliopolis")
    assert session.current_question() == "Where did you grow up?"
    session.close()
    with pytest.raises(ProfileError):
        session.recover(path, recovery, ANSWER, "new", "new")
    session.recover(path, recovery, "heliopolis", "new", "new")


def test_lost_the_key_an_open_profile_and_the_answer_make_a_new_one(tmp_path):
    session, old, path = _created(tmp_path)
    with pytest.raises(ProfileError, match="not your security answer"):
        session.prepare_recovery_key(old)  # the old key is not the answer
    pending = session.prepare_recovery_key(ANSWER)
    with pytest.raises(ProfileError, match="recovery key shown"):
        session.confirm_recovery_key(old)
    session.close()
    session.recover(path, old, ANSWER, "still old", "still old")  # nothing changed until typed back
    session.unlock(path, "still old")
    pending = session.prepare_recovery_key(ANSWER)
    session.confirm_recovery_key(pending.recovery)
    session.close()
    with pytest.raises(ProfileError):
        session.recover(path, old, ANSWER, "new", "new")
    session.recover(path, pending.recovery, ANSWER, "new", "new")


def test_a_deleted_or_damaged_key_file_comes_back_from_its_copy(tmp_path):
    session, recovery, path = _created(tmp_path)
    keys = session.paths.keys_path
    session.close()
    keys.write_text("{}")
    session.unlock(path, PASSWORD)
    assert json.loads(keys.read_text())["version"] == 2  # repaired from the copy
    session.close()
    keys.unlink()
    session.recover(path, recovery, ANSWER, "fresh", "fresh")
    assert keys.is_file()


def test_wrong_tries_wait_longer_but_never_lock_for_good(tmp_path):
    now = [1_000_000.0]
    guard = AttemptGuard(tmp_path / "attempts.json", clock=lambda: now[0])
    for _ in range(FREE_TRIES):
        guard.check()
        guard.failed()
    with pytest.raises(ProfileError, match="1 minute"):
        guard.check()
    now[0] += 60
    guard.check()
    guard.failed()
    with pytest.raises(ProfileError, match="5 minutes"):
        guard.check()
    for wait in (300, 900, 3600, 3600):
        now[0] += wait
        guard.check()
        guard.failed()
    with pytest.raises(ProfileError, match="1 hour"):
        guard.check()
    now[0] += 3600
    guard.succeeded()
    guard.check()


def test_wrong_passwords_wait_even_for_the_right_one(tmp_path, monkeypatch):
    session, _, path = _created(tmp_path)
    session.close()
    for _ in range(FREE_TRIES):
        with pytest.raises(ProfileError, match="incorrect"):
            session.unlock(path, "wrong")
    with pytest.raises(ProfileError, match="Too many wrong tries"):
        session.unlock(path, PASSWORD)
    import time
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 61)
    session.unlock(path, PASSWORD)
    session.close()


def test_the_pages_offer_a_suggestion_and_ask_for_the_second_proof(tmp_path):
    from lightning.runtime.app import profile_app
    from lightning.runtime.http import Credentials

    cfg = Credentials("http://127.0.0.1:9876")
    app = profile_app(cfg, tmp_path / "Documents" / "Lightning")
    browser = TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin})

    def csrf(text):
        return re.search(r'name="csrf" value="([^"]+)"', text).group(1)

    with browser:
        browser.get("/__launch", params={"code": cfg.launch_code})
        page = browser.get("/profiles/new").text
        suggestion = re.search(r'name="suggestion" value="([^"]+)"', page).group(1)
        assert len(suggestion.split()) == 4 and "Security question" in page
        page = browser.post("/profiles/new", data={"csrf": csrf(page), "name": "Home", "suggestion": suggestion,
                                                   "use_suggestion": "yes", "question": QUESTION, "answer": ANSWER}).text
        assert suggestion in page  # the chosen password is shown once, to write down
        recovery = re.search(r'aria-label="Recovery key">([0-9-]+)<', page).group(1)
        wrong = browser.post("/profiles/confirm", data={"csrf": csrf(page), "recovery": "1"})
        assert wrong.status_code == 400 and recovery in wrong.text  # the key stays on screen to try again
        browser.post("/profiles/confirm", data={"csrf": csrf(wrong.text), "recovery": recovery})
        manage = browser.get("/profiles").text
        for heading in ("Change password", "Change security question", "New recovery key"):
            assert heading in manage
        assert "Current password" not in manage and QUESTION in manage
        path = str(app.session.paths.db_path)
        browser.post("/profiles/lock", data={"csrf": csrf(manage)})
        page = browser.get("/profiles/recover", params={"db": path}).text
        assert QUESTION in page
        done = browser.post("/profiles/recover", data={"csrf": csrf(page), "db": path, "recovery": recovery,
                                                       "answer": "el orman", "password": "short", "confirm": "short"})
        assert "Password reset" in done.text
        page = browser.post("/profiles/unlock", data={"csrf": csrf(done.text), "db": path, "password": "short"})
        assert page.status_code == 200 and app.session.container is not None
