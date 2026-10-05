"""Bundled ISO currency subset and currency-specific amount precision."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from lightning.core.errors import ValidationError


@dataclass(frozen=True)
class Currency:
    code: str
    name: str
    minor_units: int


# The picker must work offline; this catalog is intentionally bundled.
_ROWS = (
    ("EGP", "Egyptian pound", 2),
    ("AED", "UAE dirham", 2),
    ("BHD", "Bahraini dinar", 3),
    ("KWD", "Kuwaiti dinar", 3),
    ("OMR", "Omani rial", 3),
    ("QAR", "Qatari riyal", 2),
    ("SAR", "Saudi riyal", 2),
    ("USD", "US dollar", 2),
    ("EUR", "Euro", 2),
    ("JPY", "Japanese yen", 0),
    ("GBP", "Pound sterling", 2),
    ("CNY", "Chinese yuan", 2),
    ("CHF", "Swiss franc", 2),
    ("AUD", "Australian dollar", 2),
    ("CAD", "Canadian dollar", 2),
    ("HKD", "Hong Kong dollar", 2),
    ("SGD", "Singapore dollar", 2),
)

CURRENCIES = tuple(Currency(*row) for row in _ROWS)
_BY_CODE = {item.code: item for item in CURRENCIES}


def currency(code: str) -> Currency:
    """Look up a supported currency case-insensitively."""
    normalized = (code or "").strip().upper()
    try:
        return _BY_CODE[normalized]
    except KeyError:
        raise ValidationError("Choose a supported currency.", "currency") from None


def minor_units(code: str) -> int:
    return currency(code).minor_units


def round_amount(value: Decimal, code: str) -> Decimal:
    quantum = Decimal(1).scaleb(-minor_units(code))
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def validate_amount_precision(value: Decimal, code: str, field: str = "amount") -> None:
    places = minor_units(code)
    if value != round_amount(value, code):
        unit = "whole units" if places == 0 else f"{places} decimal places"
        raise ValidationError(f"Enter {currency(code).name} to {unit}.", field)
