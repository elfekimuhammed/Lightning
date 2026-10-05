"""Filling a profile's prices from the market file: matching holdings to instruments, what is left for the
user, the delta download, a hand-imported market.zip, and the desktop upload limits for it."""

import gzip
import hashlib
import json
import threading
from datetime import date, timedelta
from decimal import Decimal as D
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from lightning.market import update as market_update
from lightning.market.bundle import Close, Instrument, MarketFile, MarketFileError, pack, write
from lightning.runtime import app as runtime_app
from lightning.runtime.http import MARKET_IMPORT_PATH, MAX_MARKET_IMPORT_BODY, request_body_limit
from lightning.ui.web import create_app
from lightning.workflows import market_prices
from lightning.workflows.market_prices import MarketPrices, current_file, file_info, local_folder

COMI = Instrument("EG:COMI", "Commercial International Bank", "STOCK", "EGP", isin="EGS60121C018", mic="XCAI",
                  ticker="COMI", country="EG", unit="share")
AZS = Instrument("EG:FUND:4104", "AZ Savings Fund", "FUND.FIXED_INCOME", "EGP", country="EG", unit="unit",
                 aliases=("FND:AZS",))
AAPL = Instrument("US:AAPL", "Apple", "STOCK", "USD", isin="US0378331005", mic="XNAS", ticker="AAPL", country="US")
USD = Instrument("USD/EGP", "US dollar", "CURRENCY", "EGP", unit="USD")


def _daily(key, first, last, price):
    day, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while day <= end:
        out.append(Close(day.isoformat(), key, D(price)))
        day += timedelta(days=1)
    return out


def publish(folder, created_at="2026-12-31T22:30:00Z", december="88"):
    """A market file with CIB daily except November, a weekly fund NAV, Apple in dollars and the dollar rate."""
    closes = (_daily("EG:COMI", "2026-09-01", "2026-10-31", "80") + _daily("EG:COMI", "2026-12-01", "2026-12-31", december)
              + [Close(d, "EG:FUND:4104", D(p)) for d, p in (("2026-09-24", "31.25"), ("2026-10-29", "31.6"),
                                                             ("2026-11-26", "31.9"), ("2026-12-24", "32.2"))]
              + _daily("US:AAPL", "2026-09-01", "2026-12-31", "230") + _daily("USD/EGP", "2026-09-01", "2026-12-31", "48.5"))
    write(folder, [COMI, AZS, AAPL, USD], closes, created_at)
    return folder


@pytest.fixture(autouse=True)
def no_bundled_file(monkeypatch, tmp_path):
    monkeypatch.setattr(market_prices, "BUNDLED", tmp_path / "absent" / "market.zip")


@pytest.fixture
def holdings(c, setup):
    accounts, _ = setup
    c.transactions.record_transfer("2026-09-01", accounts["cib"].id, accounts["thndr"].id, "40000")
    made = {"cib": c.assets.create_investment("CIB", "STOCK", "CIB", isin="EGS60121C018"),  # ISIN finds EG:COMI
            "azs": c.assets.create_investment("AZ Savings", "FUND.FIXED_INCOME", "AZS"),      # its alias FND:AZS
            "apple": c.assets.create_investment("Apple", "STOCK", "AAPL", mic="XNAS"),        # priced in pounds here
            "nope": c.assets.create_investment("Nope fund", "FUND.EQUITY", "NOPE")}
    for asset in made.values():
        c.investments.buy("2026-09-02", accounts["thndr"].id, asset.id, "10", "50")
    return made


def test_filling_matches_each_holding_and_leaves_the_rest_for_you(c, holdings, tmp_path):
    c.assets.set_price(holdings["cib"].id, "2026-10-31", "99")  # typed: wins over the file on that day
    report = MarketPrices(c.assets, c.reporting).fill(MarketFile.open(publish(tmp_path / "m")), date(2026, 12, 31))
    assert report.matched == ["CIB", "AZ Savings"] and report.unmatched == ["Nope fund"]
    assert report.other_currency == ["Apple"]  # a dollar price is never silently converted
    assert report.missing == [("CIB", "2026-11-30")]  # no CIB close within ten days of it
    assert report.added == 3 + 4  # CIB Sep, Oct, Dec (Dec 31 is also its latest); the fund's four month-ends
    assert c.assets.get_asset(holdings["cib"].id).market_key == "EG:COMI"
    assert c.assets.get_asset(holdings["azs"].id).market_key == "EG:FUND:4104"
    september = c.reporting.value_of(holdings["cib"].id, D(1), "2026-09-30")
    assert (september.price, september.source) == (D("80"), "MARKET")
    october = c.reporting.value_of(holdings["cib"].id, D(1), "2026-10-31")
    assert (october.price, october.source) == (D("99"), "MANUAL")
    fund = c.reporting.value_of(holdings["azs"].id, D(1), "2026-11-30")
    assert (fund.price, fund.price_date) == (D("31.9"), "2026-11-26")
    text = report.summary()
    assert text.startswith("Filled 7 prices for 2 investments from the price file of 2026-12-31.")
    assert "1 still missing: CIB 2026-11-30." in text and "Not in the file: Nope fund." in text and "Apple" in text


class Server:
    """Serves a published market folder over HTTP, gzipped when asked, and logs what was fetched."""

    def __init__(self, root, damage=""):
        self.root, self.damage, self.fetched = root, damage, []
        server = self

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self):
                name = self.path.lstrip("/")
                server.fetched.append(name)
                path = server.root / name
                if not path.is_file():
                    self.send_error(404)
                    return
                data = b"damaged" if name == server.damage else path.read_bytes()
                self.send_response(200)
                if "gzip" in self.headers.get("Accept-Encoding", ""):
                    data = gzip.compress(data)
                    self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(root)))
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(autouse=True)
def local_server_without_proxy(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")


def test_updating_downloads_only_what_changed_and_never_keeps_a_damaged_file(tmp_path):
    published, local = publish(tmp_path / "published"), tmp_path / "profile" / "market"
    with Server(published) as server:
        changed = market_update.update_folder(local, server.url)
        assert changed == sorted(json.loads((published / "manifest.json").read_text())["files"])
        assert MarketFile.open(local).latest("EG:COMI") == Close("2026-12-31", "EG:COMI", D("88"))
        server.fetched.clear()
        assert market_update.update_folder(local, server.url) == [] and server.fetched == ["manifest.json"]

        publish(published, "2027-01-01T22:30:00Z", december="90")  # only December and the year's month-ends change
        server.damage = "daily/2026-12.csv"
        with pytest.raises(MarketFileError, match="arrived damaged"):
            market_update.update_folder(local, server.url)
        assert MarketFile.open(local).created_at == "2026-12-31T22:30:00Z"  # the previous file is untouched
        server.damage, server.fetched[:] = "", []
        assert market_update.update_folder(local, server.url) == ["daily/2026-12.csv", "monthly/2026.csv"]
        assert MarketFile.open(local).latest("EG:COMI").close == D("90")


def test_a_published_manifest_cannot_name_a_file_outside_the_folder(tmp_path):
    published = publish(tmp_path / "published")
    manifest = json.loads((published / "manifest.json").read_text())
    manifest["files"]["../outside.csv"] = {"sha256": hashlib.sha256(b"x").hexdigest()}
    (published / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outside.csv").write_text("x")
    with Server(published) as server, pytest.raises(MarketFileError, match="may not hold"):
        market_update.update_folder(tmp_path / "profile" / "market", server.url)
    assert not (tmp_path / "profile").exists()


def test_the_prices_page_updates_imports_and_fills(c, holdings, tmp_path):
    client = TestClient(create_app(c), base_url="http://127.0.0.1")
    page = client.get("/investments/prices").text
    assert "No price file yet" in page and "Fill my prices" not in page
    assert "No price file yet" in client.post("/investments/prices/market/fill").text

    older = pack(publish(tmp_path / "old", "2026-11-01T22:30:00Z"), tmp_path / "old.zip")
    newer = pack(publish(tmp_path / "new"), tmp_path / "new.zip")
    done = client.post("/investments/prices/market/import", files={"file": ("market.zip", newer.read_bytes(), "application/zip")})
    assert "Price file imported. Filled 7 prices for 2 investments" in done.text
    assert file_info(c.data_dir) == {"created_at": "2026-12-31", "origin": "downloaded", "last_date": "2026-12-31",
                                     "instruments": 4}
    page = client.get("/investments/prices").text
    assert "Closing prices of 4 stocks, funds and currencies up to 2026-12-31" in page and "price file" in page
    refused = client.post("/investments/prices/market/import", files={"file": ("market.zip", older.read_bytes(), "application/zip")})
    assert "older than the one you have (2026-12-31). Nothing was changed." in refused.text
    junk = client.post("/investments/prices/market/import", files={"file": ("market.zip", b"not a zip", "application/zip")})
    assert "not a Lightning market file" in junk.text

    publish(tmp_path / "published", "2027-01-01T22:30:00Z", december="90")
    c.settings.set("market_url", "http://127.0.0.1:1/")  # nothing listens there
    assert "Could not reach the price file" in client.post("/investments/prices/market/update").text
    assert current_file(c.data_dir).created_at == "2026-12-31T22:30:00Z"
    with Server(tmp_path / "published") as server:
        c.settings.set("market_url", server.url)
        updated = client.post("/investments/prices/market/update").text
    assert "Price file updated. Filled" in updated
    assert c.reporting.value_of(holdings["cib"].id, D(1), "2026-12-31").price == D("90")
    assert local_folder(c.data_dir) == c.data_dir / "market"


def test_the_desktop_window_takes_one_bounded_market_file():
    assert request_body_limit(MARKET_IMPORT_PATH) == MAX_MARKET_IMPORT_BODY == 40 * 1024 * 1024
    assert runtime_app._form_file_limit(MARKET_IMPORT_PATH) == 1 and runtime_app._form_part_limit(MARKET_IMPORT_PATH) == MAX_MARKET_IMPORT_BODY
    assert runtime_app._form_file_limit("/investments/prices") == 0
