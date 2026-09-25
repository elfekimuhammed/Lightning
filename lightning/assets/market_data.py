"""Best-effort Yahoo Finance daily closes for Egyptian listed equities.

Yahoo's chart feed is undocumented; treat it as an optional convenience, never as
an authoritative source. Missing/stale quotes leave the existing valuation intact.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
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
