from lightning.ui.web import create_app
from tests.screens import _ScreenClient, visible_text


def test_financial_health_page_is_directly_reachable_and_shows_missing_values(c, monkeypatch):
    def no_matching(_day):
        raise AssertionError("reading Health must not settle scheduled payments")

    monkeypatch.setattr(c.planning, "match_payments", no_matching)
    browser = _ScreenClient(create_app(c), "http://testserver")
    response = browser.get("/financial-health")
    assert response.status_code == 200
    assert "Financial health" in response.text
    assert "Your cushion" in response.text
    assert "Monthly commitments" in response.text
    assert "Over time" in response.text
    assert "Net worth" in response.text
    assert response.text.count("Show the numbers") >= 8
    assert "Unavailable" in visible_text(response.text)
    assert 'href="/financial-health"' in response.text


def test_health_settings_save_and_restore_a_profile_limit(c):
    browser = _ScreenClient(create_app(c), "http://testserver")
    response = browser.get("/settings?section=financial-health")
    assert response.status_code == 200
    assert "At least 6 months" in response.text
    assert "Emergency fund" in response.text
    saved = browser.post("/settings/financial-health-limit", data={"key": "savings_rate", "value": "25"})
    assert saved.status_code == 200
    assert c.health.limit_values()["savings_rate"] == 25
    reset = browser.post("/settings/financial-health-limit", data={"key": "savings_rate", "action": "reset"})
    assert reset.status_code == 200
    assert c.health.limit_values()["savings_rate"] == 20


def test_emergency_health_limit_is_read_only_and_matches_reserves(c):
    browser = _ScreenClient(create_app(c), "http://testserver")
    settings = browser.get("/settings?section=financial-health").text
    health = browser.get("/financial-health").text
    assert "At least 6 months" in settings
    assert "At least 6 months" in health
    assert 'name="key" value="emergency_fund"' not in settings
    assert 'href="/plan/reserves"' in settings


def test_as_of_date_is_validated_and_rendered(c):
    browser = _ScreenClient(create_app(c), "http://testserver")
    response = browser.get("/financial-health?as_of=2026-09-15")
    assert response.status_code == 200
    assert "2026-09-15" in response.text
    future = browser.get("/financial-health?as_of=2027-01-01")
    assert future.status_code == 200
    assert "Choose today or an earlier as-of date" in visible_text(future.text)
