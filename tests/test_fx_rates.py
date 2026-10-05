from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError
from lightning.fx import FrankfurterAdapter, FxRateRepository, RateFetchError


def _enable(c, *codes):
    c.settings.set_enabled_currencies(("EGP", *codes))


def test_rate_storage_keeps_precision_and_provenance(c):
    _enable(c, "USD")
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("49.123456789123"), source="FRANKFURTER", source_id="provider-a")
    found = rates.get("USD", "EGP", "2026-10-03")
    assert found.rate == Decimal("49.123456789123")
    assert found.source == "FRANKFURTER"
    assert found.source_id == "provider-a"
    assert not found.stale


def test_manual_rate_overrides_same_day_provider_rate(c):
    _enable(c, "USD")
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("50"), source="FRANKFURTER")
    rates.save(effective_date="2026-10-01", base="USD", quote="EGP",
               rate=Decimal("49.5"), source="MANUAL", original_quote="User entry")
    assert rates.get("USD", "EGP", "2026-10-01").rate == Decimal("49.5")


def test_inverse_and_same_provider_same_date_cross_rates(c):
    _enable(c, "USD", "EUR")
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
    _enable(c, "USD")
    rates = FxRateRepository(c.db)
    rates.save(effective_date="2026-09-01", base="USD", quote="EGP",
               rate=Decimal("50"), source="MANUAL")
    assert rates.get("USD", "EGP", "2026-09-09").stale


def test_disabled_currency_cannot_be_saved_as_a_new_observation(c):
    with pytest.raises(ValidationError, match="Enable both currencies"):
        FxRateRepository(c.db).save(effective_date="2026-10-01", base="USD", quote="EGP",
                                    rate=Decimal("50"), source="MANUAL")


def test_disabled_currency_never_triggers_a_network_request(c):
    class Opener:
        called = False

        def open(self, request, timeout):
            self.called = True
            raise AssertionError("must not make a request")

    opener = Opener()
    with pytest.raises(ValidationError, match="Enable both currencies"):
        FrankfurterAdapter(FxRateRepository(c.db), opener=opener).fetch("USD", "EGP", "2026-10-01")
    assert not opener.called


def test_frankfurter_uses_fixed_host_and_validates_pair(c):
    _enable(c, "USD")
    class Response:
        headers = {"Content-Length": "72"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, limit):
            return b'{"date":"2026-10-01","base":"USD","quote":"EGP","rate":49.123456789123}'

    class Opener:
        request = None

        def open(self, request, timeout):
            self.request = request
            assert timeout == 8.0
            return Response()

    opener = Opener()
    adapter = FrankfurterAdapter(FxRateRepository(c.db), opener=opener)
    quote = adapter.fetch("usd", "egp", "2026-10-01")
    assert quote.rate == Decimal("49.123456789123")
    assert quote.source_id == "ECB"
    assert opener.request.full_url.startswith("https://api.frankfurter.dev/v2/providers/ecb/rate/usd/egp?")
    assert "2026-10-01" in opener.request.full_url


def test_frankfurter_rejects_mismatched_response(c):
    _enable(c, "USD")
    class Response:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, limit):
            return b'{"date":"2026-10-01","base":"EUR","quote":"EGP","rate":50}'

    class Opener:
        def open(self, request, timeout):
            return Response()

    with pytest.raises(RateFetchError, match="mismatched"):
        FrankfurterAdapter(FxRateRepository(c.db), opener=Opener()).fetch("USD", "EGP", "2026-10-01")
