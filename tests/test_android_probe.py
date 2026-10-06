"""Task 04c: the Android probe's Python side, run on Linux before it goes to the phone.

The probe serves the shared runtime (`Host`, `profile_app`) on a copy of the dummy profile; the phone's WebView then
unlocks it through the real form. Here an HTTP client takes the WebView's place."""
import http.cookiejar
import importlib
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "roundtrip"


@pytest.fixture
def probe(tmp_path, monkeypatch):
    package = tmp_path / "packages" / "roundtrip_fixture"
    shutil.copytree(FIXTURE, package)
    (package / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path / "packages"))
    monkeypatch.syspath_prepend(str(ROOT / "android" / "app" / "src" / "main" / "python"))
    sys.modules.pop("probe", None)
    module = importlib.import_module("probe")
    yield module
    module.stop_quietly()


def test_pages_render_and_alignment_is_reported(probe):
    assert re.match(r"OK  04c pages render: 9 pages and \d+ app files", probe._check("04c pages render", probe._pages))
    line = probe._check("04c 16 KB pages", probe._sixteen_kb)
    assert "app libraries loaded" in line  # Linux wheels may be 4 KB-aligned; the phone's must not be


def test_serve_unlock_overview_and_shutdown(probe, tmp_path):
    from lightning.runtime.roundtrip import PASSWORD

    launch = probe.serve(tmp_path / "files")
    assert probe._served[1].startswith("OK  04c server guards: refused no session cookie")
    origin = launch.split("/__launch")[0]
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    assert "Dummy" in browser.open(launch).read().decode()  # the profile chooser lists the dummy profile
    unlock = browser.open(origin + "/profiles/unlock?db=" + urllib.parse.quote(str(probe._paths.db_path))).read().decode()
    selected = re.search(r'name="db" value="([^"]+)"', unlock).group(1)
    csrf = re.search(r'name="csrf" value="([^"]+)"', unlock).group(1)
    form = urllib.parse.urlencode({"csrf": csrf, "db": selected, "password": PASSWORD}).encode()
    request = urllib.request.Request(origin + "/profiles/unlock", data=form, headers={"Origin": origin})
    overview = browser.open(request)
    assert urllib.parse.urlparse(overview.geturl()).path == "/"
    assert "CIB Payroll" in overview.read().decode()
    report = probe.stop()
    assert "OK  04c shutdown: stopped in" in report and "never unlocked" not in report
    assert probe._host is None


def test_phone_app_entry_serves_the_profiles_and_reports_when_it_must_listen(tmp_path, monkeypatch):
    """`lightning_android` is what MainActivity and SyncService call."""
    monkeypatch.syspath_prepend(str(ROOT / "android" / "app" / "src" / "main" / "python"))
    sys.modules.pop("lightning_android", None)
    phone = importlib.import_module("lightning_android")
    try:
        launch = phone.start(str(tmp_path / "files"))
        assert "/__launch?code=" in launch
        assert phone.start(str(tmp_path / "files")).endswith("/")  # reopening needs no new launch link
        assert phone.background_note() == ""  # nothing paired or lent: the phone may sleep
    finally:
        if phone._host is not None:
            phone._host.stop()
