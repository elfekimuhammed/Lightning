"""Overview figures and drilldowns use the same ledger boundaries as their source views."""

from decimal import Decimal
from fastapi.testclient import TestClient
from starlette.responses import Response

from lightning.ui.web import create_app


def test_overview_cash_reserves_spending_and_investments_reconcile(c, setup, monkeypatch):
    from lightning.ui.routes import dashboard as dashboard_module

    accounts, cats = setup
    c.transactions.record_transfer("2026-12-05", accounts["cib"].id, accounts["thndr"].id, "1000")
    c.transactions.record_outflow("2026-12-10", accounts["cib"].id, "100", cats["EXP.PERSONAL.FOOD"].id)
    reserve = c.reserves.create("Travel", "1000")
    c.reserves.allocate(reserve["id"], "500")
    captured = {}

    def capture(_request, _template, **context):
        captured.update(context)
        return Response("ok")

    monkeypatch.setattr(dashboard_module, "render", capture)
    response = TestClient(create_app(c)).get("/?period=custom&date_from=2026-12-01&date_to=2026-12-31")
    assert response.status_code == 200
    assert captured["net_worth"].total == sum((group["value"] for group in captured["account_contributions"]), Decimal(0))
    pos = captured["pos"]
    assert pos.cash_you_own == sum((row["value"] for row in captured["cash_accounts"]), Decimal(0))
    assert pos.brokerage_cash == Decimal("1000")
    assert pos.reserves == sum((row["effective_allocated"] for row in pos.reserve_rows), Decimal(0))
    assert pos.free_cash == pos.cash_you_own - Decimal("500")
    where = captured["where_it_went"]  # the "Where it went" bars
    assert where["rows"][0]["value"] == Decimal("100") and where["rows"][0]["width"] == 100
    assert "Food" in where["rows"][0]["label"]
    assert "category_id=" in where["rows"][0]["href"]
    assert captured["investment_report"]["brokerage_cash"] == Decimal("1000")
    assert captured["investment_report"]["new_money"] == Decimal("1000")
    assert captured["investment_report"]["period_result"] == Decimal("0")


def test_overview_keeps_every_current_attention_item(c, setup, monkeypatch):
    from lightning.ui.routes import dashboard as dashboard_module

    normal_net_worth = c.reporting.net_worth

    def with_missing_valuations(day):
        result = normal_net_worth(day)
        if str(day) == "2026-12-31":
            result.unvalued = [f"Holding {number}" for number in range(5)]
        return result

    monkeypatch.setattr(c.reporting, "net_worth", with_missing_valuations)
    captured = {}

    def capture(_request, _template, **context):
        captured.update(context)
        return Response("ok")

    monkeypatch.setattr(dashboard_module, "render", capture)
    assert TestClient(create_app(c)).get("/?month=2026-12").status_code == 200
    assert len([item for item in captured["attention"] if item["label"] == "Missing valuation"]) == 5


def test_reserve_historical_breakdown_matches_total_and_rejects_unknown_past(c, setup):
    reserve = c.reserves.create("Travel", "1000")
    c.reserves.allocate(reserve["id"], "500")
    assert c.reserves.breakdown_at("2026-09-30") is None
    rows = c.reserves.breakdown_at("2026-12-31")
    assert rows == [{"id": reserve["id"], "name": "Travel", "kind": "PROJECT", "effective_allocated": Decimal("500")}]
    assert c.reserves.allocation_at("2026-12-31") == sum((row["effective_allocated"] for row in rows), Decimal(0))
