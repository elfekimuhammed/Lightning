"""The market file (lightning/market): ISO names, writing, reading, checking and packing."""

import json
import zipfile
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from lightning.market.bundle import Close, Instrument, MarketFile, MarketFileError, pack, price_text, write
from lightning.market.iso import is_isin, venue_name

COMI = Instrument("EG:COMI", "Commercial International Bank", "STOCK", "EGP", isin="EGS60121C018", mic="XCAI",
                  ticker="COMI", country="EG", unit="share", aliases=("STK:COMI",), sources={"tradingview": "EGX:COMI"})
AZS = Instrument("EG:FUND:4104", "AZ Savings Fund", "FUND.FIXED_INCOME", "EGP", country="EG", unit="unit",
                 aliases=("FND:AZS",), sources={"mubasher": "4104"})
USD = Instrument("USD/EGP", "US dollar", "CURRENCY", "EGP", unit="USD", sources={"cbe": "USD"})
GOLD = Instrument("XAU:21K", "Gold 21K", "GOLD", "EGP", unit="g")


def _days(start: str, count: int, price: str, step: str = "0"):
    first = date.fromisoformat(start)
    return [(first + timedelta(days=i)).isoformat() for i in range(count)], D(price), D(step)


def _closes(key, start, count, price, step="0"):
    days, value, delta = _days(start, count, price, step)
    return [Close(day, key, value + delta * i) for i, day in enumerate(days)]


@pytest.fixture
def folder(tmp_path):
    closes = (_closes("EG:COMI", "2025-08-01", 429, "70", "0.05") + _closes("USD/EGP", "2026-09-01", 30, "48.5")
              + [Close("2026-09-24", "EG:FUND:4104", D("31.254321"))] + _closes("XAU:21K", "2026-10-01", 3, "4610"))
    write(tmp_path / "market", [COMI, AZS, USD, GOLD], closes, "2026-10-05T18:00:00Z", health={"cbe": {"ok": True}})
    return tmp_path / "market"


def test_iso_names():
    assert is_isin("US0378331005") and is_isin("EGS60121C018") and not is_isin("US0378331006")
    assert venue_name("XCAI") == "EGX" and venue_name("XNAS") == "Nasdaq" and venue_name("") == ""


@pytest.mark.parametrize("bad, says", [
    (Instrument("COMI", "x", "STOCK", "EGP"), "not one of the published forms"),
    (Instrument("EG:COMI", "x", "SHARES", "EGP"), "category"),
    (Instrument("EG:COMI", "x", "STOCK", "egp"), "ISO 4217"),
    (Instrument("EG:COMI", "x", "STOCK", "EGP", isin="EGS60121C019"), "ISO 6166"),
    (Instrument("EG:COMI", "x", "STOCK", "EGP", mic="EGX"), "ISO 10383"),
    (Instrument("EG:COMI", "x", "STOCK", "EGP", country="EGY"), "ISO 3166"),
    (Instrument("XAU:20K", "x", "GOLD", "EGP"), "published forms"),
])
def test_an_instrument_must_use_the_iso_forms(bad, says):
    with pytest.raises(MarketFileError, match=says):
        bad.check()


def test_round_trip_with_month_ends_derived_from_daily(folder):
    market = MarketFile.open(folder)
    assert market.created_at == "2026-10-05T18:00:00Z" and market.last_date() == "2026-10-03"
    instruments = market.instruments()
    assert instruments["EG:COMI"] == COMI and instruments["EG:FUND:4104"].sources == {"mubasher": "4104"}
    assert market.close_on("EG:COMI", "2025-08-01") == Close("2025-08-01", "EG:COMI", D("70"))
    assert market.close_on("USD/EGP", "2026-10-05") == Close("2026-09-30", "USD/EGP", D("48.5"))  # five days back
    assert market.close_on("EG:FUND:4104", "2026-10-03") == Close("2026-09-24", "EG:FUND:4104", D("31.254321"))  # a weekly NAV
    assert market.close_on("EG:FUND:4104", "2026-10-15") is None  # 21 days old: not used for that day
    assert market.close_on("EG:COMI", "2025-07-31") is None and market.close_on("US:AAPL", "2026-10-01") is None
    monthly = (folder / "monthly" / "2025.csv").read_text().splitlines()
    assert monthly[0] == "date,key,close" and "2025-08-31,EG:COMI,71.5" in monthly  # the month's last close
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["files"]["daily/2026-09.csv"]["first_date"] == "2026-09-01"
    assert manifest["files"]["instruments.csv"]["rows"] == 4


def test_a_damaged_or_foreign_file_is_refused(folder, tmp_path):
    (folder / "daily" / "2026-09.csv").write_text("date,key,close\n2026-09-01,USD/EGP,1\n")
    with pytest.raises(MarketFileError, match="damaged"):
        MarketFile.open(folder)
    (tmp_path / "x.zip").write_bytes(b"not a zip")
    with pytest.raises(MarketFileError, match="not a Lightning market file"):
        MarketFile.open(tmp_path / "x.zip")


def test_writing_refuses_what_it_cannot_promise(tmp_path):
    with pytest.raises(MarketFileError, match="does not list"):
        write(tmp_path / "m", [COMI], [Close("2026-09-01", "US:AAPL", D("1"))], "2026-10-05")
    with pytest.raises(MarketFileError, match="zero or negative"):
        write(tmp_path / "m", [COMI], [Close("2026-09-01", "EG:COMI", D("0"))], "2026-10-05")
    with pytest.raises(MarketFileError, match="share a key"):
        write(tmp_path / "m", [COMI, COMI], [], "2026-10-05")


def test_rewriting_removes_partitions_that_no_longer_exist(folder):
    write(folder, [COMI], _closes("EG:COMI", "2026-10-01", 2, "80"), "2026-10-06")
    assert sorted(p.name for p in (folder / "daily").iterdir()) == ["2026-10.csv"]
    assert MarketFile.open(folder).latest("EG:COMI") == Close("2026-10-02", "EG:COMI", D("80"))


def test_the_shipped_zip_keeps_every_month_end_and_the_last_daily_months(folder, tmp_path):
    packed = pack(folder, tmp_path / "market.zip", daily_months=2)
    names = set(zipfile.ZipFile(packed).namelist())
    assert {"daily/2026-09.csv", "daily/2026-10.csv", "monthly/2025.csv", "monthly/2026.csv"} <= names
    assert "daily/2025-08.csv" not in names
    market = MarketFile.open(packed)
    assert market.close_on("EG:COMI", "2025-08-31") == Close("2025-08-31", "EG:COMI", D("71.5"))  # from monthly
    assert market.close_on("EG:COMI", "2025-08-20") is None  # that day's daily close was not shipped


def test_prices_are_written_plainly():
    assert price_text(D("48.50")) == "48.5" and price_text(D("1E+3")) == "1000" and price_text(D("0.1234567")) == "0.123457"
