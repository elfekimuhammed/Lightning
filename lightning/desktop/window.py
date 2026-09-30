"""Minimal, fail-closed Windows WebView2 window adapter."""

from __future__ import annotations

import importlib.metadata
import threading
from urllib.parse import urlsplit

_PYWEBVIEW_VERSION = "6.2.1"
_SMOKE_TIMEOUT = 20.0
_STARTUP_TIMEOUT = 30.0


def _origin(value: str) -> tuple[str, str, int]:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("origin must be an HTTP(S) origin")
    if parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("origin must not contain credentials, path, query, or fragment")
    host = parsed.hostname.lower()
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("desktop origin must use loopback")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid origin port") from exc
    scheme = parsed.scheme.lower()
    return scheme, host, port if port is not None else (443 if scheme == "https" else 80)


def _allowed_navigation(uri: str, allowed_origin: tuple[str, str, int]) -> bool:
    if uri == "about:blank":
        return True
    try:
        parsed = urlsplit(uri)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return False
        scheme = parsed.scheme.lower()
        port = parsed.port
        candidate = (scheme, parsed.hostname.lower(), port if port is not None else (443 if scheme == "https" else 80))
        return candidate == allowed_origin
    except ValueError:
        return False


def _show_error(message: str) -> None:
    """Show a native Windows error without importing GUI bindings on other platforms."""
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, message, "Lightning", 0x10)


def run_window(url: str, origin: str, *, smoke: bool = False, diagnostics: dict | None = None) -> int:
    """Run one guarded WebView2 window; return nonzero for startup or smoke failures."""
    if __import__("sys").platform != "win32":
        raise RuntimeError("The Lightning desktop window is available only on Windows")

    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics["stage"] = "initializing"
    try:
        allowed_origin = _origin(origin)
        target = urlsplit(url)
        if not _allowed_navigation(url, allowed_origin) or target.scheme not in ("http", "https"):
            raise ValueError("URL must belong to the configured loopback origin")
        if importlib.metadata.version("pywebview") != _PYWEBVIEW_VERSION:
            raise RuntimeError("Lightning requires pywebview 6.2.1")

        import webview

        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["ALLOW_FILE_URLS"] = False
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        webview.settings["IGNORE_SSL_ERRORS"] = False
        webview.settings["REMOTE_DEBUGGING_PORT"] = None

        state: dict[str, object] = {"guard": False, "failure": None, "rejected": threading.Event()}
        app_ready = threading.Event()
        smoke_done = threading.Event()
        window_closed = threading.Event()
        result = {"code": 1 if smoke else 0}

        def fail(reason: str) -> None:
            diagnostics["failure"] = reason
            state["failure"] = reason
            result["code"] = 1
            smoke_done.set()
            native = window.native
            if native is not None:
                try:
                    from System import Action

                    native.BeginInvoke(Action(lambda: native.Close()))
                except Exception:
                    try:
                        if not native.InvokeRequired:
                            native.Close()
                    except Exception:
                        pass

        def before_show(*_args) -> None:
            diagnostics["stage"] = "native-window"
            try:
                if webview.renderer != "edgechromium":
                    raise RuntimeError("WebView2 renderer was not selected")
                native = window.native
                browser = getattr(native, "browser", None)
                control = getattr(browser, "webview", None)
                init_event = getattr(control, "CoreWebView2InitializationCompleted", None)
                if control is None or init_event is None:
                    raise RuntimeError("WebView2 initialization hook unavailable")

                def initialized(sender, args) -> None:
                    try:
                        if not args.IsSuccess:
                            raise RuntimeError("WebView2 initialization failed")
                        core = sender.CoreWebView2
                        if core is None:
                            raise RuntimeError("WebView2 core is unavailable")

                        def navigation_starting(_sender, event) -> None:
                            uri = str(event.Uri)
                            if not _allowed_navigation(uri, allowed_origin):
                                event.Cancel = True
                                state["rejected"].set()

                        def new_window(_sender, event) -> None:
                            event.set_Handled(True)
                            state["rejected"].set()

                        core.NavigationStarting += navigation_starting
                        core.NewWindowRequested += new_window
                        state["guard"] = True
                        diagnostics["stage"] = "navigation-guard-installed"

                        def navigate() -> None:
                            if not window.events.shown.wait(10):
                                fail("WebView2 window did not become visible")
                                return
                            try:
                                window.load_url(url)
                            except Exception:
                                fail("Could not open the local application")

                        threading.Thread(target=navigate, daemon=True).start()
                    except Exception:
                        fail("Could not install the WebView2 navigation guard")

                init_event += initialized
            except Exception:
                fail("Could not attach the WebView2 initialization guard")

        window = webview.create_window(
            "Lightning", "about:blank", width=1200, height=800, js_api=None
        )

        def require_edgechromium(renderer: str) -> bool | None:
            if renderer != "edgechromium":
                state["failure"] = "WebView2 renderer was not selected"
                result["code"] = 1
                return False
            return None

        window.events.initialized += require_edgechromium
        window.events.before_show += before_show
        window.events.closed += lambda *_args: (window_closed.set(), smoke_done.set())

        if smoke:
            def monitor_smoke() -> None:
                import time

                end = time.monotonic() + _SMOKE_TIMEOUT
                while time.monotonic() < end and not smoke_done.is_set():
                    if app_ready.is_set() and state["guard"]:
                        try:
                            if window.evaluate_js("Boolean(document.querySelector('#probe-ready'))"):
                                window.run_js(
                                    "(async()=>{try{const r=await fetch('/api/check');"
                                    "const j=await r.json();document.documentElement.dataset.lightningSmoke="
                                    "(r.ok&&new URL(r.url).origin===location.origin&&j.ok===true?"
                                    "'ok':'fail')}catch(e){"
                                    "document.documentElement.dataset.lightningSmoke='fail'}})()"
                                )
                                check_end = time.monotonic() + 5
                                while time.monotonic() < check_end:
                                    if window.evaluate_js(
                                        "document.documentElement.dataset.lightningSmoke||''"
                                    ) == "ok":
                                        window.run_js("location.href='https://example.com/'")
                                        if state["rejected"].wait(2):
                                            if not window_closed.is_set():
                                                result["code"] = 0
                                                diagnostics["stage"] = "smoke-passed"
                                        else:
                                            result["code"] = 1
                                        smoke_done.set()
                                        break
                                    if window.evaluate_js(
                                        "document.documentElement.dataset.lightningSmoke||''"
                                    ) == "fail":
                                        result["code"] = 1
                                        smoke_done.set()
                                        break
                                    threading.Event().wait(0.1)
                                break
                        except Exception:
                            result["code"] = 1
                            smoke_done.set()
                            break
                    threading.Event().wait(0.1)
                if not smoke_done.is_set():
                    result["code"] = 1
                    smoke_done.set()
                if result["code"]:
                    fail("WebView2 smoke check failed")
                else:
                    try:
                        window.destroy()
                    except Exception:
                        result["code"] = 1

            def on_loaded(*_args) -> None:
                try:
                    current_url = str(window.get_current_url() or "")
                    if current_url != "about:blank" and state["guard"] and _allowed_navigation(
                        current_url, allowed_origin
                    ):
                        app_ready.set()
                except Exception:
                    pass

            window.events.loaded += on_loaded
            threading.Thread(target=monitor_smoke, daemon=True).start()
        else:
            def on_loaded(*_args) -> None:
                try:
                    current_url = str(window.get_current_url() or "")
                    if current_url != "about:blank" and state["guard"] and _allowed_navigation(
                        current_url, allowed_origin
                    ):
                        app_ready.set()
                except Exception:
                    pass

            window.events.loaded += on_loaded

            def startup_watchdog() -> None:
                if not app_ready.wait(_STARTUP_TIMEOUT) and not window.events.closed.wait(0):
                    fail("The local application did not finish loading")

            threading.Thread(target=startup_watchdog, daemon=True).start()

        webview.start(gui="edgechromium", debug=False, private_mode=True)
        if state["failure"] and not smoke:
            _show_error(str(state["failure"]))
            return 1
        return int(result["code"])
    except Exception as exc:
        diagnostics["error_type"] = type(exc).__name__
        # Do not surface exception text: framework errors can contain the launch URL.
        if not smoke:
            try:
                _show_error("Lightning window failed to start. Check the local URL and WebView2 runtime.")
            except Exception:
                pass
        return 1
