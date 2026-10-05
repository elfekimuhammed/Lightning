"""One collector run: ask every source, check every answer, merge into the market folder, report health.

A failing source never stops the others and never removes a price: its market keeps its last good closes,
and health.json counts its failures in a row so the workflow can open an issue (proposal › Keeping it alive).
Published closes are never changed by a run; a different value for a published day is only reported."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from lightning.market.bundle import Close, Instrument, MarketFile, write

from . import checks
from .model import Quote, SourceError, SourceResult
from .sources import cbe, mubasher, tradingview, yahoo

MARKETS = ("egx", "funds", "fx", "us")
TRADING_DAYS = {"egx": {6, 0, 1, 2, 3}, "us": {0, 1, 2, 3, 4}}  # Python weekdays: Sunday is 6
INACTIVE_AFTER_DAYS = 30


def _load(folder: Path) -> tuple[dict[str, Instrument], dict[str, list[Close]], dict]:
    if not (folder / "manifest.json").exists():
        return {}, {}, {}
    market = MarketFile.open(folder)
    series: dict[str, list[Close]] = {}
    for close in market.daily_closes():
        series.setdefault(close.key, []).append(close)
    for closes in series.values():
        closes.sort(key=lambda c: c.date)
    health = json.loads((folder / "health.json").read_text(encoding="utf-8")) if (folder / "health.json").exists() else {}
    return dict(market.instruments()), series, health


def _sources(session, markets, today: str, instruments: dict[str, Instrument]):
    """(name, market, fetch) for today's run, highest priority first within a market."""
    weekday = date.fromisoformat(today).weekday()
    classes = {int(i.sources["mubasher"]): i.category for i in instruments.values() if "mubasher" in i.sources}
    plan = []
    if "egx" in markets and weekday in TRADING_DAYS["egx"]:
        plan.append(("tradingview-egx", "egx", lambda: tradingview.fetch(session, "egx", today)))
    if "funds" in markets:
        plan.append(("mubasher-funds", "funds", lambda: mubasher.fetch(session, classes)))
    if "fx" in markets:
        plan.append(("cbe", "fx", lambda: cbe.fetch(session, today)))
    if "us" in markets and weekday in TRADING_DAYS["us"]:
        plan.append(("tradingview-us", "us", lambda: tradingview.fetch(session, "us", today)))
    return plan


def _merge_instrument(old: Instrument | None, new: Instrument) -> Instrument:
    """Keep the key, ISIN, aliases and a known category; take the source's fresh name and venue."""
    if old is None:
        return new
    return replace(old, name=new.name or old.name, mic=new.mic or old.mic, ticker=new.ticker or old.ticker,
                   currency=new.currency or old.currency, isin=old.isin or new.isin,
                   category=old.category if new.category == "FUND.OTHER" else new.category,
                   sources={**old.sources, **new.sources})


def _health_entry(previous: dict, name: str, ok: bool, created_at: str, **facts) -> dict:
    entry = dict(previous.get(name, {}))
    entry.update(facts, ok=ok, checked_at=created_at)
    if ok:
        entry.update(last_ok=created_at, failures_in_a_row=0, error="")
    else:
        entry["failures_in_a_row"] = int(entry.get("failures_in_a_row", 0)) + 1
    return entry


def _finish(folder, instruments, series, quotes, problems, health, today, created_at):
    """Append accepted quotes, keep published ones, refresh status and dates, write the folder."""
    categories = {k: i.category for k, i in instruments.items()}
    accepted, found = checks.accept(quotes, series, categories, today, history=False)
    return _write(folder, instruments, series, accepted, problems + found, health, today, created_at)


def _write(folder, instruments, series, accepted: list[Quote], problems, health, today, created_at):
    for quote in accepted:
        closes = series.setdefault(quote.key, [])
        same = next((c for c in closes if c.date == quote.date), None)
        if same is None:
            closes.append(Close(quote.date, quote.key, quote.close))
        elif same.close != quote.close:
            problems.append(f"{quote.source}: {quote.key} {quote.date} would change a published {same.close} "
                            f"to {quote.close}; kept (corrections go through corrections.csv)")
    cutoff = (date.fromisoformat(today) - timedelta(days=INACTIVE_AFTER_DAYS)).isoformat()
    for key, instrument in list(instruments.items()):
        closes = sorted(series.get(key, []), key=lambda c: c.date)
        series[key] = closes
        status = instrument.status if instrument.status == "delisted" else (
            "active" if closes and closes[-1].date >= cutoff else "inactive")
        instruments[key] = replace(instrument, status=status, first_date=closes[0].date if closes else "",
                                   last_date=closes[-1].date if closes else "")
    health["_run"] = {"created_at": created_at, "problems": problems[:200], "problem_count": len(problems)}
    write(folder, list(instruments.values()), [c for closes in series.values() for c in closes], created_at, health)
    return health


def collect(folder: Path, session, today: str, created_at: str, markets=MARKETS) -> dict:
    folder = Path(folder)
    instruments, series, health = _load(folder)
    quotes, problems = [], []
    for name, market, fetch in _sources(session, markets, today, instruments):
        try:
            result: SourceResult = fetch()
            minimum = checks.MINIMUM_ROWS.get(name, 1)
            if len(result.quotes) < minimum:
                raise SourceError(f"answered with {len(result.quotes)} prices, fewer than the {minimum} expected")
        except SourceError as exc:
            health[name] = _health_entry(health, name, False, created_at, error=str(exc), rows=0)
            continue
        for instrument in result.instruments:
            instruments[instrument.key] = _merge_instrument(instruments.get(instrument.key), instrument)
        quotes += result.quotes
        health[name] = _health_entry(health, name, True, created_at, rows=len(result.quotes))
    return _finish(folder, instruments, series, quotes, problems, health, today, created_at)


def backfill(folder: Path, session, keys: list[str], today: str, created_at: str) -> dict:
    """Whole history for some instruments: Mubasher's CSV for funds, Yahoo's chart for the rest."""
    folder = Path(folder)
    instruments, series, health = _load(folder)
    accepted, problems = [], []
    for key in keys:
        instrument = instruments.get(key)
        if instrument is None:
            problems.append(f"{key}: not in the instrument list; run collect first")
            continue
        try:
            if "mubasher" in instrument.sources:
                found = mubasher.fetch_history(session, key, instrument.sources["mubasher"])
            else:
                found = yahoo.fetch_history(session, key)
        except SourceError as exc:
            problems.append(f"{key}: {exc}")
            continue
        quotes, issues = checks.accept(found, series, {key: instrument.category}, today, history=True)
        accepted += quotes
        problems += issues
    return _write(folder, instruments, series, accepted, problems, health, today, created_at)
