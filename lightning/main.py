"""Start Lightning: back up, migrate, then serve the app on this computer only.

    python -m lightning                 # opens http://127.0.0.1:8765 in your browser
    python -m lightning --db my.db --port 9000 --no-browser
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

if sys.version_info < (3, 11):
    sys.exit("Lightning needs Python 3.11 or newer.")


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    from lightning.bootstrap import DEFAULT_DATA_DIR, build
    from lightning.ui.web import create_app

    parser = argparse.ArgumentParser(prog="lightning", description="Personal finance, in one place.")
    parser.add_argument("--db", default=str(DEFAULT_DATA_DIR / "lightning.db"), help="database file")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    url = f"http://127.0.0.1:{args.port}"
    # Reuse the server on repeated desktop launches before backing up or refreshing prices.
    try:
        with urlopen(f"{url}/__health", timeout=1) as response:
            if response.read(32) == b"lightning-ok":
                print(f"Lightning is already running at {url}.")
                return
    except (OSError, URLError):
        pass
    try:
        with socket.create_connection(("127.0.0.1", args.port), timeout=1):
            parser.error(f"port {args.port} is already used by another application")
    except OSError:
        pass

    container = build(args.db, backup_on_start=True)
    from lightning.assets.market_data import refresh_market_prices

    try:
        updated = refresh_market_prices(container)
        if updated:
            print(f"Updated {updated} investment price{'s' if updated != 1 else ''}.")
    except Exception:
        print("Investment price refresh skipped; existing saved prices remain in use.", file=sys.stderr)
    app = create_app(container)
    print(f"Lightning is running at {url}  (data: {container.db.path})  — press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
