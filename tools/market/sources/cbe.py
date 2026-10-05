"""The Central Bank of Egypt's official exchange rates: a table of currencies with buy and sell rates.

We publish the mid (buy and sell averaged) as the price of one unit in pounds, keyed by its ISO 4217
pair (USD/EGP). The page layout is read loosely: any table row whose first cell names a currency and
whose next cells hold two numbers. The format is to confirm on the first collector run."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from lightning.market.bundle import Instrument

from ..model import Quote, SourceError, SourceResult

URL = "https://www.cbe.org.eg/en/economic-research/statistics/cbe-exchange-rates"
# Names on the page (English and Arabic) as ISO 4217 codes. "per 100" names are scaled to one unit.
NAMES = {
    "us dollar": "USD", "دولار أمريكي": "USD", "euro": "EUR", "يورو": "EUR",
    "pound sterling": "GBP", "british pound": "GBP", "جنيه إسترليني": "GBP", "swiss franc": "CHF", "فرنك سويسري": "CHF",
    "japanese yen": "JPY", "ين ياباني": "JPY", "saudi riyal": "SAR", "ريال سعودي": "SAR",
    "kuwaiti dinar": "KWD", "دينار كويتي": "KWD", "uae dirham": "AED", "emirati dirham": "AED", "درهم إماراتي": "AED",
    "chinese yuan": "CNY", "يوان صيني": "CNY", "canadian dollar": "CAD", "دولار كندي": "CAD",
    "australian dollar": "AUD", "دولار أسترالي": "AUD", "danish krone": "DKK", "كرونة دنماركية": "DKK",
    "norwegian krone": "NOK", "كرونة نرويجية": "NOK", "swedish krona": "SEK", "كرونة سويدية": "SEK",
    "bahraini dinar": "BHD", "دينار بحريني": "BHD", "omani riyal": "OMR", "ريال عماني": "OMR",
    "qatari riyal": "QAR", "ريال قطري": "QAR", "jordanian dinar": "JOD", "دينار أردني": "JOD",
}
CURRENCY_NAMES = {"USD": "US dollar", "EUR": "Euro", "GBP": "Pound sterling", "CHF": "Swiss franc", "JPY": "Japanese yen",
                  "SAR": "Saudi riyal", "KWD": "Kuwaiti dinar", "AED": "UAE dirham", "CNY": "Chinese yuan",
                  "CAD": "Canadian dollar", "AUD": "Australian dollar", "DKK": "Danish krone", "NOK": "Norwegian krone",
                  "SEK": "Swedish krona", "BHD": "Bahraini dinar", "OMR": "Omani riyal", "QAR": "Qatari riyal",
                  "JOD": "Jordanian dinar"}
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.text: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def _code(name: str) -> tuple[str, Decimal] | None:
    text = name.casefold().replace("100", "").strip()
    for words, code in NAMES.items():
        if words in text:
            return code, (Decimal(100) if "100" in name else Decimal(1))
    return None


def parse(html: str, today: str) -> SourceResult:
    """The rates table as currency instruments and mid rates dated by the page (else `today`)."""
    page = _Rows()
    page.feed(html)
    found = _DATE.search(" ".join(page.text))
    if found and found.group(3):
        day = date(int(found.group(3)), int(found.group(2)), int(found.group(1))).isoformat()
    elif found:
        day = date(int(found.group(4)), int(found.group(5)), int(found.group(6))).isoformat()
    else:
        day = today
    if day > today:
        day = today
    result = SourceResult("cbe")
    for row in page.rows:
        if not row:
            continue
        named = _code(row[0])
        numbers = []
        for cell in row[1:]:
            try:
                numbers.append(Decimal(cell.replace(",", "")))
            except InvalidOperation:
                continue
        if not named or len(numbers) < 2 or any(n <= 0 for n in numbers[:2]):
            continue
        code, per = named
        if any(i.key == f"{code}/EGP" for i in result.instruments):
            continue
        mid = (numbers[0] + numbers[1]) / 2 / per
        result.instruments.append(Instrument(key=f"{code}/EGP", name=CURRENCY_NAMES.get(code, code), category="CURRENCY",
                                             currency="EGP", unit=code, sources={"cbe": code}))
        result.quotes.append(Quote(f"{code}/EGP", day, mid.quantize(Decimal("0.000001")), result.source))
    if not any(i.key == "USD/EGP" for i in result.instruments):
        raise SourceError("CBE's rates page had no US dollar row; its layout may have changed")
    return result


def _describe(html: str) -> str:
    """What the page held, for the run's log when it could not be read: its size, table rows, and the text
    around the first mention of the dollar (no full page, which may be large)."""
    page = _Rows()
    page.feed(html)
    lowered = html.casefold()
    at = next((lowered.find(word) for word in ("us dollar", "usd", "دولار") if lowered.find(word) >= 0), -1)
    near = " ".join(html[max(0, at - 300):at + 500].split()) if at >= 0 else "no dollar mentioned"
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return (f"{len(html)} characters, {len(page.rows)} table rows, title {(title.group(1).strip() if title else '')!r}; "
            f"near the dollar: {near[:800]}")


def fetch(session, today: str) -> SourceResult:
    html = session.get_text(URL)
    try:
        return parse(html, today)
    except SourceError:
        import sys
        print(f"cbe: {_describe(html)}", file=sys.stderr)  # the run's log shows what the page holds now
        raise
