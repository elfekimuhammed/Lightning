"""Bring a local market folder up to date from the published one, downloading only files that changed.

Every changed file is downloaded and checked against the published manifest before any is written, so a
failed or damaged download changes nothing; the manifest is written last (bundle.install)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .bundle import FILE_NAME, MAX_UNPACKED, SCHEMA, MarketFileError, install

DEFAULT_URL = "https://raw.githubusercontent.com/elfekimuhammed/Lightning-downloads/main/market/"
DAILY_MONTHS = 13


def _get(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Lightning (market file update)", "Accept-Encoding": "gzip"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_UNPACKED)
            if response.headers.get("Content-Encoding") == "gzip":  # about a quarter of the size on the wire
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as unpacked:
                    data = unpacked.read(MAX_UNPACKED)
            return data
    except (URLError, TimeoutError, OSError, EOFError) as exc:
        raise MarketFileError(f"Could not reach the price file ({exc}). Your saved prices stay in use.") from None


def update_folder(folder: Path, base_url: str = DEFAULT_URL, timeout: float = 20.0,
                  daily_months: int = DAILY_MONTHS) -> list[str]:
    """Download what changed into `folder`; return the names of the files that were new or changed."""
    folder, base = Path(folder), base_url.rstrip("/") + "/"
    try:
        remote = json.loads(_get(base + "manifest.json", timeout))
    except ValueError:
        raise MarketFileError("The published price file's manifest is not readable.") from None
    if not isinstance(remote, dict) or remote.get("schema") != SCHEMA or not isinstance(remote.get("files"), dict):
        raise MarketFileError("The published price file needs a newer Lightning; your saved prices stay in use.")
    if any(not FILE_NAME.fullmatch(name) for name in remote["files"]):
        raise MarketFileError("The published price file lists a file it may not hold. Nothing was changed.")
    daily = sorted(name for name in remote["files"] if name.startswith("daily/"))
    keep = {n: e for n, e in remote["files"].items() if not n.startswith("daily/") or n in daily[-daily_months:]}
    changed = {}
    for name, entry in sorted(keep.items()):
        target = folder / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry.get("sha256"):
            continue
        data = _get(base + name, timeout)
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise MarketFileError(f"{name} arrived damaged (its checksum does not match). Nothing was changed.")
        changed[name] = data
    install(folder, changed, dict(remote, files=keep))
    return sorted(changed)
