"""Fill a profile's investment prices from the market file (docs/proposals/market_data.md).

The file comes with the app (lightning/market/market.zip) or is downloaded or imported into the profile's
market folder; the newer one is used. Each holding is matched to an instrument (ISIN,
then its saved key, then an alias such as STK:COMI, then country and ticker), and gets the close for every
month-end it was held plus its latest close. Prices are saved with source MARKET, so a price you typed on
the same day still wins, and an instrument priced in another currency is left for you (no silent
conversion). What the file lacks is listed, never guessed."""
from __future__ import annotations

import calendar
import json
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lightning.core.dates import fmt_date
from lightning.market.bundle import MarketFile, MarketFileError

SOURCE = "MARKET"
BUNDLED = Path(__file__).resolve().parents[1] / "market" / "market.zip"


@dataclass
class FillReport:
    file_date: str
    matched: list[str] = field(default_factory=list)
    added: int = 0
    missing: list[tuple[str, str]] = field(default_factory=list)     # (investment, month-end)
    unmatched: list[str] = field(default_factory=list)
    other_currency: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"Filled {self.added} price{'s' if self.added != 1 else ''} for {len(self.matched)} "
                 f"investment{'s' if len(self.matched) != 1 else ''} from the price file of {self.file_date[:10]}."]
        if self.missing:
            shown = ", ".join(f"{name} {day}" for name, day in self.missing[:3])
            parts.append(f"{len(self.missing)} still missing: {shown}{' and more' if len(self.missing) > 3 else ''}.")
        if self.unmatched:
            parts.append(f"Not in the file: {', '.join(self.unmatched[:3])}{' and more' if len(self.unmatched) > 3 else ''}.")
        if self.other_currency:
            parts.append(f"Priced in another currency, left for you: {', '.join(self.other_currency[:3])}.")
        return " ".join(parts)


def local_folder(data_dir: Path | None) -> Path | None:
    return Path(data_dir) / "market" if data_dir else None


def current_file(data_dir: Path | None) -> MarketFile | None:
    """The newest usable market file: the downloaded or imported one, or the one that came with the app."""
    found = []
    folder = local_folder(data_dir)
    for path in ([folder] if folder and (folder / "manifest.json").exists() else []) + ([BUNDLED] if BUNDLED.exists() else []):
        try:
            found.append(MarketFile.open(path))
        except MarketFileError:
            continue
    return max(found, key=lambda m: m.created_at, default=None)


def file_info(data_dir: Path | None) -> dict | None:
    """What the Prices page shows about the newest market file, read from its manifest alone (no checks,
    so the page stays fast; filling checks every file)."""
    found = []
    folder = local_folder(data_dir)
    try:
        if folder and (folder / "manifest.json").exists():
            found.append((json.loads((folder / "manifest.json").read_text(encoding="utf-8")), "downloaded"))
        if BUNDLED.exists():
            with zipfile.ZipFile(BUNDLED) as archive:
                found.append((json.loads(archive.read("manifest.json")), "came with Lightning"))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        pass
    found = [(m, origin) for m, origin in found if isinstance(m, dict) and isinstance(m.get("files"), dict)]
    if not found:
        return None
    manifest, origin = max(found, key=lambda pair: str(pair[0].get("created_at", "")))
    files = manifest["files"]
    return {"created_at": str(manifest.get("created_at", ""))[:10], "origin": origin,
            "last_date": max((str(e.get("last_date", "")) for e in files.values() if isinstance(e, dict)), default=""),
            "instruments": files.get("instruments.csv", {}).get("rows", 0)}


def _month_ends(first: date, last: date) -> list[str]:
    days, year, month = [], first.year, first.month
    while (year, month) <= (last.year, last.month):
        end = date(year, month, calendar.monthrange(year, month)[1])
        if end <= last:
            days.append(fmt_date(end))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return days


class MarketPrices:
    def __init__(self, assets, reporting):
        self.assets, self.reporting = assets, reporting

    def match(self, asset, market: MarketFile) -> str | None:
        instruments = market.instruments()
        if asset.isin:
            for key, instrument in instruments.items():
                if instrument.isin == asset.isin:
                    return key
        if asset.market_key in instruments:
            return asset.market_key
        for key, instrument in instruments.items():
            if asset.code in instrument.aliases:
                return key
        if asset.country and asset.mic:
            key = f"{asset.country}:{asset.ticker}"
            if key in instruments:
                return key
        return None

    def fill(self, market: MarketFile, today: date) -> FillReport:
        report = FillReport(market.created_at)
        first = self.reporting.first_activity_date()
        held: dict[int, list[str]] = {}
        if first:
            for day in _month_ends(date.fromisoformat(first[:10]), today):
                for holding in self.reporting.holdings(day)[0]:
                    if holding.quantity and holding.asset_id:
                        held.setdefault(holding.asset_id, []).append(day)
        for holding in self.reporting.holdings(fmt_date(today))[0]:
            if holding.quantity and holding.asset_id:
                held.setdefault(holding.asset_id, [])
        instruments = market.instruments()
        for asset_id, month_ends in sorted(held.items()):
            asset = self.assets.get_asset(asset_id)
            if asset.is_cash or asset.code.startswith(("OTH:ITEM-", "REF:")):
                continue
            key = self.match(asset, market)
            if key is None:
                report.unmatched.append(asset.name)
                continue
            if instruments[key].currency != asset.currency:
                report.other_currency.append(asset.name)
                continue
            self.assets.link_market(asset.id, key)
            report.matched.append(asset.name)
            found = {}
            for day in month_ends:
                close = market.close_on(key, day)
                if close is None:
                    report.missing.append((asset.name, day))
                else:
                    found[close.date] = close
            latest = market.latest(key)
            if latest and (today - date.fromisoformat(latest.date)).days <= 10:
                found[latest.date] = latest
            for close in found.values():  # one price per day, even when a month-end is also the latest close
                self.assets.set_price(asset.id, close.date, close.close, source=SOURCE)
            report.added += len(found)
        return report
