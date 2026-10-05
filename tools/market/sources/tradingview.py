"""TradingView's screener: every EGX stock (and the largest US stocks and ETFs) with its latest close,
in one request per market. The request shape is the one open-source trackers use daily."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from lightning.market.bundle import Instrument

from ..model import Quote, SourceError, SourceResult

SCAN = "https://scanner.tradingview.com/{screener}/scan"
COLUMNS = ["name", "description", "close", "currency", "type", "subtype", "exchange"]
EGX_QUERY = {"columns": COLUMNS, "range": [0, 2000], "sort": {"sortBy": "name", "sortOrder": "asc"}}
US_STOCKS = 600   # about the S&P 500 and Nasdaq-100 by size; widened later on request
US_ETFS = 100
_US = [{"left": "exchange", "operation": "in_range", "right": ["NASDAQ", "NYSE", "AMEX"]}]
US_STOCK_QUERY = {"columns": COLUMNS, "filter": _US + [
    {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
    {"left": "subtype", "operation": "nequal", "right": "preferred"}],
    "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, US_STOCKS]}
US_ETF_QUERY = {"columns": COLUMNS, "filter": _US + [
    {"left": "type", "operation": "equal", "right": "fund"},
    {"left": "subtype", "operation": "equal", "right": "etf"}],
    "sort": {"sortBy": "aum", "sortOrder": "desc"}, "range": [0, US_ETFS]}
# TradingView names venues its own way; ISO 10383 MICs are what the file stores. It reports NYSE Arca
# listings (most ETFs) as AMEX, so an ETF there is ARCX and a share there is NYSE American (XASE).
_MIC = {"EGX": "XCAI", "NASDAQ": "XNAS", "NYSE": "XNYS"}


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


def parse(data: dict, market: str, day: str) -> SourceResult:
    """One screener answer as instruments and closes dated `day` (the trading day the run is for)."""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise SourceError("TradingView's screener answered without its data list")
    result = SourceResult(f"tradingview-{market}")
    for row in data["data"]:
        try:
            symbol, values = row["s"], dict(zip(COLUMNS, row["d"]))
        except (KeyError, TypeError):
            continue
        exchange, _, ticker = str(symbol).partition(":")
        close = _decimal(values.get("close"))
        if not ticker or close is None:
            continue
        if market == "egx":
            if exchange != "EGX" or values.get("type") not in ("stock", "fund", "dr"):
                continue
            key, country, mic = f"EG:{ticker}", "EG", "XCAI"
        else:
            if exchange not in ("NASDAQ", "NYSE", "AMEX"):
                continue
            key, country = f"US:{ticker}", "US"
            mic = _MIC.get(exchange) or ("ARCX" if values.get("type") == "fund" else "XASE")
        is_fund = values.get("type") == "fund"
        result.instruments.append(Instrument(
            key=key, name=" ".join(str(values.get("description") or ticker).split()), ticker=ticker, mic=mic,
            country=country, currency=str(values.get("currency") or ("EGP" if market == "egx" else "USD")).upper(),
            category="FUND.OTHER" if is_fund else "STOCK", unit="unit" if is_fund else "share",
            sources={"tradingview": symbol}))
        result.quotes.append(Quote(key, day, close, result.source))
    return result


def fetch(session, market: str, day: str) -> SourceResult:
    url = SCAN.format(screener="egypt" if market == "egx" else "america")
    if market == "egx":
        return parse(session.post_json(url, EGX_QUERY), "egx", day)
    stocks = parse(session.post_json(url, US_STOCK_QUERY), "us", day)
    etfs = parse(session.post_json(url, US_ETF_QUERY), "us", day)
    stocks.instruments += etfs.instruments
    stocks.quotes += etfs.quotes
    return stocks
