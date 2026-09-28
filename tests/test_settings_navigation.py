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
