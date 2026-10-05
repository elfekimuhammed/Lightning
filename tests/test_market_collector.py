"""The price collector (tools/market): each adapter on a recorded sample of its source's answer, the checks,
and whole runs against a fake network, including a source that fails."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from lightning.market.bundle import Close, MarketFile
from tools.market import checks
from tools.market.collect import backfill, collect
from tools.market.model import Quote, SourceError
from tools.market.sources import cbe, mubasher, tradingview, yahoo

SAMPLES = Path(__file__).parent / "fixtures" / "market"


def sample(name):
    text = (SAMPLES / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


# -- adapters, on recorded samples -----------------------------------------------------------------
def test_tradingview_lists_egx_and_us_with_iso_venues():
    egx = tradingview.parse(sample("tradingview_egx.json"), "egx", "2026-10-05")
    assert [(i.key, i.mic, i.country, i.currency) for i in egx.instruments] == [
        ("EG:COMI", "XCAI", "EG", "EGP"), ("EG:ETEL", "XCAI", "EG", "EGP")]  # no close, not EGX: skipped
    assert egx.quotes[0] == Quote("EG:COMI", "2026-10-05", D("85.25"), "tradingview-egx")
    us = tradingview.parse(sample("tradingview_us.json"), "us", "2026-10-05")
    assert [(i.key, i.mic, i.category) for i in us.instruments] == [
        ("US:AAPL", "XNAS", "STOCK"), ("US:BRK.B", "XNYS", "STOCK"), ("US:SPY", "ARCX", "FUND.OTHER")]
    with pytest.raises(SourceError, match="data list"):
        tradingview.parse({"error": "blocked"}, "egx", "2026-10-05")


def test_mubasher_funds_and_their_history():
    funds = mubasher.parse_funds(sample("mubasher_funds.json"), {4104: "FUND.FIXED_INCOME"})
    assert [(i.key, i.name, i.currency, i.category) for i in funds.instruments][:2] == [
        ("EG:FUND:4104", "AZ Savings Fund", "EGP", "FUND.FIXED_INCOME"),
        ("EG:FUND:2207", "Beltone Fixed Income Fund Issuance 1 USD", "USD", "FUND.OTHER")]
    assert [(q.key, q.date, q.close) for q in funds.quotes] == [
        ("EG:FUND:4104", "2026-09-24", D("31.254321")), ("EG:FUND:2207", "2026-09-20", D("1.0412"))]
    history = mubasher.parse_history(sample("mubasher_history.csv"), "EG:FUND:4104")
    assert [(q.date, q.close) for q in history] == [("2022-12-18", D("10.01437")), ("2022-12-19", D("10.02"))]
    with pytest.raises(SourceError, match="paging|pages"):
        mubasher.parse_funds({"numberOfPages": 2, "rows": []})


def test_cbe_publishes_the_mid_rate_per_one_unit():
    rates = cbe.parse(sample("cbe_rates.html"), "2026-10-05")
    found = {q.key: q for q in rates.quotes}
    assert found["USD/EGP"] == Quote("USD/EGP", "2026-10-05", D("52.4315"), "cbe")  # (52.3624 + 52.5006) / 2
    assert found["JPY/EGP"].close == D("0.351508")  # quoted per 100 yen, published per yen
    assert set(found) == {"USD/EGP", "EUR/EGP", "JPY/EGP", "SAR/EGP", "GBP/EGP"}
    with pytest.raises(SourceError, match="no US dollar"):
        cbe.parse("<table><tr><td>Euro</td><td>1</td><td>2</td></tr></table>", "2026-10-05")


def test_yahoo_history_is_put_back_to_the_prices_that_traded():
    quotes = yahoo.parse(sample("yahoo_chart.json"), "EG:COMI")
    assert [(q.date, q.close) for q in quotes] == [  # a 2:1 split on the 26th: earlier closes doubled back
        ("2025-09-24", D("80")), ("2025-09-25", D("82")), ("2025-09-26", D("42.5"))]
    assert yahoo.symbol_for("EG:COMI") == "COMI.CA" and yahoo.symbol_for("US:BRK.B") == "BRK-B"
    assert yahoo.symbol_for("EG:FUND:4104") is None and yahoo.symbol_for("USD/EGP") == "EGP=X"


# -- checks -----------------------------------------------------------------------------------------
def _q(key, day, close, source):
    return Quote(key, day, D(close), source)


def test_checks_hold_back_a_jump_unless_a_second_source_or_the_official_one_says_so():
    published = {"EG:COMI": [Close("2026-10-01", "EG:COMI", D("80"))], "USD/EGP": [Close("2026-10-01", "USD/EGP", D("48"))],
                 "EG:FUND:1": [Close("2026-10-01", "EG:FUND:1", D("400"))]}
    categories = {"EG:COMI": "STOCK", "EG:ETEL": "STOCK", "USD/EGP": "CURRENCY", "EG:FUND:1": "FUND.EQUITY"}
    accepted, problems = checks.accept([
        _q("EG:COMI", "2026-10-02", "120", "tradingview-egx"),     # +50%, alone: held back
        _q("USD/EGP", "2026-10-02", "70", "cbe"),                  # +46%, official: used
        _q("EG:FUND:1", "2026-10-02", "10", "mubasher-funds"),     # 1:40 unit split: used, reported
        _q("EG:ETEL", "2026-10-02", "41.9", "tradingview-egx"),    # nothing published yet: used
        _q("EG:ETEL", "2026-10-02", "43.0", "yahoo-latest"),       # disagrees by 2.6%: reported
        _q("EG:COMI", "2027-01-01", "80", "tradingview-egx"),      # in the future: refused
    ], published, categories, "2026-10-02")
    assert sorted((q.key, q.close) for q in accepted) == [
        ("EG:ETEL", D("41.9")), ("EG:FUND:1", D("10")), ("USD/EGP", D("70"))]
    text = "\n".join(problems)
    assert "EG:COMI 2026-10-02 held back" in text and "unit split" in text and "in the future" in text
    assert "tradingview-egx says 41.9, yahoo-latest says 43.0" in text

    confirmed, _ = checks.accept([_q("EG:COMI", "2026-10-02", "120", "tradingview-egx"),
                                  _q("EG:COMI", "2026-10-02", "120.5", "yahoo-latest")], published, categories, "2026-10-02")
    assert confirmed == [_q("EG:COMI", "2026-10-02", "120", "tradingview-egx")]  # a second source agrees


# -- whole runs against a fake network --------------------------------------------------------------
class FakeNet:
    """Answers each source's URL from samples; `failing` names sources that are down."""

    def __init__(self, failing=(), egx_close="85.25"):
        self.failing, self.egx_close = set(failing), egx_close

    def _fail(self, name):
        if name in self.failing:
            raise SourceError(f"{name} answered HTTP 403")

    def post_json(self, url, payload):
        if "egypt" in url:
            self._fail("tradingview-egx")
            rows = [{"s": f"EGX:T{i:03d}", "d": [f"T{i:03d}", f"Company {i}", 10 + i, "EGP", "stock", "common", "EGX"]}
                    for i in range(160)]
            rows.append({"s": "EGX:COMI", "d": ["COMI", "CIB", float(self.egx_close), "EGP", "stock", "common", "EGX"]})
            return {"data": rows}
        self._fail("tradingview-us")
        kind = "fund" if payload["filter"][1]["right"] == "fund" else "stock"
        count = 100 if kind == "fund" else 420
        return {"data": [{"s": f"NASDAQ:{kind[0].upper()}{i:03d}", "d": [f"{kind[0].upper()}{i:03d}", f"{kind} {i}",
                                                                         50 + i, "USD", kind, "etf" if kind == "fund" else "common",
                                                                         "NASDAQ"]} for i in range(count)]}

    def get_json(self, url, params=None):
        if "mubasher" in url:
            self._fail("mubasher-funds")
            return {"numberOfPages": 1, "rows": [{"fundId": i, "name": f"Fund {i}", "price": 10 + i, "date": "1 October 2026"}
                                                 for i in range(1, 111)]}
        self._fail("yahoo")
        return sample("yahoo_chart.json")

    def get_text(self, url, params=None):
        if "cbe.org.eg" in url:
            self._fail("cbe")
            return sample("cbe_rates.html").replace("05/10/2026", "01/10/2026")
        self._fail("mubasher-history")
        return sample("mubasher_history.csv")


def test_a_run_writes_every_market_and_a_failing_source_keeps_its_last_prices(tmp_path):
    folder = tmp_path / "market"
    health = collect(folder, FakeNet(), "2026-10-01", "2026-10-01T22:30:00Z")  # a Thursday: EGX and US both trade
    assert all(health[name]["ok"] for name in ("tradingview-egx", "mubasher-funds", "cbe", "tradingview-us"))
    market = MarketFile.open(folder)
    assert len(market.instruments()) == 161 + 110 + 5 + 520
    assert market.close_on("EG:COMI", "2026-10-01").close == D("85.25")
    assert market.close_on("USD/EGP", "2026-10-01").close == D("52.4315")

    # Next day (Friday): EGX does not trade, CBE is down, and nothing published is lost or changed.
    health = collect(folder, FakeNet(failing={"cbe"}), "2026-10-02", "2026-10-02T22:30:00Z")
    assert "tradingview-egx" in health and health["tradingview-egx"]["checked_at"] == "2026-10-01T22:30:00Z"  # skipped
    assert health["cbe"]["ok"] is False and health["cbe"]["failures_in_a_row"] == 1 and "403" in health["cbe"]["error"]
    assert health["cbe"]["last_ok"] == "2026-10-01T22:30:00Z"
    market = MarketFile.open(folder)
    assert market.close_on("USD/EGP", "2026-10-02").close == D("52.4315")  # the last good rate stays

    # Sunday: EGX trades again; a 60% jump in CIB from one source is held back and reported.
    health = collect(folder, FakeNet(egx_close="136.4"), "2026-10-04", "2026-10-04T22:30:00Z")
    assert MarketFile.open(folder).latest("EG:COMI") == Close("2026-10-01", "EG:COMI", D("85.25"))
    assert any("EG:COMI 2026-10-04 held back" in p for p in health["_run"]["problems"])
    assert health["cbe"]["ok"] is True and health["cbe"]["failures_in_a_row"] == 0


def test_a_source_that_answers_too_little_counts_as_failing(tmp_path):
    class Thin(FakeNet):
        def get_json(self, url, params=None):
            return {"numberOfPages": 1, "rows": [{"fundId": 1, "name": "One fund", "price": 10, "date": "1 October 2026"}]}

    health = collect(tmp_path / "m", Thin(), "2026-10-01", "2026-10-01T22:30:00Z", markets=("funds",))
    assert health["mubasher-funds"]["ok"] is False and "fewer than the 100 expected" in health["mubasher-funds"]["error"]


def test_backfill_brings_whole_histories(tmp_path):
    folder = tmp_path / "market"
    collect(folder, FakeNet(), "2026-10-01", "2026-10-01T22:30:00Z")
    health = backfill(folder, FakeNet(), ["EG:COMI", "EG:FUND:4", "EG:NOPE"], "2026-10-01", "2026-10-01T23:00:00Z")
    market = MarketFile.open(folder)
    assert market.close_on("EG:COMI", "2025-09-25") == Close("2025-09-25", "EG:COMI", D("82"))
    assert market.close_on("EG:FUND:4", "2022-12-19") == Close("2022-12-19", "EG:FUND:4", D("10.02"))
    assert any("EG:NOPE: not in the instrument list" in p for p in health["_run"]["problems"])
