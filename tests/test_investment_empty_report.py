from lightning.core.money import ZERO
from lightning.investments.report import build_investment_report
from fastapi.testclient import TestClient

from lightning.ui.web import create_app


class NoInvestmentAccounts:
    def list(self, active_only=False):
        return []


def test_empty_investment_report_has_reconciliation_and_template_fields():
    report = build_investment_report(
        None, NoInvestmentAccounts(), None, None, "2026-09-01", "2026-09-30"
    )
    assert report["net_money"] == ZERO
    assert report["unresolved_dividends"] == 0
    assert report["value"] == ZERO
    assert report["investment_cash"] == ZERO


def test_investment_page_renders_without_investment_accounts(c):
    response = TestClient(create_app(c)).get("/investments")
    assert response.status_code == 200
    assert "Add a brokerage account" in response.text
