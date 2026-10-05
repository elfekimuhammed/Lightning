import re

from fastapi.testclient import TestClient

from lightning.ui.web import create_app


def test_settings_sections_share_one_subsection_navigation(c):
    client = TestClient(create_app(c))
    pages = {
        "/settings": "General",
        "/settings?section=budget": "Budget",
        "/settings?section=valuations": "Valuations",
        "/counterparties": "Counterparties",
        "/categories": "Categories",
        "/checks": "Data checks",
    }
    for url, active in pages.items():
        response = client.get(url)
        assert response.status_code == 200
        assert 'aria-label="Settings sections"' in response.text
        assert f'aria-current="page">{active}</a>' in response.text


def test_currency_settings_enable_currency_and_change_lcy_before_entries(c):
    client = TestClient(create_app(c))
    page = client.get("/settings")
    assert page.status_code == 200
    assert 'id="currency-settings"' in page.text
    assert 'list="currency-catalog"' in page.text
    token = re.search(r'name="__session" value="([^"]*)"', page.text).group(1)
    enabled = client.post("/settings/currencies", data={"__session": token, "action": "enable", "currency": "USD"})
    assert enabled.status_code in (302, 303)
    assert c.settings.enabled_currencies == ("EGP", "USD")
    changed = client.post("/settings/currencies", data={"__session": token, "action": "base", "currency": "USD"})
    assert changed.status_code in (302, 303)
    assert c.base_currency == "USD"
