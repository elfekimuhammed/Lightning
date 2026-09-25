from decimal import Decimal

from lightning.investments.xirr import xirr


def test_xirr_annualizes_one_year_return():
    result = xirr([("2025-01-01", Decimal("-1000")), ("2026-01-01", Decimal("1100"))])
    assert result is not None
    assert abs(result - Decimal("0.10")) < Decimal("0.001")


def test_xirr_returns_none_when_flows_do_not_define_a_rate():
    assert xirr([("2025-01-01", Decimal("-100"))]) is None
    assert xirr([("2025-01-01", Decimal("-100")), ("2025-01-01", Decimal("110"))]) is None
