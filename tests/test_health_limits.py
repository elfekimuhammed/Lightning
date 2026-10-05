from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError
from lightning.planning.health import HealthService, LIMIT_DEFAULTS, compare_to_limit


@pytest.mark.parametrize(("value", "limit", "direction", "expected"), [
    (Decimal("20"), Decimal("20"), "minimum", "within your limit"),
    (Decimal("19.9"), Decimal("20"), "minimum", "outside your limit"),
    (Decimal("50"), Decimal("50"), "maximum", "within your limit"),
    (Decimal("50.1"), Decimal("50"), "maximum", "outside your limit"),
    (None, Decimal("20"), "minimum", None),
    (Decimal("20"), None, "minimum", None),
])
def test_comparison_is_inclusive_and_missing_inputs_have_no_status(value, limit, direction, expected):
    assert compare_to_limit(value, limit, direction) == expected


def test_limits_are_profile_settings_with_defaults_and_individual_restore(c):
    service = c.health
    assert service.limit_values() == LIMIT_DEFAULTS
    service.set_limit("savings_rate", "23.5")
    service.set_limit("debt_to_cash", "", no_limit=True)
    assert service.limit_values()["savings_rate"] == Decimal("23.5")
    assert service.limit_values()["debt_to_cash"] is None
    service.restore_limit("savings_rate")
    assert service.limit_values()["savings_rate"] == Decimal("20")
    assert service.limit_values()["debt_to_cash"] is None


@pytest.mark.parametrize(("key", "raw"), [("savings_rate", "-1"), ("savings_rate", "1.23"), ("unknown", "5")])
def test_limits_reject_negative_excess_precision_and_unknown_keys(c, key, raw):
    with pytest.raises(ValidationError):
        c.health.set_limit(key, raw)


def test_health_overview_uses_six_months_ending_before_last_completed_month(c):
    overview = c.health.overview()
    assert overview["savings_month"] == "2026-11"
    assert [month.month for month in overview["trends"]] == [
        "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    assert all(month.savings_rate is None for month in overview["trends"])
    assert all(month.net_worth is None for month in overview["trends"])


def test_health_reads_do_not_trigger_planned_payment_matching(c, monkeypatch):
    calls = []
    original = c.position.at

    def tracked(day, *, match_payments=True):
        calls.append(match_payments)
        return original(day, match_payments=match_payments)

    monkeypatch.setattr(c.position, "at", tracked)
    c.health.overview()
    assert calls and not any(calls)
