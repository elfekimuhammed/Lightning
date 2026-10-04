"""Sold everything in the period: nothing is held, but the Investments tab still shows the period's
gain (bug found 2026-10-04: the tab showed only "No holdings yet")."""


def test_a_period_where_everything_was_sold_still_shows_its_result(c, setup, monkeypatch):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-12-31")
    accounts, _ = setup
    thndr = accounts["thndr"]
    c.transactions.record_transfer("2026-12-01", accounts["cib"].id, thndr.id, "10000")
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    entry = {"price_basis": "total", "fees": "", "fees_included": "1", "instrument_key": "catalog:COMI", "units": "100"}
    client.post(f"/accounts/{thndr.id}/investment-entry", data={**entry, "date": "2026-12-02", "total": "7000",
                                                               "trade_action": "buy"})
    client.post(f"/accounts/{thndr.id}/investment-entry", data={**entry, "date": "2026-12-20", "total": "8000",
                                                               "trade_action": "sell"})
    page = client.get("/investments?period=month&month=2026-12").text
    assert "No holdings yet" not in page
    assert "+1,000" in page                      # the period's gain from the sale
    assert "No owned holdings to show." in page  # and the table says nothing is held now
