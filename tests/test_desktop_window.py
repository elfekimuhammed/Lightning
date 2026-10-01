from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from lightning.desktop.window import _allowed_navigation, _origin, run_window


ORIGIN = ("http", "127.0.0.1", 43123)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://127.0.0.1:43123/", True),
        ("http://127.0.0.1:43123/path?launch=secret", True),
        ("about:blank", True),
        ("https://127.0.0.1:43123/", False),
        ("http://127.0.0.1:43124/", False),
        ("http://localhost:43123/", False),
        ("http://user@127.0.0.1:43123/", False),
        ("https://example.com/", False),
        ("file:///tmp/page.html", False),
        ("javascript:alert(1)", False),
    ],
)
def test_navigation_allowlist_is_exact(url, expected):
    assert _allowed_navigation(url, ORIGIN) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("http://127.0.0.1:43123", ORIGIN),
        ("http://localhost/", ("http", "localhost", 80)),
        ("https://localhost:443/", ("https", "localhost", 443)),
        ("http://[::1]:43123", ("http", "::1", 43123)),
    ],
)
def test_parse_loopback_origin(value, expected):
    assert _origin(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "http://127.0.0.1/path",
        "http://user:pass@127.0.0.1:80",
        "http://127.0.0.1:bad",
    ],
)
def test_reject_invalid_origin(value):
    with pytest.raises(ValueError):
        _origin(value)


def test_linux_import_and_call_do_not_import_webview(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    was_loaded = "webview" in sys.modules
    with pytest.raises(RuntimeError, match="only on Windows"):
        run_window("http://127.0.0.1:43123/", "http://127.0.0.1:43123")
    assert ("webview" in sys.modules) is was_loaded


def test_adapter_defers_platform_imports_until_run():
    source = Path(__file__).resolve().parents[1] / "lightning/desktop/window.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    module_imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all(
        name.split(".")[0] not in {"webview", "clr", "System", "Microsoft"}
        for node in module_imports
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
        )
        if name is not None
    )
