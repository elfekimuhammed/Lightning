"""Navigation and entry paths used throughout the finance workspace."""

import re

from fastapi.testclient import TestClient

from lightning.ui.web import create_app


def test_analysis_navigation_selects_only_the_current_page(c):
    client = TestClient(create_app(c))
    for path, current in (
        ("/birdview", "/birdview"),
        ("/birdview/expenses", "/birdview/expenses"),
        ("/settings", "/settings"),
        ("/counterparties", "/settings"),
    ):
        page = client.get(path)
        assert page.status_code == 200
        active = re.findall(r'<a href="([^"]+)" class="active" aria-current="page">', page.text)
        assert active == [current]


def test_account_uses_guided_transaction_entry_and_keeps_advanced_row_secondary(c):
    c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "1000")
    client = TestClient(create_app(c))
    page = client.get("/accounts/1")
    assert page.status_code == 200
    assert 'data-popup-open href="/accounts/1/transaction/new"' in page.text
    assert 'id="quick-add" hidden' in page.text
    assert 'data-toggle-quick-add' in page.text
    assert 'href="/accounts/1/import"' in page.text


def test_custom_period_apply_keeps_custom_mode(c):
    c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "1000")
    client = TestClient(create_app(c))
    page = client.get("/birdview?period=custom&date_from=2026-09-01&date_to=2026-09-20")
    assert page.status_code == 200
    assert 'name="period" value="custom" class="btn small">Apply' in page.text
    assert 'name="date_from" value="2026-09-01"' in page.text
    assert 'name="date_to" value="2026-09-20"' in page.text


def test_mobile_account_navigation_uses_a_collapsible_account_section(c):
    c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "1000")
    page = TestClient(create_app(c)).get("/")
    assert page.status_code == 200
    assert '<details class="side-accounts" id="sidebar-accounts">' in page.text
    assert '<summary class="mobile-accounts-summary">' in page.text
    assert 'href="/accounts/1"' in page.text
