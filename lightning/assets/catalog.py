"""Read the bundled EGX stock and Thndr mutual-fund picker catalogue."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path


CATALOGUE_FILE = Path(__file__).with_name("egx_instruments.csv")
@lru_cache(maxsize=1)
def instruments() -> list[dict[str, str]]:
    """Return searchable instrument records from the local, versioned CSV."""
    with CATALOGUE_FILE.open(encoding="utf-8-sig", newline="") as source:
        records = list(csv.DictReader(source))
    return sorted(records, key=lambda row: (row["kind"] != "Stocks", row["name"].casefold()))
