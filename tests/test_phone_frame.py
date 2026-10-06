"""Milestone 2, step 1: on the phone app every page renders in the phone frame (guideline Part C).

What a browser must measure (nothing scrolls sideways at 360 and 320, C12) is in `tools/phone_check.py`; it
needs Playwright and runs locally. This test needs no browser: the frame, its five sections and no desktop
leftovers."""
import re

import pytest
from fastapi.testclient import TestClient

from lightning.runtime.app import profile_app
from lightning.runtime.devices import Devices
from lightning.runtime.http import Credentials

from test_profile_app import create, token

PAGES = ("/", "/birdview/expenses", "/financial-health", "/budget", "/plan", "/plan/recurring", "/plan/loans",
         "/plan/reserves", "/investments", "/accounts", "/transactions", "/settings", "/checks")


@pytest.fixture(scope="module")
def phone(tmp_path_factory):
    folder = tmp_path_factory.mktemp("phone")
    cfg = Credentials("http://127.0.0.1:9861")
    app = profile_app(cfg, folder / "docs", devices=Devices(folder / "app", port=0), phone=True)
    with TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin}) as browser:
        browser.get("/__launch", params={"code": cfg.launch_code})
        create(browser)
        page = browser.get("/")
        browser.post("/demo", data={"__session": token(page.text, "__session")})
        yield browser


@pytest.mark.parametrize("path", PAGES)
def test_every_page_renders_in_the_phone_frame(phone, path):
    page = phone.get(path)
    assert page.status_code == 200
    html = page.text
    assert html.count('class="phone-appbar"') == 1 and html.count('class="phone-tabbar"') == 1
    assert 'class="shell"' not in html and 'class="side"' not in html  # no desktop sidebar
    assert "Ctrl K" not in html  # C12: no keyboard hints on a phone
    assert html.count('class="section-bar"') <= 1
    assert "viewport-fit=cover" in html and "/static/phone.css" in html
    names = re.findall(r'class="phone-tab-name">([^<]+)<', html)
    assert names == ["Overview", "Budget", "Cash", "Investments", "Accounts"]


def test_the_chosen_section_and_the_period_words(phone):
    html = phone.get("/budget").text
    assert re.search(r'class="phone-tab is-chosen" href="/budget" aria-current="page"', html)
    overview = phone.get("/").text
    assert ">Monthly<" not in overview and ">All time<" not in overview  # C04.2


def test_the_pc_keeps_its_own_frame(tmp_path):
    cfg = Credentials("http://127.0.0.1:9862")
    app = profile_app(cfg, tmp_path / "docs", devices=Devices(tmp_path / "app", port=0))
    with TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin}) as browser:
        browser.get("/__launch", params={"code": cfg.launch_code})
        create(browser)
        html = browser.get("/").text
    assert 'class="shell"' in html and "phone-tabbar" not in html and "phone.css" not in html


def test_overview_uses_the_phone_forms(phone):
    html = phone.get("/").text
    assert 'class="phone-kpis"' in html and html.count('class="phone-kpi ') <= 4  # C06.1: four tiles, 2 × 2
    assert "stat-tile-spark" not in html  # no sparkline in a phone tile
    assert "chart-sankey" not in html and 'class="phone-flow"' in html  # C07.3.3
    assert "chart-cfall" not in html and "scheme-flow" in html  # C07.3.2: the waterfall as rows
    assert 'class="mcal"' not in html and 'class="phone-months"' in html  # C07.3.4
    assert re.search(r'class="phone-lead">[\d,]+ <small>EGP</small>', html)  # whole EGP on the big figure
