"""Each copy of Lightning fetches its own prices from the sources (owner, 2026-10-05; docs/proposals/market_data.md
› How the app gets prices).

When: never daily by itself. Month-end closes matter most, because the monthly revaluation is posted from them,
so on opening a profile the app fetches only when a month-end has passed that a held investment has no price
for: open it three days after the month ends and it fetches that month-end's close. It tries at most once a
day by itself, so a source that is down never slows every start. Update prices fetches at any time: every
held investment's latest close and every month-end it lacks.

How: one request for a whole board's latest closes (EGX from TradingView, every Egyptian fund from Mubasher),
so asking reveals nothing about what you hold; a month-end close comes from the instrument's history (Yahoo
for stocks, Mubasher for funds). Only closes that are final are kept: during trading hours today's moving
price is skipped. Prices are saved with source ONLINE, so a price you type for the same day wins. What the
sources cannot give is listed for Needs you, never guessed. The shared price files (the daily collector's
backup) stay one click away on Investment prices, and typing a price always works.

The work is split so the network never holds the database: plan() reads, gather() only fetches, save() writes.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as clock, timedelta, timezone
from decimal import Decimal

from lightning.core.dates import fmt_date
from lightning.market.http import APP_AGENT, Polite
from lightning.market.model import Quote, SourceError
from lightning.market.packs import PACKS
from lightning.market.sources import mubasher, tradingview, yahoo
from lightning.workflows.market_prices import MISSING_SETTING, _month_ends

SOURCE = "ONLINE"
TRIED_SETTING = "prices_online_tried"   # the day the app last fetched by itself
OFFLINE_ENV = "LIGHTNING_PRICES_OFFLINE"  # "1": never fetch (tests, and anyone who wants no network)
NEAR_DAYS = 10                           # a close this close to a month-end stands for it (as revaluation reads it)
CURRENCY = {"egx": "EGP", "eg-funds": "EGP", "us": "USD"}


@dataclass
class Want:
    asset_id: int
    name: str
    key: str            # the instrument: EG:COMI, EG:FUND:4104, US:AAPL
    pack: str
    month_ends: list[str] = field(default_factory=list)  # held month-ends without a price


@dataclass
class Plan:
    on: str
    wants: list[Want] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)          # held, but no source can name it (type its price)
    other_currency: list[str] = field(default_factory=list)   # priced in another currency than the holding

    def month_ends_missing(self) -> int:
        return sum(len(w.month_ends) for w in self.wants)


@dataclass
class Report:
    saved: int = 0
    priced: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)         # sources that did not answer
    missing: list[tuple[str, str]] = field(default_factory=list)  # (investment, month-end) still without a price
    unknown: list[str] = field(default_factory=list)
    other_currency: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"Fetched {self.saved} price{'s' if self.saved != 1 else ''} for {len(self.priced)} "
                 f"investment{'s' if len(self.priced) != 1 else ''}." if self.saved else "No new prices fetched."]
        if self.failed:
            parts.append(f"Not reachable now: {', '.join(self.failed)}.")
        if self.missing:
            shown = ", ".join(f"{name} {day}" for name, day in self.missing[:3])
            parts.append(f"{len(self.missing)} month-end price{'s' if len(self.missing) != 1 else ''} still missing: "
                         f"{shown}{' and more' if len(self.missing) > 3 else ''}.")
        if self.unknown:
            parts.append(f"No online source for {', '.join(self.unknown[:3])}{' and more' if len(self.unknown) > 3 else ''}"
                         "; type their prices.")
        if self.other_currency:
            parts.append(f"Priced in another currency, left for you: {', '.join(self.other_currency[:3])}.")
        return " ".join(parts)


def enabled() -> bool:
    return os.environ.get(OFFLINE_ENV, "").strip() not in ("1", "true", "yes")


def instrument_key(asset) -> tuple[str, str] | None:
    """Which instrument and pack an investment is, when a source can name it: its saved market key, else a
    stock's country and ticker (EGX by default). Funds need their saved key (EG:FUND:<Mubasher id>)."""
    key = (asset.market_key or "").strip()
    if not key and asset.code.startswith("STK:"):
        key = f"{asset.country or 'EG'}:{asset.ticker}"
    if key.startswith("EG:FUND:"):
        return key, "eg-funds"
    if key.startswith("EG:"):
        return key, "egx"
    if key.startswith("US:"):
        return key, "us"
    return None


def final_day(pack: str, now: datetime) -> date:
    """The latest trading day whose close is final at `now` (UTC): today once the market's prices are final,
    else the trading day before. Holidays are not known here; a holiday's close is the day before's."""
    spec = PACKS[pack]
    hour, minute = (int(part) for part in spec.final_utc.split(":"))
    now = now.astimezone(timezone.utc)
    day = now.date() if now.time() >= clock(hour, minute) else now.date() - timedelta(days=1)
    while day.weekday() not in spec.days:
        day -= timedelta(days=1)
    return day


def due_month_ends(on: date, first: date, now: datetime) -> list[str]:
    """Month-ends from `first` whose closes are final by `now`: every one before `on`, and `on` itself once
    the day's prices are final (the evening of the last day of a month)."""
    days = _month_ends(first, on)
    hour, minute = (int(part) for part in PACKS["egx"].final_utc.split(":"))
    if days and days[-1] == fmt_date(on) and now.astimezone(timezone.utc).time() < clock(hour, minute):
        days.pop()
    return days


def plan(c, on: date, now: datetime | None = None) -> Plan:
    """What to fetch: every held investment a source can name, with the month-ends it lacks a price for."""
    now = now or datetime.now(timezone.utc)
    result = Plan(fmt_date(on))
    first = c.reporting.first_activity_date()
    held: dict[int, list[str]] = {}
    if first:
        for day in due_month_ends(on, date.fromisoformat(first[:10]), now):
            for holding in c.reporting.holdings(day)[0]:
                if holding.quantity and holding.asset_id and not c.reevaluations.has_price(holding.asset_id, day):
                    held.setdefault(holding.asset_id, []).append(day)
    for holding in c.reporting.holdings(fmt_date(on))[0]:
        if holding.quantity and holding.asset_id:
            held.setdefault(holding.asset_id, [])
    for asset_id, month_ends in sorted(held.items()):
        asset = c.assets.get_asset(asset_id)
        if asset.is_cash or asset.code.startswith(("OTH:ITEM-", "REF:", "GLD:")):
            continue
        found = instrument_key(asset)
        if found is None:
            if month_ends:
                result.unknown.append(asset.name)
            continue
        key, pack = found
        if pack != "eg-funds" and CURRENCY[pack] != asset.currency:
            result.other_currency.append(asset.name)
            continue
        result.wants.append(Want(asset.id, asset.name, key, pack, month_ends))
    return result


def _range(oldest: date, on: date) -> str:
    """The shortest Yahoo history range reaching back to `oldest` (with room for a month-end on a weekend)."""
    days = (on - oldest).days + NEAR_DAYS
    for limit, name in ((28, "1mo"), (88, "3mo"), (178, "6mo"), (360, "1y"), (725, "2y"), (1820, "5y"), (3640, "10y")):
        if days <= limit:
            return name
    return "max"


def gather(work: Plan, session=None, now: datetime | None = None, budget: float = 20.0) -> tuple[dict, list[str]]:
    """Fetch, touching no database: the closes found per asset id, and the sources that failed. Latest closes
    come from whole boards; history only for investments missing a month-end. Stops when `budget` runs out."""
    now = now or datetime.now(timezone.utc)
    session = session or Polite(min_interval=0.3, retries=2, timeout=10.0, user_agent=APP_AGENT)
    deadline = time.monotonic() + budget
    found: dict[int, dict[str, Decimal]] = {}
    failed: list[str] = []
    on = date.fromisoformat(work.on)

    def last_final(want: Want) -> date:  # a fund's NAV is published once, already final, on its own date
        return on if want.pack == "eg-funds" else min(final_day(want.pack, now), on)

    def keep(want: Want, quotes) -> None:
        for quote in quotes:
            if date.fromisoformat(quote.date) <= last_final(want):
                found.setdefault(want.asset_id, {})[quote.date] = quote.close

    by_pack: dict[str, list[Want]] = {}
    for want in work.wants:
        by_pack.setdefault(want.pack, []).append(want)
    if by_pack.get("egx"):  # the whole EGX board, one request: only final closes (not during trading)
        final, utc_today = final_day("egx", now), now.astimezone(timezone.utc).date()
        if final == utc_today or utc_today.weekday() not in PACKS["egx"].days:
            try:
                board = tradingview.fetch(session, "egx", fmt_date(final))
                closes = {q.key: q for q in board.quotes}
                for want in by_pack["egx"]:
                    if want.key in closes:
                        keep(want, [closes[want.key]])
            except SourceError:
                failed.append("TradingView")
    if by_pack.get("eg-funds"):  # every Egyptian fund's latest NAV, one request
        try:
            navs = {q.key: q for q in mubasher.fetch(session).quotes}
            for want in by_pack["eg-funds"]:
                if want.key in navs:
                    keep(want, [navs[want.key]])
        except SourceError:
            failed.append("Mubasher")
    for want in work.wants:  # history: month-ends still missing, and a latest close the board did not give
        latest_known = bool(found.get(want.asset_id))
        if (not want.month_ends and latest_known) or time.monotonic() > deadline:
            continue
        oldest = date.fromisoformat(min(want.month_ends)) if want.month_ends else on
        try:
            if want.pack == "eg-funds":
                quotes = mubasher.fetch_history(session, want.key, want.key.rsplit(":", 1)[1])
            else:
                quotes = yahoo.fetch_history(session, want.key, _range(oldest, on))
        except SourceError:
            name = "Mubasher" if want.pack == "eg-funds" else "Yahoo Finance"
            if name not in failed:
                failed.append(name)
            continue
        wanted = set(want.month_ends)
        picked: list[Quote] = []
        ordered = sorted((q for q in quotes if date.fromisoformat(q.date) <= last_final(want)),
                         key=lambda q: q.date)
        for day in sorted(wanted):  # the last close on or before each month-end, within NEAR_DAYS
            before = [q for q in ordered if q.date <= day]
            if before and (date.fromisoformat(day) - date.fromisoformat(before[-1].date)).days <= NEAR_DAYS:
                picked.append(before[-1])
        if ordered and not latest_known:
            picked.append(ordered[-1])
        keep(want, picked)
    return found, failed


def save(c, work: Plan, found: dict, failed: list[str]) -> Report:
    """Write what was fetched (a typed price on the same day still wins), post the month-end revaluations
    it allows, and remember what is still missing for Needs you."""
    report = Report(failed=list(failed), unknown=list(work.unknown), other_currency=list(work.other_currency))
    on = date.fromisoformat(work.on)
    for want in work.wants:
        closes = found.get(want.asset_id, {})
        for day, close in sorted(closes.items()):
            if (on - date.fromisoformat(day)).days > NEAR_DAYS and not any(
                    0 <= (date.fromisoformat(m) - date.fromisoformat(day)).days <= NEAR_DAYS for m in want.month_ends):
                continue  # an old close that stands for no month-end we need
            c.assets.set_price(want.asset_id, day, Decimal(close).quantize(Decimal("0.000001")), source=SOURCE)
            report.saved += 1
        if closes:
            report.priced.append(want.name)
    c.reevaluations.process_due()
    missing_ids = []
    for want in work.wants:
        for day in want.month_ends:
            if not c.reevaluations.has_price(want.asset_id, day):
                report.missing.append((want.name, day))
                missing_ids.append([want.asset_id, day])
    try:
        earlier = json.loads(c.settings.get(MISSING_SETTING) or "[]")
    except ValueError:
        earlier = []
    planned = {w.asset_id for w in work.wants}
    kept = [pair for pair in earlier if isinstance(pair, list) and len(pair) == 2 and pair[0] not in planned]
    c.settings.set(MISSING_SETTING, json.dumps((kept + missing_ids)[:200]))
    return report


def fetch_now(c, on: date, session=None, now: datetime | None = None) -> Report:
    """Update prices: every held investment's latest close and every month-end it lacks, now."""
    work = plan(c, on, now)
    found, failed = gather(work, session, now) if work.wants else ({}, [])
    return save(c, work, found, failed)


def fetch_if_due(c, on: date, session=None, now: datetime | None = None) -> Report | None:
    """On opening a profile: fetch only when a held investment lacks a passed month-end's price, at most once
    a day. None when nothing was due (no request is made), offline, or the profile is a read-only copy."""
    if c.db.read_only or not enabled() or c.settings.get(TRIED_SETTING) == fmt_date(on):
        return None
    work = plan(c, on, now)
    if not work.month_ends_missing():
        return None
    c.settings.set(TRIED_SETTING, fmt_date(on))
    found, failed = gather(work, session, now, budget=12.0)
    return save(c, work, found, failed)
