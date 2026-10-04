"""The period picked in a page header is remembered, but "this month" moves on with the calendar
(review 2026-10-04: a month that was current stayed pinned after the month turned)."""


def test_this_month_moves_on_and_a_past_month_stays(c, setup, monkeypatch):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    client = TestClient(create_app(c))
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-10-31")
    client.get("/budget?period=month&month=2026-10")                      # the current month
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-11-01")
    assert client.get("/budget", follow_redirects=False).headers["location"].endswith("month=2026-11")
    client.get("/budget?period=month&month=2026-08")                      # a past month on purpose
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-12-01")
    assert client.get("/budget", follow_redirects=False).headers["location"].endswith("month=2026-08")
