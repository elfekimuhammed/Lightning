"""Exact money and quantity handling.

Rules:
- Every amount, quantity, price and rate is a ``Decimal`` — never a float.
- In SQLite they are stored as integers scaled by 1,000,000 (columns end in ``_e6``),
  so SQL ``SUM()`` stays exact. ``to_e6`` / ``from_e6`` are the only conversions.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .errors import ValidationError

SCALE_PLACES = 6
SCALE = 10**SCALE_PLACES
ZERO = Decimal("0")
ONE = Decimal("1")


_ARABIC_DIGITS = {**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)},
                  0x066B: ".", 0x066C: ","}


def ascii_digits(text: str) -> str:
    """Arabic-Indic digits (٠١٢, ۰۱۲) and the Arabic decimal and thousands marks as plain ASCII."""
    return text.translate(_ARABIC_DIGITS)


def to_decimal(value: object, field: str = "amount") -> Decimal:
    """Parse user or code input into a Decimal.

    Accepts ``Decimal``, ``int`` and strings such as ``"1,250.50"`` or ``" 450 "``.
    Floats are rejected on purpose: they cannot represent money exactly.
    """
    if isinstance(value, bool):
        raise ValidationError("Enter a number.", field)
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        cleaned = ascii_digits(value).strip().replace("−", "-")
        if cleaned == "":
            raise ValidationError("Enter an amount.", field)
        if re.fullmatch(r"[+-]?\d{1,3},\d{1,2}", cleaned):
            raise ValidationError("Use a dot for decimals, for example 12.5.", field)
        if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", cleaned):
            raise ValidationError(f"'{value}' is not a valid number. Use commas only as thousands separators.", field)
        cleaned = cleaned.replace(",", "")
        try:
            result = Decimal(cleaned)
        except InvalidOperation:
            raise ValidationError(f"'{value}' is not a valid number.", field) from None
    elif isinstance(value, float):
        raise ValidationError("Internal error: floats are not allowed for money.", field)
    else:
        raise ValidationError("Enter a number.", field)
    if not result.is_finite():
        raise ValidationError("Enter a finite number.", field)
    if abs(result) >= Decimal("1000000000000"):
        raise ValidationError("That amount is too large.", field)
    return result


def decimal_places(value: Decimal) -> int:
    exponent = value.normalize().as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def check_places(value: Decimal, places: int, field: str = "amount") -> Decimal:
    """Reject values with more decimal places than allowed (e.g. 12.345 EGP)."""
    if decimal_places(value) > places:
        if places == 0:
            raise ValidationError("Use whole numbers only.", field)
        raise ValidationError(f"Use at most {places} decimal places.", field)
    return value


def quantize(value: Decimal, places: int = 2) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def to_e6(value: Decimal) -> int:
    """Decimal -> integer micro-units for storage. Refuses to lose precision."""
    if decimal_places(value) > SCALE_PLACES:
        raise ValidationError(f"At most {SCALE_PLACES} decimal places can be stored.")
    return int(value.scaleb(SCALE_PLACES))


def from_e6(value: int | None) -> Decimal:
    """Integer micro-units from storage -> Decimal."""
    if value is None:
        return ZERO
    # normalize() drops trailing zeros; adding 0.00 keeps at least two decimals (450 -> 450.00)
    return Decimal(int(value)).scaleb(-SCALE_PLACES).normalize() + Decimal("0.00")


def fmt(value: Decimal | None, places: int = 2, signed: bool = False) -> str:
    """Human format: ``1,234.50`` / ``-1,234.50`` (``+`` prefix when signed)."""
    if value is None:
        return "—"
    q = quantize(value, places)
    text = f"{abs(q):,.{places}f}"
    if q < 0:
        return f"-{text}"
    if signed and q > 0:
        return f"+{text}"
    return text
