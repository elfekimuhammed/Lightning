from decimal import Decimal

import pytest

from lightning.core.errors import ValidationError
from lightning.currencies import CURRENCIES, currency, round_amount, validate_amount_precision


def test_catalog_and_minor_units():
    assert len(CURRENCIES) == 17
    assert currency("jpy").minor_units == 0
    assert {currency(code).minor_units for code in ("BHD", "KWD", "OMR")} == {3}
    assert currency("EGP").minor_units == 2


def test_precision_validation():
    validate_amount_precision(Decimal("12.345"), "KWD")
    validate_amount_precision(Decimal("12"), "JPY")
    with pytest.raises(ValidationError):
        validate_amount_precision(Decimal("12.34"), "JPY")
    with pytest.raises(ValidationError):
        validate_amount_precision(Decimal("12.345"), "EGP")


def test_final_rounding_is_currency_specific_and_half_up():
    assert round_amount(Decimal("12.345"), "EGP") == Decimal("12.35")
    assert round_amount(Decimal("12.5"), "JPY") == Decimal("13")


def test_unknown_currency_is_rejected():
    with pytest.raises(ValidationError):
        currency("XXX")
