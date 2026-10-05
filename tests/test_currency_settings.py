import pytest

from lightning.core.errors import ValidationError


def test_profile_currency_defaults_to_egp_and_can_change_before_entries(c):
    assert c.settings.enabled_currencies == ("EGP",)
    c.settings.set_base_currency("usd")
    assert c.settings.base_currency == "USD"
    assert c.settings.enabled_currencies == ("USD",)


def test_profile_currency_is_fixed_after_first_financial_entry(c):
    c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "0")
    with pytest.raises(ValidationError, match="fixed after"):
        c.settings.set_base_currency("USD")


def test_used_currency_cannot_be_disabled(c):
    c.settings.set_enabled_currencies(["EGP", "USD"])
    c.db.execute("UPDATE accounts SET currency='USD' WHERE id=(SELECT MIN(id) FROM accounts)")
    with pytest.raises(ValidationError, match="used by an account"):
        c.settings.set_enabled_currencies(["EGP"])


def test_profile_currency_cannot_be_disabled(c):
    c.settings.set_enabled_currencies(["USD"])
    assert "EGP" in c.settings.enabled_currencies
