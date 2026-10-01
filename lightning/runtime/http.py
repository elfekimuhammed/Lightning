"""Authenticated, bounded loopback transport shared by browser and window shells."""
from __future__ import annotations

import asyncio
import hmac
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field

import uvicorn
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse

# Below Starlette's 1 MiB upload spool threshold: no uploaded CSV hits a plaintext
# temporary file. Larger imports need a separately designed in-memory upload path.
MAX_BODY = 512 * 1024


@dataclass
class Credentials:
    origin: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    launch_code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    cookie_name: str = field(default_factory=lambda: "lightning_" + secrets.token_hex(12))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    expires: float = field(default_factory=lambda: time.monotonic() + 120)
    used: bool = False


def equal(value: str, expected: str) -> bool:
    return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))


def body_receiver(body: bytes):
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        # The inner response owns cancellation of any disconnect listener.
        await asyncio.Event().wait()

    return receive


class Guard:
    def __init__(self, app, credentials: Credentials):
        self.app, self.credentials = app, credentials

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cfg = self.credentials
        request = Request(scope)
        scope.setdefault("state", {})["csp_nonce"] = cfg.nonce

        async def secured_send(message):
            if message["type"] == "http.response.start":
                csp = ("default-src 'none'; script-src 'self' 'nonce-" + cfg.nonce + "'; "
                       "script-src-attr 'none'; style-src 'self' 'unsafe-inline'; "
                       "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in
                           (b"cache-control", b"content-security-policy", b"referrer-policy")]
                # no-referrer on ordinary HTML makes Chromium send Origin:null
                # for native form POSTs. Keep exact-origin checks and use
                # same-origin, which still suppresses all external referrers.
                referrer = b"no-referrer" if request.url.path == "/__launch" else b"same-origin"
                headers.extend([(b"cache-control", b"no-store"), (b"referrer-policy", referrer),
                                (b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                                (b"content-security-policy", csp.encode("ascii"))])
                message = {**message, "headers": headers}
            await send(message)

        response = None
        origin = request.headers.get("origin")
        site = request.headers.get("sec-fetch-site")
        if request.headers.get("host") != cfg.origin.removeprefix("http://"):
            response = PlainTextResponse("Bad host", 400)
        elif origin is not None and origin != cfg.origin:
            response = PlainTextResponse("Forbidden origin", 403)
        elif site not in (None, "none", "same-origin"):
            response = PlainTextResponse("Forbidden site", 403)
        elif request.url.path == "/__launch":
            if request.method != "GET" or cfg.used or time.monotonic() >= cfg.expires or not equal(
                    request.query_params.get("code", ""), cfg.launch_code):
                response = PlainTextResponse("Launch link expired. Restart Lightning.", 403)
            else:
                cfg.used = True
                response = RedirectResponse("/profiles", 303)
                response.set_cookie(cfg.cookie_name, cfg.token, httponly=True, samesite="strict")
        elif not equal(request.cookies.get(cfg.cookie_name, ""), cfg.token):
            response = PlainTextResponse("Forbidden", 403)
        elif request.method not in ("GET", "HEAD") and origin != cfg.origin:
            response = PlainTextResponse("A same-origin form submission is required.", 403)
        if response is not None:
            return await response(scope, receive, secured_send)
        try:
            chunks = bytearray()
            async with asyncio.timeout(15):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunks.extend(message.get("body", b""))
                    if len(chunks) > MAX_BODY:
                        response = PlainTextResponse("Request too large. The current upload limit is 512 KiB.", 413)
                        return await response(scope, receive, secured_send)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await PlainTextResponse("Request timed out", 408)(scope, receive, secured_send)
        scope["state"]["request_body"] = bytes(chunks)
        await self.app(scope, body_receiver(bytes(chunks)), secured_send)


class Host:
    """Pre-bind before choosing an origin; ASGI thread owns the complete session."""

    def __init__(self, factory):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.socket.bind(("127.0.0.1", 0))
            self.origin = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
            self.credentials = Credentials(self.origin)
            self.app = factory(self.credentials)
            self.server = uvicorn.Server(uvicorn.Config(
                self.app, log_config=None, access_log=False, log_level="critical",
                http="h11", loop="asyncio", ws="none", lifespan="on",
                server_header=False, date_header=False, timeout_graceful_shutdown=5,
            ))
            self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.socket]},
                                           name="lightning-profile-owner", daemon=True)
        except BaseException:
            self.socket.close()
            raise

    @property
    def launch_url(self):
        return f"{self.origin}/__launch?code={self.credentials.launch_code}"

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.stop()
                raise RuntimeError("The local server could not start")
            time.sleep(.02)
        return self

    def stop(self):
        self.server.should_exit = True
        if self.thread.ident is not None:
            self.thread.join(10)
        if self.thread.is_alive():
            raise RuntimeError("The profile server did not stop cleanly")
        self.socket.close()
