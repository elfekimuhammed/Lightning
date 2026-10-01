"""Small, authenticated loopback host used by the Windows feasibility build.

This owns no application database. The production session runtime will be wired
only after the Windows feasibility gate passes.
"""
from __future__ import annotations

import hmac
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field

import uvicorn
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse


@dataclass
class Credentials:
    origin: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    launch_code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    cookie_name: str = field(default_factory=lambda: "lightning_" + secrets.token_hex(12))
    expires: float = field(default_factory=lambda: time.monotonic() + 120)
    used: bool = False


def _equal(value: str, expected: str) -> bool:
    return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))


class LocalGuard:
    def __init__(self, app, credentials: Credentials):
        self.app = app
        self.credentials = credentials

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cfg = self.credentials
        request = Request(scope)

        async def secured_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"cache-control", b"no-store"),
                    (b"referrer-policy", b"same-origin"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"content-security-policy", b"default-src 'none'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
                ])
                message = {**message, "headers": headers}
            await send(message)

        response = None
        if request.headers.get("host") != cfg.origin.removeprefix("http://"):
            response = PlainTextResponse("Bad host", 400)
        elif request.url.path == "/__launch":
            if (request.method != "GET" or cfg.used or time.monotonic() >= cfg.expires
                    or not _equal(request.query_params.get("code", ""), cfg.launch_code)):
                response = PlainTextResponse("Launch link expired. Restart Lightning.", 403)
            else:
                cfg.used = True
                response = RedirectResponse("/", 303)
                response.set_cookie(cfg.cookie_name, cfg.token, httponly=True, samesite="strict")
        elif not _equal(request.cookies.get(cfg.cookie_name, ""), cfg.token):
            response = PlainTextResponse("Forbidden", 403)
        else:
            site = request.headers.get("sec-fetch-site")
            if request.method in ("GET", "HEAD"):
                valid = site in (None, "none", "same-origin")
            else:
                valid = (site == "same-origin" if site is not None
                         else request.headers.get("origin") == cfg.origin)
            if not valid:
                response = PlainTextResponse("Forbidden", 403)
        if response is not None:
            return await response(scope, receive, secured_send)
        await self.app(scope, receive, secured_send)


def probe_app(credentials: Credentials, checks: dict):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    async def index():
        return HTMLResponse("""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Lightning desktop check</title>
<style>body{font:18px system-ui;background:#f2f8f6;color:#173d32;margin:0;padding:8vw}
main{max-width:680px;padding:40px;background:white;border-radius:20px}h1{font-size:32px}
p{line-height:1.6}small{color:#52655d}</style><main id="probe-ready">
<small>LIGHTNING · WINDOWS FEASIBILITY BUILD</small><h1>The desktop window is ready.</h1>
<p>This build checks the Windows window, protected local server, bundled resources,
password encryption, recovery keys and encrypted backups.</p>
<p>It uses temporary test data only. It does not open your financial database.</p>
<small>This is an engineering check, not the beta finance application.</small></main></html>""")

    @app.get("/api/check")
    async def check():
        return JSONResponse({"ok": bool(checks) and all(value is True for value in checks.values()), "checks": checks})

    return LocalGuard(app, credentials)


class LocalServer:
    def __init__(self, checks: dict):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.origin = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.credentials = Credentials(self.origin)
        self.server = uvicorn.Server(uvicorn.Config(
            probe_app(self.credentials, checks), log_config=None, access_log=False,
            log_level="critical", http="h11", loop="asyncio", ws="none",
            lifespan="on", server_header=False, date_header=False,
            timeout_graceful_shutdown=5,
        ))
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]},
                                       name="lightning-loopback", daemon=True)

    @property
    def launch_url(self) -> str:
        return f"{self.origin}/__launch?code={self.credentials.launch_code}"

    def start(self) -> "LocalServer":
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.stop()
                raise RuntimeError("The local server could not start")
            time.sleep(0.02)
        return self

    def stop(self) -> None:
        self.server.should_exit = True
        if self.thread.ident is not None:
            self.thread.join(10)
        if self.thread.is_alive():
            raise RuntimeError("The local server did not stop cleanly")
        self.socket.close()
