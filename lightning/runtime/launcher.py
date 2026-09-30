"""Linux-compatible browser shell for the same encrypted profile runtime."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from .app import profile_app
from .http import Host


def run_browser(root: Path | str | None = None, *, open_browser: bool = True) -> None:
    host = Host(lambda credentials: profile_app(credentials, root)).start()
    try:
        if open_browser:
            if not webbrowser.open(host.launch_url):
                print("Open this single-use local link within two minutes:", host.launch_url)
        else:
            # Deliberately shown only to the local user, never in HTTP access logs.
            print("Open this single-use local link within two minutes:", host.launch_url, flush=True)
        print("Lightning profiles are running locally. Press Ctrl+C here to stop.", flush=True)
        while host.thread.is_alive():
            host.thread.join(.5)
    except KeyboardInterrupt:
        pass
    finally:
        host.stop()
