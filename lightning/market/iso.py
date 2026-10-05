"""ISO names used for market data: ISO 6166 (ISIN), ISO 10383 (MIC), ISO 4217 (currency), ISO 3166 (country).

Only checks of form, and the venues Lightning shows; no registry is copied here.
"""
from __future__ import annotations

import re

# ISO 10383 market identifier codes Lightning shows, with the name people use and the country.
VENUES: dict[str, tuple[str, str]] = {
    "XCAI": ("EGX", "EG"),            # The Egyptian Exchange
    "XNAS": ("Nasdaq", "US"),
    "XNYS": ("NYSE", "US"),
    "ARCX": ("NYSE Arca", "US"),
    "XASE": ("NYSE American", "US"),
    "BATS": ("Cboe BZX", "US"),
    "XSAU": ("Saudi Exchange", "SA"),
    "XDFM": ("Dubai Financial Market", "AE"),
    "XADS": ("Abu Dhabi Securities Exchange", "AE"),
    "DSMQ": ("Qatar Stock Exchange", "QA"),
    "XKUW": ("Boursa Kuwait", "KW"),
    "XBAH": ("Bahrain Bourse", "BH"),
    "XLON": ("London Stock Exchange", "GB"),
    "XETR": ("Xetra", "DE"),
    "XPAR": ("Euronext Paris", "FR"),
    "XAMS": ("Euronext Amsterdam", "NL"),
    "XBRU": ("Euronext Brussels", "BE"),
    "XLIS": ("Euronext Lisbon", "PT"),
    "XMAD": ("Madrid Stock Exchange", "ES"),
    "XMIL": ("Borsa Italiana", "IT"),
    "XSWX": ("SIX Swiss Exchange", "CH"),
}


def venue_name(mic: str | None) -> str:
    """'XCAI' -> 'EGX'; an unknown MIC is shown as itself, an empty one as ''."""
    code = (mic or "").strip().upper()
    return VENUES.get(code, (code, ""))[0]


def is_mic(text: str | None) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{4}", text or ""))


def is_currency(text: str | None) -> bool:
    """An ISO 4217 alphabetic code: three capital letters (EGP, USD, XAU)."""
    return bool(re.fullmatch(r"[A-Z]{3}", text or ""))


def is_country(text: str | None) -> bool:
    """An ISO 3166-1 alpha-2 code: two capital letters (EG, US)."""
    return bool(re.fullmatch(r"[A-Z]{2}", text or ""))


def is_isin(text: str | None) -> bool:
    """ISO 6166: two letters of country, nine letters or digits, and a check digit (Luhn over the letters
    turned into numbers, A=10 ... Z=35). 'US0378331005' (Apple) is valid; one wrong character is not."""
    isin = (text or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        return False
    digits = "".join(str(int(ch, 36)) for ch in isin)
    total = 0
    for position, digit in enumerate(reversed(digits)):
        value = int(digit) * (2 if position % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0
