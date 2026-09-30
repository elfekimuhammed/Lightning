"""FastAPI app factory. The UI only calls services/workflows — no SQL, no financial math."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lightning.bootstrap import Container
from lightning.core.dates import fmt_date, month_of, today
from lightning.core.errors import NotFoundError
from lightning.core.figures import FIGURES
from lightning.core.money import ZERO, fmt

UI_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(UI_DIR / "templates"))


def _minus(text: str) -> str:
    """Screens show a true minus (−5,000.00); exports keep the ASCII hyphen."""
    return "\u2212" + text[1:] if text.startswith("-") else text


def _money(value, signed: bool = False, places: int = 2) -> str:
    if value is None or isinstance(value, Decimal):
        return _minus(fmt(value, places, signed))
    # Re-rendered forms hand back what the user typed ("45,000.00", "−450");
    # show it as typed instead of failing the whole page.
    text = str(value).strip().replace(",", "").replace("\u2212", "-")
    try:
        return _minus(fmt(Decimal(text), places, signed))
    except InvalidOperation:
        return str(value)


def _tone(value) -> str:
    if value is None:
        return ""
    return "neg" if value < ZERO else ("pos" if value > ZERO else "zero")


def _keep_dates(text) -> Markup:
    """Dates never break across lines (a narrow key note would split 2026-10-03 at a hyphen)."""
    return Markup(re.sub(r"\b(\d{4}-\d{2}(?:-\d{2})?)\b", r'<span class="nowrap">\1</span>', str(escape(text))))


templates.env.filters["money"] = _money
templates.env.filters["tone"] = _tone
templates.env.filters["keep_dates"] = _keep_dates


def _units(value) -> str:
    """A quantity with no trailing zeros: 25 units, 1 piece, 12.5 g, 1,250 shares."""
    if value is None:
        return ""
    text = f"{Decimal(value):,.4f}".rstrip("0").rstrip(".")
    return text


templates.env.filters["units"] = _units
templates.env.globals["abs"] = abs


def _back_url(request) -> str:
    """Where a full page's Back button goes: the page it was opened from (``return_to``), only if
    it is a page of this app. Empty when there is nowhere to go back to."""
    raw = str(request.query_params.get("return_to", "") or "")
    parts = urlsplit(raw)
    if parts.netloc and parts.netloc != request.url.netloc:
        return ""
    path = parts.path or ""
    if not path.startswith("/") or path.startswith("//") or path == request.url.path:
        return ""
    query = "&".join(q for q in parts.query.split("&") if q and not q.startswith("popup="))
    return path + (f"?{query}" if query else "")


templates.env.globals["back_url"] = _back_url
templates.env.globals["fig"] = FIGURES


def container(request: Request) -> Container:
    current = request.app.state.container
    if current is None:
        raise RuntimeError("Financial routes require an unlocked profile")
    return current


def render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    c = container(request)
    context.setdefault("msg", request.query_params.get("msg", ""))
    context.setdefault("error", "")
    context.setdefault("error_field", "")
    total, owned_total, groups = c.reporting.sidebar(today())
    return templates.TemplateResponse(
        request,
        name,
        {
            "base": c.base_currency,
            "today": fmt_date(today()),
            "this_month": month_of(today()),
            "path": request.url.path,
            "sidebar_total": total,
            "sidebar_owned_total": owned_total,
            "sidebar_groups": groups,
            "csrf": getattr(request.state, "csrf", ""),
            "session_epoch": getattr(request.state, "session_epoch", ""),
            "session_token": getattr(request.state, "session_token", ""),
            **context,
        },
        status_code=status_code,
    )


def redirect(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url, status_code=303)


def create_app(c: Container | None = None) -> FastAPI:
    from .routes import accounts, bank_imports, birdview, budget, categories, counterparties, dashboard, integrity, investments, physical_items, planning, reserves, search, settings, transactions

    app = FastAPI(title="Lightning", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.container = c
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def same_origin_posts(request: Request, call_next):
        if request.method == "POST":
            host = request.headers.get("host", "").lower()
            for header in ("origin", "referer"):
                value = request.headers.get(header)
                if value and urlsplit(value).netloc.lower() != host:
                    return PlainTextResponse("Cross-origin form submission blocked.", status_code=403)
        return await call_next(request)

    @app.get("/__health", include_in_schema=False)
    async def health():
        return PlainTextResponse("lightning-ok")

    app.mount("/static", StaticFiles(directory=str(UI_DIR / "static")), name="static")
    for module in (dashboard, accounts, bank_imports, birdview, transactions, budget, investments, physical_items, planning, reserves, integrity, counterparties, categories, settings, search):
        app.include_router(module.router)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError):
        return render(request, "not_found.html", status_code=404, message=exc.message)

    return app
