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


# ------------------------------------------------------------------ 06b: borrowed paths, role changes
PROFILE_ID = "5b0c3c52-7d0e-4c4a-9f3e-2b8d9c1a0e11"


def test_a_borrowed_profile_lives_in_local_app_data(tmp_path):
    from lightning.runtime.paths import app_data_root, borrowed_profile

    windows = app_data_root(platform="win32", environ={"LOCALAPPDATA": r"C:\Users\m\AppData\Local"})
    assert str(windows).replace("\\", "/").endswith("AppData/Local/Lightning")
    linux = app_data_root(platform="linux", environ={}, home=tmp_path)
    assert linux == tmp_path / ".local" / "share" / "Lightning"
    paths = borrowed_profile(PROFILE_ID, platform="linux", environ={}, home=tmp_path)
    assert paths.data_dir == linux / "borrowed" / PROFILE_ID
    paths.prepare()
    assert paths.prefetch_dir.is_dir() and paths.recovery_dir.is_dir() and paths.sealed_dir.is_dir()
    assert not paths.working_path.exists()  # nothing but folders until a lend writes a file
    with pytest.raises(ValueError, match="UUID"):
        borrowed_profile("../escape", root=tmp_path)
    with pytest.raises(ValueError, match="LOCALAPPDATA"):
        app_data_root(platform="win32", environ={})


@pytest.mark.parametrize("folder", ["OneDrive/Lightning", "Dropbox/Apps/Lightning", "iCloud Drive/Lightning"])
def test_a_borrowed_profile_refuses_synced_folders(tmp_path, folder):
    from lightning.runtime.paths import borrowed_profile

    with pytest.raises(ValueError, match="synced"):
        borrowed_profile(PROFILE_ID, root=tmp_path / folder)


def test_a_borrowed_profile_refuses_documents_links_and_hard_links(tmp_path):
    from lightning.runtime.paths import BorrowedPaths, borrowed_profile, check_borrowed_location

    documents = tmp_path / "Documents" / "Lightning"
    with pytest.raises(ValueError, match="Documents"):
        check_borrowed_location(documents / "borrowed" / PROFILE_ID, documents_root=documents)
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "linked").symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="link"):
        borrowed_profile(PROFILE_ID, root=tmp_path / "linked")
    paths = borrowed_profile(PROFILE_ID, root=tmp_path / "app")
    paths.prepare()
    paths.working_path.write_bytes(b"x")
    (tmp_path / "copy.db").hardlink_to(paths.working_path)
    with pytest.raises(ValueError, match="hard link"):
        paths.validate()
    (tmp_path / "copy.db").unlink()
    paths.working_path.unlink()
    paths.working_path.symlink_to(tmp_path / "elsewhere.db")
    with pytest.raises(ValueError, match="links or junctions"):
        BorrowedPaths(PROFILE_ID, paths.data_dir).validate()


def test_a_role_change_waits_for_the_request_in_flight(tmp_path):
    """The gate closes and drains before the new role is published (plan section 5, rule 1)."""
    import asyncio
    from types import SimpleNamespace

    from lightning.runtime.app import SessionGate

    async def scenario():
        session = ProfileSession(tmp_path / "Documents" / "Lightning")
        session.prepare("Home", PASSWORD, PASSWORD)
        session.confirm(True)
        gate = SessionGate(SimpleNamespace(state=SimpleNamespace()), session)
        async with gate.mutex:  # a request is in flight
            change = asyncio.create_task(gate.change_role(SessionRole.READER))
            await asyncio.sleep(0.01)
            assert not change.done() and session.role is SessionRole.HOME
            session.container.settings.set("probe", "last write before lending")
        await change
        assert session.role is SessionRole.READER and session.container.db.read_only
        assert session.container.settings.get("probe") == "last write before lending"
        assert gate.app.state.container is session.container
        await gate.change_role(SessionRole.HOME)
        assert not session.container.db.read_only
        session.container.settings.set("probe", "home again")
        session.close()

    asyncio.run(scenario())


def test_no_form_from_before_a_role_change_can_save(tmp_path):
    from lightning.runtime.app import profile_app
    from lightning.runtime.http import Credentials

    cfg = Credentials("http://127.0.0.1:9876")
    app = profile_app(cfg, tmp_path / "Documents" / "Lightning")
    browser = TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin})
    wallet = {"name": "Wallet", "account_type": "CASH", "currency": "EGP", "opening_balance": "0",
              "opening_date": "2026-09-30"}

    def form_token():
        return re.search(r'name="__session" value="([^"]+)"', browser.get("/accounts/new").text).group(1)

    with browser:
        browser.get("/__launch", params={"code": cfg.launch_code})
        browser.portal.call(lambda: (app.session.prepare("Home", PASSWORD, PASSWORD), app.session.confirm(True)))
        home_form = form_token()
        browser.portal.call(app.gate.change_role, SessionRole.READER)
        assert browser.post("/accounts/new", data={"__session": home_form, **wallet}).status_code == 403
        reader_form = form_token()
        browser.portal.call(app.gate.change_role, SessionRole.HOME)
        stale = browser.post("/accounts/new", data={"__session": reader_form, **wallet})
        assert stale.status_code == 403 and "expired" in stale.text
        assert browser.post("/accounts/new", data={"__session": form_token(), **wallet}).status_code == 200
        assert "Wallet" in browser.get("/accounts").text
