"""Precise FX observation storage and dated, provenance-aware lookup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from json import loads
from decimal import InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lightning.core.dates import now_iso, parse_date
from lightning.core.errors import ValidationError
from lightning.core.money import decimal_places
from lightning.currencies import CURRENCIES, currency
from lightning.database.connection import Database
from lightning.database.settings import SettingsStore

_SCALE = Decimal(10**12)
_MAX_AGE_DAYS = 7
_FRANKFURTER_HOST = "api.frankfurter.dev"
_MAX_RESPONSE_BYTES = 256 * 1024


class RateFetchError(RuntimeError):
    """A configured rate source failed or returned an invalid response."""


class _AllowlistedRedirects(HTTPRedirectHandler):
    def __init__(self, host: str):
        self.host = host
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname != self.host or parsed.port not in (None, 443):
            raise RateFetchError("The rate source tried to redirect to an unapproved host.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class RateQuote:
    base: str
    quote: str
    effective_date: str
    rate: Decimal
    source: str
    fetched_at: str
    source_id: str = ""
    original_quote: str = ""
    bid: Decimal | None = None
    ask: Decimal | None = None
    stale: bool = False


def _scaled(value: Decimal | None) -> int | None:
    return None if value is None else int((value * _SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _decimal(value: int | None) -> Decimal | None:
    return None if value is None else Decimal(value) / _SCALE


class FxRateRepository:
    def __init__(self, db: Database):
        self.db = db
        self.settings = SettingsStore(db)

    def ensure_enabled_pair(self, base: str, quote: str) -> tuple[str, str]:
        base, quote = currency(base).code, currency(quote).code
        enabled = set(self.settings.enabled_currencies)
        if base not in enabled or quote not in enabled:
            raise ValidationError("Enable both currencies before saving or fetching their rate.", "currency")
        return base, quote

    def save(self, *, effective_date: str, base: str, quote: str, rate: Decimal,
             source: str, source_id: str = "", original_quote: str = "",
             fetched_at: str | None = None, bid: Decimal | None = None,
             ask: Decimal | None = None) -> None:
        base, quote = self.ensure_enabled_pair(base, quote)
        day = parse_date(effective_date).isoformat()
        if isinstance(rate, float):
            raise TypeError("FX rates must be Decimal values, not floats.")
        value = Decimal(rate)
        if base == quote or not value.is_finite() or value <= 0:
            raise ValidationError("Choose two different currencies and enter a positive rate.", "rate")
        if decimal_places(value) > 12:
            raise ValidationError("Enter an exchange rate to at most 12 decimal places.", "rate")
        if source not in {"CBE", "FRANKFURTER", "WISE", "MANUAL"}:
            raise ValidationError("The exchange-rate source is not supported.", "source")
        if any(value is not None and (isinstance(value, float) or not value.is_finite() or value <= 0)
               for value in (bid, ask)):
            raise ValueError("FX bid and ask must be positive Decimal values.")
        if bid is not None and ask is not None and ask < bid:
            raise ValidationError("Enter positive bid and ask values, with ask no lower than bid.", "rate")
        self.db.execute(
            "INSERT INTO fx_rate_observations(effective_date,base,quote,rate_e12,fetched_at,source,source_id,"
            "original_quote,bid_e12,ask_e12) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(effective_date,base,quote,source,source_id) DO UPDATE SET "
            "rate_e12=excluded.rate_e12,fetched_at=excluded.fetched_at,original_quote=excluded.original_quote,"
            "bid_e12=excluded.bid_e12,ask_e12=excluded.ask_e12",
            (day, base, quote, _scaled(value), fetched_at or now_iso(), source, source_id,
             original_quote, _scaled(bid), _scaled(ask)),
        )

    def get(self, base: str, quote: str, as_of: str) -> RateQuote | None:
        base, quote = currency(base).code, currency(quote).code
        day = parse_date(as_of)
        if base == quote:
            return RateQuote(base, quote, day.isoformat(), Decimal(1), "IDENTITY", "")
        direct = self._latest(base, quote, day.isoformat())
        if direct:
            return self._quote(direct, day)
        inverse = self._latest(quote, base, day.isoformat())
        if inverse:
            quote_row = self._quote(inverse, day)
            return RateQuote(base, quote, quote_row.effective_date, Decimal(1) / quote_row.rate,
                             quote_row.source, quote_row.fetched_at, quote_row.source_id,
                             quote_row.original_quote, stale=quote_row.stale)
        return self._cross(base, quote, day)

    def _latest(self, base: str, quote: str, as_of: str):
        return self.db.one(
            "SELECT * FROM fx_rate_observations WHERE base=? AND quote=? AND effective_date<=? "
            "ORDER BY effective_date DESC, CASE source WHEN 'MANUAL' THEN 0 ELSE 1 END, fetched_at DESC LIMIT 1",
            (base, quote, as_of),
        )

    def _quote(self, row, day: date) -> RateQuote:
        age = (day - parse_date(row["effective_date"])).days
        return RateQuote(row["base"], row["quote"], row["effective_date"], _decimal(row["rate_e12"]),
                         row["source"], row["fetched_at"], row["source_id"], row["original_quote"],
                         _decimal(row["bid_e12"]), _decimal(row["ask_e12"]), age > _MAX_AGE_DAYS)

    def _cross(self, base: str, quote: str, day: date) -> RateQuote | None:
        candidates = []
        for pivot in (item.code for item in CURRENCIES if item.code not in (base, quote)):
            rows = self.db.all(
                "SELECT * FROM fx_rate_observations WHERE effective_date<=? AND "
                "((base=? AND quote=?) OR (base=? AND quote=?) OR "
                "(base=? AND quote=?) OR (base=? AND quote=?))",
                (day.isoformat(), base, pivot, pivot, base, pivot, quote, quote, pivot),
            )
            grouped: dict[tuple[str, str, str], dict[tuple[str, str], object]] = {}
            for row in rows:
                group = grouped.setdefault((row["effective_date"], row["source"], row["source_id"]), {})
                key = (row["base"], row["quote"])
                existing = group.get(key)
                if existing is None or (row["source"] == "MANUAL" and existing["source"] != "MANUAL"):
                    group[key] = row
            for (effective, source, source_id), pair_rows in grouped.items():
                def pair_rate(left: str, right: str):
                    row = pair_rows.get((left, right))
                    if row:
                        return _decimal(row["rate_e12"])
                    inverse = pair_rows.get((right, left))
                    return Decimal(1) / _decimal(inverse["rate_e12"]) if inverse else None

                first, second = pair_rate(base, pivot), pair_rate(pivot, quote)
                if first is not None and second is not None:
                    fetched = max((r["fetched_at"] for r in pair_rows.values()), default="")
                    candidates.append((effective, source, source_id, first * second, fetched))
        if not candidates:
            return None
        effective, source, source_id, value, fetched = max(
            candidates, key=lambda row: (row[0], row[1] == "MANUAL", row[4]))
        age = (day - parse_date(effective)).days
        return RateQuote(base, quote, effective, value, source, fetched, source_id,
                         stale=age > _MAX_AGE_DAYS)


class FrankfurterAdapter:
    """Fixed-host, ECB-provider historical adapter; it sends only pair and date."""

    def __init__(self, repository: FxRateRepository, opener=None, timeout: float = 8.0):
        self.repository = repository
        self.opener = opener or build_opener(_AllowlistedRedirects(_FRANKFURTER_HOST))
        self.timeout = timeout

    def fetch(self, base: str, quote: str, effective_date: str) -> RateQuote | None:
        base, quote = self.repository.ensure_enabled_pair(base, quote)
        day = parse_date(effective_date).isoformat()
        if base == quote:
            raise ValueError("An external rate is unnecessary for the same currency.")
        path = f"/v2/providers/ecb/rate/{base.lower()}/{quote.lower()}"
        query = urlencode({"date": day})
        url = f"https://{_FRANKFURTER_HOST}{path}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "Lightning/0.5"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > _MAX_RESPONSE_BYTES:
                    raise RateFetchError("The rate source response exceeded the size limit.")
                payload = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise RateFetchError(f"Frankfurter returned HTTP {exc.code}.") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise RateFetchError("Could not reach the configured Frankfurter rate source.") from exc
        if len(payload) > _MAX_RESPONSE_BYTES:
            raise RateFetchError("The rate source response exceeded the size limit.")
        try:
            document = loads(payload, parse_float=Decimal, parse_int=Decimal)
            observed_date = parse_date(document["date"]).isoformat()
            returned_base, returned_quote = currency(document["base"]).code, currency(document["quote"]).code
            raw_rate = document["rate"]
            rate = raw_rate if isinstance(raw_rate, Decimal) else Decimal(str(raw_rate))
        except (ValueError, TypeError, KeyError, ValidationError, InvalidOperation):
            raise RateFetchError("Frankfurter returned an invalid rate response.") from None
        if (returned_base, returned_quote) != (base, quote) or rate <= 0 or not rate.is_finite():
            raise RateFetchError("Frankfurter returned a mismatched or invalid currency pair.")
        self.repository.save(effective_date=observed_date, base=base, quote=quote, rate=rate,
                             source="FRANKFURTER", source_id="ECB", original_quote=str(raw_rate))
        return self.repository.get(base, quote, day)
