"""Multi-device task 06a: a reader session opens a real read-only connection and changes nothing.

Plan section 5, rule 10: no migration, seed, backup, payment matching or form bypasses the role gate,
and readers use actual read-only SQLCipher connections. Task 01's two-node fixture
(`tests/test_sync_write_inventory.py`) opened its borrower directly; these open it through the session.
"""
from __future__ import annotations

import hashlib
import html
import re
from collections import deque
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from lightning.bootstrap import ReadOnlyCopyError, build
from lightning.core.dates import fmt_date, today
from lightning.demo import build_demo
from lightning.runtime.roles import READ_ONLY_REFUSAL, SessionRole
from lightning.runtime.session import ProfileError, ProfileSession
from lightning.ui.web import create_app

PASSWORD = "a correct long passphrase"


def _digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(folder) -> set[str]:
    return {p.name for p in folder.rglob("*") if p.is_file()}


def _unmatched_bill(c) -> None:
    """A bill already paid by a posted transaction that nothing has linked yet: opening the Overview
    links it, which is a write."""
    account = c.account_flows.open_account("CIB", "BANK", "2026-01-01", "10000")
    rent = c.categories.get_by_code("EXP.PERSONAL.HOUSING")
    due = today() - timedelta(days=1)
    item_id = c.planning.create(kind="BILL", name="Rent", amount="3000", frequency="MONTHLY",
                                start_date=fmt_date(due), account_id=str(account.id), category_id=str(rent.id))
    c.transactions.record_outflow(fmt_date(due), account.id, "3000", rent.id)
    item = c.planning.get(item_id)
    assert c.planning.payments(item, due, today())[0].status.value == "DUE"


def test_a_reader_build_skips_every_startup_write(tmp_path):
    path = tmp_path / "copy.db"
    build(path).db.close()
    before, files = _digest(path), _files(tmp_path)
    reader = build(path, read_only=True, backup_on_start=True)
    with pytest.raises(reader.db.OperationalError, match="readonly"):
        reader.settings.set("probe", "x")
    reader.db.close()
    assert _digest(path) == before
    assert _files(tmp_path) == files  # no backup, journal or companion file appeared


def test_a_reader_refuses_a_copy_that_needs_an_upgrade_and_leaves_it_alone(tmp_path):
    path = tmp_path / "old.db"
    writer = build(path)
    writer.db.execute("DELETE FROM schema_migrations WHERE version = "
                      "(SELECT max(version) FROM schema_migrations)")
    writer.db.close()
    before = _digest(path)
    with pytest.raises(ReadOnlyCopyError, match="upgrade"):
        build(path, read_only=True)
    assert _digest(path) == before


def test_a_reader_settles_no_payments(tmp_path):
    path = tmp_path / "copy.db"
    writer = build(path)
    _unmatched_bill(writer)
    writer.db.close()
    before = _digest(path)
    reader = build(path, read_only=True)
    assert reader.planning.match_payments(today()) == 0
    assert TestClient(create_app(reader)).get("/").status_code == 200
    reader.db.close()
    assert _digest(path) == before


def test_every_page_of_a_saved_copy_opens_and_changes_nothing(tmp_path):
    path = tmp_path / "demo.db"
    writer = build(path)
    build_demo(writer)
    _unmatched_bill(writer)
    writer.db.close()
    before = _digest(path)
    reader = build(path, read_only=True)
    client = TestClient(create_app(reader))
    seen, shapes, queue, failed = set(), set(), deque(["/"]), []
    while queue and len(seen) < 120:
        url = queue.popleft()
        shape = re.sub(r"\d+", "N", url)
        if url in seen or shape in shapes:
            continue
        seen.add(url)
        shapes.add(shape)
        response = client.get(url)
        if response.status_code >= 500:
            failed.append(url)
        queue.extend(link for link in (html.unescape(h).split("#")[0]
                                       for h in re.findall(r'href="(/[^"]*)"', response.text))
                     if not link.startswith(("/static", "/exports")))
    reader.db.close()
    assert len(seen) > 50 and not failed
    assert _digest(path) == before


@pytest.fixture
def profile(tmp_path):
    session = ProfileSession(tmp_path / "Documents" / "Lightning")
    session.prepare("Home", PASSWORD, PASSWORD)
    session.confirm(True)
    path = session.paths.db_path
    session.container.settings.set("probe", "home")
    session.close()
    return session, path


def test_a_reader_session_opens_read_only_without_a_backup(profile):
    session, path = profile
    backups = _files(path.parent / "backups") if (path.parent / "backups").exists() else set()
    before = _digest(path)
    session.unlock(str(path), PASSWORD, role=SessionRole.READER)
    assert session.role is SessionRole.READER and session.container.db.read_only
    assert session.container.settings.get("probe") == "home"
    with pytest.raises(session.container.db.OperationalError):
        session.container.settings.set("probe", "reader")
    session.close()
    assert session.role is SessionRole.HOME
    assert _digest(path) == before
    after = _files(path.parent / "backups") if (path.parent / "backups").exists() else set()
    assert after == backups


def test_a_writer_never_activates_with_a_read_only_connection(profile):
    session, path = profile
    session.unlock(str(path), PASSWORD, role=SessionRole.READER)
    container, lock, paths = session.container, session.lock, session.paths
    with pytest.raises(ProfileError, match="wrong kind"):
        session._activate(paths, lock, container, SessionRole.HOME)
    session.close()


def test_the_request_gate_refuses_every_finance_write_for_a_reader(tmp_path):
    from lightning.runtime.app import profile_app
    from lightning.runtime.http import Credentials

    cfg = Credentials("http://127.0.0.1:9876")
    app = profile_app(cfg, tmp_path / "Documents" / "Lightning")
    session = app.session
    session.prepare("Home", PASSWORD, PASSWORD)
    session.confirm(True)
    path = session.paths.db_path
    session.close()
    browser = TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin})
    with browser:
        browser.get("/__launch", params={"code": cfg.launch_code})
        # The encrypted database belongs to the app's thread; the reader page arrives with task 18a.
        browser.portal.call(lambda: session.unlock(str(path), PASSWORD, role=SessionRole.READER))
        before = _digest(path)
        page = browser.get("/accounts/new")
        assert page.status_code == 200
        form_token = re.search(r'name="__session" value="([^"]+)"', page.text).group(1)
        response = browser.post("/accounts/new", data={"__session": form_token, "name": "Wallet",
                                                       "account_type": "CASH", "currency": "EGP",
                                                       "opening_balance": "0", "opening_date": "2026-09-30"})
        assert response.status_code == 403 and READ_ONLY_REFUSAL in response.text
        assert "Wallet" not in browser.get("/accounts").text
        assert _digest(path) == before
        # Locking is a profile action, not a finance write: a reader can always close its copy.
        csrf = re.search(r'name="csrf" value="([^"]+)"', browser.get("/profiles").text).group(1)
        browser.post("/profiles/lock", data={"csrf": csrf})
        assert session.container is None
