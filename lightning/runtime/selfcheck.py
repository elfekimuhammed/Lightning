"""Frozen-app acceptance using a disposable household, never user data."""
import asyncio
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from lightning.ui.web import UI_DIR, create_app

from .session import ProfileSession

# The main finance pages, rendered from the bundle on an encrypted synthetic profile. A template,
# static file or module missing from the build fails here, not on a user's PC.
FINANCE_PAGES = ("/", "/accounts/new", "/transactions", "/budget", "/plan", "/investments",
                 "/birdview/expenses", "/settings")
_STATIC_LINK = re.compile(r'(?:href|src)="(/static/[^"?#]+)')
_FONT_URL = re.compile(r"url\(\s*['\"]?\./([^'\")]+)")


def get(app, path: str) -> tuple[int, bytes]:
    """One GET request through the app in this thread, with no server or network: (status, body).

    The encrypted database only answers on the thread that opened it, and every finance route is
    async, so the whole request runs on this thread's event loop."""
    import httpx

    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://127.0.0.1") as client:
            response = await client.get(path)
            return response.status_code, response.content

    return asyncio.run(request())


def finance_page_checks(container) -> dict[str, bool]:
    """Render each finance page and every app file the Overview and the font sheet name."""
    from lightning.demo import build_demo  # an offline sample household, so pages have content

    if not container.accounts.list():
        build_demo(container)
    app = create_app(container)
    checks: dict[str, bool] = {}
    pages = list(FINANCE_PAGES)
    first_account = next(iter(container.accounts.list()), None)
    if first_account is not None:
        pages.append(f"/accounts/{first_account.id}")
    static: set[str] = set()
    for path in pages:
        started = perf_counter()
        status, body = get(app, path)
        text = body.decode("utf-8", "replace")
        checks[f"page {path}"] = (status == 200 and "</html>" in text and "Traceback" not in text
                                  and perf_counter() - started < 30)
        static.update(_STATIC_LINK.findall(text))
    fonts = (UI_DIR / "static" / "fonts" / "fonts.css").read_text(encoding="utf-8")
    static.update(f"/static/fonts/{name}" for name in _FONT_URL.findall(fonts))
    checks["static files linked"] = bool(static)
    for path in sorted(static):
        status, body = get(app, path)
        checks[f"file {path}"] = status == 200 and bool(body)
    return checks


def run_profile_checks() -> dict[str, bool]:
    checks = {"profile_resources": all((UI_DIR / item).is_file() for item in (
        "templates/profiles.html", "static/profiles.css", "static/session.js",
        "static/app.js", "static/fonts/fonts.css",
    )), "profile_setup": False, "profile_reopen": False, "profile_recovery": False,
              "finance_routes": False, "profile_backup": False}
    with TemporaryDirectory(prefix="lightning-profile-check-") as folder:
        session = ProfileSession(Path(folder) / "Profiles")
        try:
            pending = session.prepare("Synthetic household", "temporary synthetic password", "temporary synthetic password",
                                      "Synthetic question?", "Synthetic answer")
            session.confirm(pending.recovery)
            path = session.paths.db_path
            session.container.settings.set("profile_check", "synthetic marker")
            checks["profile_setup"] = path.is_file() and b"synthetic marker" not in path.read_bytes()
            app = create_app(session.container)
            checks["finance_routes"] = (str(app.url_path_for("dashboard")) == "/"
                                        and str(app.url_path_for("new_account")) == "/accounts/new")
            checks.update(finance_page_checks(session.container))
            session.close()
            session.unlock(str(path), "temporary synthetic password")
            checks["profile_reopen"] = session.container.settings.get("profile_check") == "synthetic marker"
            checks["profile_backup"] = bool(session.container.backup_files())
            session.close()
            session.recover(str(path), pending.recovery, "synthetic ANSWER", "recovered synthetic password",
                            "recovered synthetic password")
            session.unlock(str(path), "recovered synthetic password")
            checks["profile_recovery"] = session.container.settings.get("profile_check") == "synthetic marker"
        finally:
            session.close()
    return checks
