"""Recording money or an asset you already had is not a change in what you own or in net worth
(bug found 2026-10-04: All time showed a change bigger than net worth itself)."""
from decimal import Decimal

D = Decimal


def test_an_opening_balance_in_the_period_is_not_a_change(c, monkeypatch):
    monkeypatch.setenv("LIGHTNING_TODAY", "2026-09-30")
    f = c.account_flows
    f.open_account("CIB Current", "BANK", "2026-09-01", "50,000")
    f.open_account("Family flat", "OTHER_ASSET", "2026-09-15", "400,000")
    change, reason = c.position.change_in_what_you_own("2026-09-01", "2026-09-30")
    assert reason == "" and change == D("0")
    net, _ = c.position.change_in_net_worth("2026-09-01", "2026-09-30")
    assert net == D("0")
    assert c.position.at("2026-09-30").net_worth == D("450000")   # still owned, just not a change
