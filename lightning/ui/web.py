"""FastAPI app factory. The UI only calls services/workflows — no SQL, no financial math."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from lightning.bootstrap import Container
from lightning.core.dates import fmt_date, month_of, today
from lightning.core.errors import NotFoundError
from lightning.core.money import ZERO, fmt

UI_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(UI_DIR / "templates"))


def _money(value, signed: bool = False, places: int = 2) -> str:
    return fmt(value if value is None or isinstance(value, Decimal) else Decimal(str(value)), places, signed)


def _tone(value) -> str:
    if value is None:
        return ""
    return "neg" if value < ZERO else ("pos" if value > ZERO else "zero")


templates.env.filters["money"] = _money
templates.env.filters["tone"] = _tone
templates.env.globals["abs"] = abs


def container(request: Request) -> Container:
    return request.app.state.container


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
            **context,
        },
        status_code=status_code,
    )


def redirect(url: str, msg: str = "") -> RedirectResponse:
    if msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url, status_code=303)


def create_app(c: Container) -> FastAPI:
    from .routes import accounts, bank_imports, birdview, budget, categories, counterparties, dashboard, integrity, investments, physical_items, reserves, search, settings, transactions

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
    for module in (dashboard, accounts, bank_imports, birdview, transactions, budget, investments, physical_items, reserves, integrity, counterparties, categories, settings, search):
        app.include_router(module.router)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError):
        return render(request, "not_found.html", status_code=404, message=exc.message)

    return app
