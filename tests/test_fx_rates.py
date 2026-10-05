from decimal import Decimal

from lightning.fx import FxRateRepository


def test_rate_storage_keeps_precision_and_provenance(c):
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("49.123456789123"), source="FRANKFURTER", source_id="provider-a")
    found = rates.get("USD", "EGP", "2026-10-03")
    assert found.rate == Decimal("49.123456789123")
    assert found.source == "FRANKFURTER"
    assert found.source_id == "provider-a"
    assert not found.stale


def test_manual_rate_overrides_same_day_provider_rate(c):
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("50"), source="FRANKFURTER")
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("49.5"), source="MANUAL", original_quote="User entry")
    assert rates.get("USD", "EGP", "2026-10-01").rate == Decimal("49.5")


def test_inverse_and_same_provider_same_date_cross_rates(c):
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-10-01", base="USD", quote="EUR",
               rate=Decimal("0.8"), source="FRANKFURTER")
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("50"), source="FRANKFURTER")
    assert rates.get("EUR", "USD", "2026-10-01").rate == Decimal("1.25")
    cross = rates.get("EUR", "EGP", "2026-10-01")
    assert cross.rate == Decimal("62.5")
    assert cross.source == "FRANKFURTER"


def test_stale_observation_is_flagged(c):
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-09-01", base="USD", quote="EGP",
               rate=Decimal("50"), source="MANUAL")
    assert rates.get("USD", "EGP", "2026-09-09").stale
