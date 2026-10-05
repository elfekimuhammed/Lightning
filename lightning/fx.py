"""Precise FX observation storage and dated, provenance-aware lookup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from lightning.core.dates import now_iso, parse_date
from lightning.currencies import CURRENCIES, currency
from lightning.database.connection import Database

_SCALE = Decimal(10**12)
_MAX_AGE_DAYS = 7


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

    def save(self, *, effective_date: str, base: str, quote: str, rate: Decimal,
             source: str, source_id: str = "", original_quote: str = "",
             fetched_at: str | None = None, bid: Decimal | None = None,
             ask: Decimal | None = None) -> None:
        base, quote = currency(base).code, currency(quote).code
        day = parse_date(effective_date).isoformat()
        if isinstance(rate, float):
            raise TypeError("FX rates must be Decimal values, not floats.")
        value = Decimal(rate)
        if base == quote or not value.is_finite() or value <= 0:
            raise ValueError("An FX observation needs distinct currencies and a positive finite rate.")
        if source not in {"CBE", "FRANKFURTER", "WISE", "MANUAL"}:
            raise ValueError("FX source is not in the adapter allowlist.")
        if any(value is not None and (isinstance(value, float) or not value.is_finite() or value <= 0)
               for value in (bid, ask)):
            raise ValueError("FX bid and ask must be positive Decimal values.")
        if bid is not None and ask is not None and ask < bid:
            raise ValueError("FX bid and ask must be positive and ordered.")
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
