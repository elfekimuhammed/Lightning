"""Best-effort Yahoo Finance daily closes for Egyptian listed equities.

Yahoo's chart feed is undocumented; treat it as an optional convenience, never as
an authoritative source. Missing/stale quotes leave the existing valuation intact.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lightning.core.dates import today


def _ticker(asset) -> str | None:
    if asset.external_symbol:
        return asset.external_symbol.strip()
    if asset.code.startswith(("STK:", "FND:")):
        return asset.code.split(":", 1)[1] + ".CA"
    return None


def _fetch_close(ticker: str) -> tuple[str, Decimal] | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}?range=5d&interval=1d"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 Lightning personal finance"})
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read(1_000_000))
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice")
        timestamp = meta.get("regularMarketTime")
        if price is None or timestamp is None:
            timestamps = result.get("timestamp") or []
            closes = result["indicators"]["quote"][0].get("close") or []
            samples = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
            if not samples:
                return None
            timestamp, price = samples[-1]
        day = datetime.fromtimestamp(int(timestamp), ZoneInfo("Africa/Cairo")).date().isoformat()
        if datetime.fromisoformat(day).date() > today():
            return None
        value = Decimal(str(price))
        return (day, value) if value.is_finite() and value > 0 else None
    except (KeyError, IndexError, TypeError, ValueError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_price_for_date(asset, day: str) -> tuple[Decimal, str] | None:
    """Fetch the last daily close on or before a requested checkpoint, up to ten days back."""
    ticker = _ticker(asset)
    if not ticker:
        return None
    requested = datetime.fromisoformat(day).date()
    start = requested - timedelta(days=10)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}"
           f"?period1={int(datetime.combine(start, datetime.min.time()).timestamp())}"
           f"&period2={int(datetime.combine(requested + timedelta(days=1), datetime.min.time()).timestamp())}"
           "&interval=1d")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 Lightning personal finance"})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read(1_000_000))
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
        samples = [(datetime.fromtimestamp(int(ts), ZoneInfo("Africa/Cairo")).date(), close)
                   for ts, close in zip(timestamps, closes) if close is not None]
        samples = [(d, v) for d, v in samples if start <= d <= requested]
        if not samples:
            return None
        observed, raw = max(samples, key=lambda sample: sample[0])
        price = Decimal(str(raw))
        return (price, "YAHOO") if price.is_finite() and price > 0 else None
    except (KeyError, IndexError, TypeError, ValueError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def refresh_reevaluation_prices(container, timeout: float = 12) -> int:
    """Prefetch missing historical month-end closes in parallel before monthly posting."""
    from lightning.core.dates import fmt_date, parse_date, today

    first = container.db.scalar(
        "SELECT MIN(le.date) FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
        "JOIN financial_assets a ON a.id=le.asset_id WHERE t.status='POSTED' AND a.is_cash=0")
    if not first:
        return 0
    start = parse_date(first)
    cursor = datetime(start.year, start.month, 1).date()
    end_day = today()
    work = set()
    while cursor <= end_day:
        end = datetime(cursor.year, cursor.month,
                       __import__("calendar").monthrange(cursor.year, cursor.month)[1]).date()
        if end <= end_day:
            day = fmt_date(end)
            positions = container.reporting.q.holdings(day)
            for row in positions:
                if int(row["quantity_e6"] or 0) == 0:
                    continue
                asset = container.assets.get_asset(row["asset_id"])
                if _ticker(asset) and container.reevaluations._price(asset.id, day) is None:
                    work.add((asset.id, day))
        cursor = datetime(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1).date()
    if not work:
        return 0
    pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="historical-price")
    jobs = {pool.submit(fetch_price_for_date, container.assets.get_asset(asset_id), day): (asset_id, day)
            for asset_id, day in work}
    done, _pending = wait(jobs, timeout=timeout)
    saved = 0
    for job in done:
        result = job.result()
        if result:
            asset_id, day = jobs[job]
            price, source = result
            try:
                container.assets.set_price(asset_id, day, price, source=source)
                saved += 1
            except Exception:
                pass
    pool.shutdown(wait=False, cancel_futures=True)
    return saved


def refresh_market_prices(container, timeout: float = 8) -> int:
    """Fetch supported quotes in parallel, then write completed results on the caller's DB thread."""
    assets = [asset for asset in container.assets.investments(active_only=True) if _ticker(asset)]
    if not assets:
        return 0
    pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="quote-fetch")
    jobs = {pool.submit(_fetch_close, _ticker(asset)): asset for asset in assets}
    done, _pending = wait(jobs, timeout=timeout)
    updated = 0
    for job in done:
        quote_data = job.result()
        if quote_data is None:
            continue
        day, price = quote_data
        try:
            container.assets.set_price(jobs[job].id, day, price, source="YAHOO")
            updated += 1
        except Exception:
            continue
    pool.shutdown(wait=False, cancel_futures=True)
    return updated
