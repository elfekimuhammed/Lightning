from __future__ import annotations

from datetime import date
from decimal import Decimal


def _save(c, accounts, **overrides):
    values = {
        "account_id": accounts["cd"].id,
        "start_date": "2026-09-15",
        "maturity_date": "2026-11-15",
        "principal": "5000",
        "annual_rate": "18",
        "interest_method": "SIMPLE",
        "payout_frequency": "MONTHLY",
        "destination_account_id": accounts["cib"].id,
    }
    values.update(overrides)
    return c.deposits.save(**values)


def test_simple_cd_interest_and_maturity_are_cash_but_not_income(c, setup):
    accounts, _ = setup
    as_of = date(2026, 10, 1)
    baseline = c.forecaster.forecast(as_of)
    _save(c, accounts)

    forecast = c.forecaster.forecast(as_of)
    events = c.deposits.future_events(as_of, date(2026, 12, 31))
    expected = {
        month.month: sum((event.amount for event in events if event.date[:7] == month.month), Decimal(0))
        for month in forecast.months
    }
    assert expected == {
        "2026-10": Decimal("73.972603"),
        "2026-11": Decimal("5076.438356"),
        "2026-12": Decimal("0"),
    }
    assert [month.deposit_cash for month in forecast.months] == list(expected.values())
    assert [month.income for month in forecast.months] == [month.income for month in baseline.months]
    assert forecast.free_cash == baseline.free_cash
    for index, month in enumerate(forecast.months):
        total_proceeds = sum((row.deposit_cash for row in forecast.months[:index + 1]), Decimal(0))
        assert month.closing == baseline.months[index].closing + total_proceeds
    assert forecast.safe_to_spend == baseline.safe_to_spend


def test_compound_cd_returns_one_maturity_cash_event(c, setup):
    accounts, _ = setup
    _save(c, accounts, maturity_date="2026-11-01", interest_method="COMPOUND",
          payout_frequency="AT_MATURITY", compounding_frequency="MONTHLY")

    forecast = c.forecaster.forecast(date(2026, 10, 1))
    event = c.deposits.future_events(date(2026, 10, 1), date(2026, 12, 31))[0]
    assert event.kind == "MATURITY"
    assert forecast.months[0].deposit_cash == 0
    assert forecast.months[1].deposit_cash == event.amount
    assert forecast.months[1].income == 0


def test_recorded_future_maturity_transfer_replaces_projection(c, setup):
    accounts, _ = setup
    as_of = date(2026, 10, 1)
    free_cash_before = c.position.at(as_of).free_cash
    _save(c, accounts, start_date="2026-09-01", maturity_date="2026-11-01", annual_rate="0",
          payout_frequency="AT_MATURITY")
    c.deposits.move_legacy_cash(accounts["cd"].id, "2026-11-01", "5000", accounts["cib"].id)

    forecast = c.forecaster.forecast(as_of)
    assert forecast.months[1].deposit_cash == Decimal("5000")
    assert forecast.months[1].income == 0
    assert forecast.free_cash == free_cash_before


def test_cd_withdrawn_before_as_of_has_no_projected_cash(c, setup):
    accounts, _ = setup
    _save(c, accounts)
    c.deposits.move_legacy_cash(accounts["cd"].id, "2026-10-01", "5000", accounts["cib"].id)

    forecast = c.forecaster.forecast(date(2026, 10, 2))
    assert all(month.deposit_cash == 0 for month in forecast.months)


def test_maturity_beyond_forecast_horizon_is_excluded(c, setup):
    accounts, _ = setup
    _save(c, accounts, start_date="2026-09-01", maturity_date="2027-01-01", annual_rate="18",
          interest_method="SIMPLE", payout_frequency="AT_MATURITY")

    forecast = c.forecaster.forecast(date(2026, 10, 1))
    assert [month.month for month in forecast.months] == ["2026-10", "2026-11", "2026-12"]
    assert all(month.deposit_cash == 0 for month in forecast.months)
