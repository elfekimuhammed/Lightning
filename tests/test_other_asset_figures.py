"""An asset you only know the worth of (an "Other" account, such as a share of a flat) is a holding,
never brokerage cash, and every screen shows the same Holdings value (bug found 2026-10-03)."""
from decimal import Decimal

from lightning.investments.report import build_investment_report

D = Decimal


def test_an_other_account_is_a_holding_not_brokerage_cash(c, setup, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    accounts, _ = setup
    flat = c.account_flows.open_account("Family flat", "OTHER_ASSET", "2026-09-15", "400,000")
    report = build_investment_report(c.db, c.accounts, c.assets, c.reporting, "2026-09-01", "2026-09-30")
    assert report["investment_cash"] == D("0")            # THNDR holds no cash; the flat is not cash
    assert any(row["asset"] == "Family flat" and row["value"] == D("400000") for row in report["holdings"])
    position = c.position.at("2026-09-30")
    assert position.brokerage_cash == D("0") and position.holdings_value == D("400000")
    assert report["value"] == position.holdings_value      # the same figure on the Investments tab and the Overview
    assert flat.id


def test_the_overview_investments_row_reads_the_position(c, setup, monkeypatch):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    c.account_flows.open_account("Family flat", "OTHER_ASSET", "2026-09-15", "400,000")
    page = TestClient(create_app(c)).get("/?period=month&month=2026-09").text
    row = page[page.index('aria-label="Investments in this period"'):page.index("See investments")]
    assert "400,000" in row and "Brokerage cash" not in row
