"""A polite HTTP client for the collector: one request every few seconds, a User-Agent that names
Lightning, retries on network errors and server errors only, and loud failures on block pages."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import SourceError

# The usual crawler form (as search engines use), still naming Lightning: some sites' firewalls reject a
# request without it or without the headers every browser sends (CBE answered "Request Rejected").
USER_AGENT = "Mozilla/5.0 (compatible; Lightning-market-collector/1; +https://github.com/elfekimuhammed/Lightning)"
HEADERS = {"Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"}


class Polite:
    def __init__(self, min_interval: float = 3.0, retries: int = 3, timeout: float = 30.0):
        self.min_interval, self.retries, self.timeout = min_interval, retries, timeout
        self.requests = 0
        self._last = float("-inf")

    def _send(self, url: str, data: bytes | None, headers: dict) -> bytes:
        for attempt in range(1, self.retries + 1):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                with urlopen(Request(url, data=data, headers={"User-Agent": USER_AGENT, **HEADERS, **headers}),
                             timeout=self.timeout) as response:
                    return response.read(50_000_000)
            except HTTPError as exc:
                if exc.code < 500 or attempt == self.retries:
                    raise SourceError(f"{url} answered HTTP {exc.code}") from None
            except (URLError, TimeoutError) as exc:
                if attempt == self.retries:
                    raise SourceError(f"{url} could not be reached ({exc})") from None
            time.sleep(self.min_interval * attempt)
        raise SourceError(f"{url} failed")  # pragma: no cover

    def get(self, url: str, params: dict | None = None) -> bytes:
        return self._send(url + ("?" + urlencode(params) if params else ""), None, {})

    def get_text(self, url: str, params: dict | None = None) -> str:
        return self.get(url, params).decode("utf-8", errors="replace")

    def get_json(self, url: str, params: dict | None = None):
        return _json(self.get(url, params), url)

    def post_json(self, url: str, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        return _json(self._send(url, body, {"Content-Type": "application/json"}), url)


def _json(data: bytes, url: str):
    text = data.decode("utf-8", errors="replace").lstrip()
    if text.startswith("<"):
        raise SourceError(f"{url} returned a web page instead of data; it may be blocking us or may have moved")
    try:
        return json.loads(text)
    except ValueError:
        raise SourceError(f"{url} returned something that is not JSON") from None
