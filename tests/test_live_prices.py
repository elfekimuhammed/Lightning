"""Each app fetches its own prices (lightning/workflows/live_prices.py): month-end closes by itself the first
time it opens after a month ends, everything on Update prices; never a moving intraday price; a typed price
wins; and nothing is asked when nothing is due."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from lightning.market.model import SourceError
from lightning.ui.web import create_app
from lightning.workflows import live_prices, market_prices
from lightning.workflows.live_prices import due_month_ends, fetch_if_due, fetch_now, final_day


def _stamp(day: str, hour: int = 12) -> int:
    return int(datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc).timestamp())


class Sources:
    """Stands in for the network: TradingView's EGX board, Mubasher's funds and Yahoo's history."""

    def __init__(self, board=None, history=None, funds=None, fund_history="", fail=()):
        self.board, self.history, self.funds, self.fund_history = board or {}, history or {}, funds or [], fund_history
        self.fail, self.asked = set(fail), []

    def _check(self, what):
        self.asked.append(what)
        if what in self.fail:
            raise SourceError(f"{what} is down")

    def post_json(self, url, payload):
        self._check("tradingview")
        return {"data": [{"s": f"EGX:{t}", "d": [t, t, close, "EGP", "stock", "common", "EGX"]}
                         for t, close in self.board.items()]}

    def get_json(self, url, params=None):
        if "mubasher" in url:
            self._check("mubasher")
            return {"rows": self.funds, "numberOfPages": 1}
        self._check("yahoo:" + url.rsplit("/", 1)[-1])
        series = self.history.get(url.rsplit("/", 1)[-1], {})
        return {"chart": {"result": [{"timestamp": [_stamp(d) for d in series],
                                      "indicators": {"quote": [{"close": list(series.values())}]}}]}}

    def get_text(self, url, params=None):
        self._check("mubasher-history")
        return self.fund_history


@pytest.fixture(autouse=True)
def online(monkeypatch, tmp_path):
    monkeypatch.delenv(live_prices.OFFLINE_ENV, raising=False)
    monkeypatch.setattr(market_prices, "BUNDLED", tmp_path / "absent" / "market.zip")


@pytest.fixture
def held(c, setup):
    accounts, _ = setup
    c.transactions.record_transfer("2026-09-01", accounts["cib"].id, accounts["thndr"].id, "40000")
    made = {"cib": c.assets.create_investment("CIB", "STOCK", "COMI"),
            "azs": c.assets.create_investment("AZ Savings", "FUND.FIXED_INCOME", "AZS"),
            "apple": c.assets.create_investment("Apple", "STOCK", "AAPL", mic="XNAS"),
            "nope": c.assets.create_investment("Nope fund", "FUND.EQUITY", "NOPE")}
    c.assets.link_market(made["azs"].id, "EG:FUND:4104")
    for asset in made.values():
        c.investments.buy("2026-09-02", accounts["thndr"].id, asset.id, "10", "50")
    return made


def test_a_close_counts_only_once_it_is_final():
    thursday = datetime(2026, 12, 31, 11, tzinfo=timezone.utc)  # EGX trades Sunday to Thursday, final 13:30 UTC
    assert final_day("egx", thursday) == date(2026, 12, 30)
    assert final_day("egx", thursday.replace(hour=14)) == date(2026, 12, 31)
    assert final_day("egx", datetime(2027, 1, 2, 9, tzinfo=timezone.utc)) == date(2026, 12, 31)  # Saturday
    first = date(2026, 9, 2)
    assert due_month_ends(date(2026, 12, 31), first, thursday)[-1] == "2026-11-30"  # today's month-end not final yet
    assert due_month_ends(date(2026, 12, 31), first, thursday.replace(hour=14))[-1] == "2026-12-31"


def test_three_days_after_a_month_end_the_app_fetches_that_close(c, held):
    sources = Sources(history={"COMI.CA": {"2026-09-29": 70, "2026-10-29": 75, "2026-11-01": 76, "2026-11-02": 77,
                                           "2026-11-03": 79}},  # Nov 3 is still trading at 09:00 UTC
                      fund_history="2026-09-30,30.5\n2026-10-30,31\n2026-11-02,31.2\n")
    morning = datetime(2026, 11, 3, 9, tzinfo=timezone.utc)
    report = fetch_if_due(c, date(2026, 11, 3), sources, morning)
    assert "tradingview" not in sources.asked  # during trading hours the board's price is still moving
    october = c.reporting.value_of(held["cib"].id, D(1), "2026-10-31")
    assert (october.price, october.price_date, october.source) == (D("75"), "2026-10-29", "ONLINE")
    latest = c.reporting.value_of(held["cib"].id, D(1), "2026-11-03")
    assert (latest.price, latest.price_date) == (D("77"), "2026-11-02")  # never today's moving price
    assert c.reporting.value_of(held["azs"].id, D(1), "2026-10-31").price == D("31")
    assert report.priced == ["CIB", "AZ Savings"] and report.other_currency == ["Apple"]
    assert report.unknown == ["Nope fund"] and not report.missing
    assert not c.reevaluations.pending_prices() or all(
        p["asset_id"] in (held["nope"].id, held["apple"].id) for p in c.reevaluations.pending_prices())
    # tried once today: opening again does not ask again, even though Nope fund still has no price
    assert fetch_if_due(c, date(2026, 11, 3), Sources(fail={"tradingview"}), morning) is None


def test_nothing_due_means_no_request(c, held):
    for asset in held.values():
        for day in ("2026-09-30", "2026-10-31", "2026-11-30"):
            c.assets.set_price(asset.id, day, "60")  # every month-end typed
    sources = Sources()
    assert fetch_if_due(c, date(2026, 12, 15), sources, datetime(2026, 12, 15, 9, tzinfo=timezone.utc)) is None
    assert sources.asked == []


def test_offline_and_read_only_never_fetch(c, held, monkeypatch):
    monkeypatch.setenv(live_prices.OFFLINE_ENV, "1")
    sources = Sources()
    assert fetch_if_due(c, date(2026, 11, 3), sources, datetime(2026, 11, 3, 9, tzinfo=timezone.utc)) is None
    assert sources.asked == []


def test_update_prices_takes_the_whole_board_and_a_typed_price_wins(c, held):
    c.assets.set_price(held["cib"].id, "2026-12-31", "99")  # typed today
    sources = Sources(board={"COMI": 101.5, "ETEL": 40},
                      history={"COMI.CA": {"2026-09-30": 70, "2026-10-29": 75, "2026-11-30": 80}},
                      funds=[{"fundId": 4104, "name": "AZ Savings", "price": 32.1, "date": "31 December 2026"}],
                      fund_history="2026-09-30,30.5\n2026-10-30,31\n2026-11-30,31.5\n")
    report = fetch_now(c, date(2026, 12, 31), sources, datetime(2026, 12, 31, 15, tzinfo=timezone.utc))
    assert sources.asked[:2] == ["tradingview", "mubasher"]  # whole boards: they learn nothing of what you hold
    today = c.reporting.value_of(held["cib"].id, D(1), "2026-12-31")
    assert (today.price, today.source) == (D("99"), "MANUAL")
    assert c.reporting.value_of(held["cib"].id, D(1), "2026-11-30").price == D("80")
    assert c.reporting.value_of(held["azs"].id, D(1), "2026-12-31").price == D("32.1")
    assert report.summary().startswith("Fetched ")


def test_a_failing_source_is_named_and_the_month_end_waits_for_you(c, held):
    sources = Sources(fail={"tradingview", "yahoo:COMI.CA", "mubasher", "mubasher-history"})
    report = fetch_now(c, date(2026, 12, 31), sources, datetime(2026, 12, 31, 15, tzinfo=timezone.utc))
    assert report.failed == ["TradingView", "Mubasher", "Yahoo Finance"] and report.saved == 0
    assert ("CIB", "2026-10-31") in report.missing
    assert "Not reachable now: TradingView, Mubasher, Yahoo Finance." in report.summary()
    assert ("CIB", "2026-10-31") in market_prices.missing_prices(c)  # Needs you: Enter prices


def test_the_update_prices_button(c, held, monkeypatch):
    called = []
    monkeypatch.setattr(live_prices, "gather", lambda work: (called.append(work.on), ({}, ["TradingView"]))[1])
    client = TestClient(create_app(c))
    page = client.get("/investments/prices")
    assert "Update prices" in page.text and "Download shared prices" in page.text
    answer = client.post("/investments/prices/online", follow_redirects=False)
    assert answer.status_code == 303 and called
    assert "Not reachable now: TradingView." in client.get(answer.headers["location"]).text
