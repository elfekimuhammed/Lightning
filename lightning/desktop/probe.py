"""P0 executable: synthetic checks, then an isolated WebView2 window."""
from __future__ import annotations

import argparse
import json
import multiprocessing
import sys
from pathlib import Path


def run(argv=None) -> int:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="Lightning Windows feasibility check; no user data")
    parser.add_argument("--self-check", action="store_true", help="temporary crypto/resource checks only")
    parser.add_argument("--smoke", action="store_true", help="open, check and close the real Windows window")
    parser.add_argument("--report", type=Path, help="write a non-secret JSON result")
    args = parser.parse_args(argv)
    report = {"ok": False, "mode": "self-check" if args.self_check else "window", "checks": {}}
    try:
        from lightning.security.selfcheck import run_checks
        checks = run_checks()
        report["checks"] = checks
        if not checks or not all(value is True for value in checks.values()):
            raise RuntimeError("A feasibility check failed")
        if not args.self_check:
            from lightning.desktop.server import LocalServer
            from lightning.desktop.window import run_window
            server = LocalServer(checks).start()
            try:
                if run_window(server.launch_url, server.origin, smoke=args.smoke,
                              diagnostics=report.setdefault("window", {})) != 0:
                    raise RuntimeError("The WebView2 window check failed")
                report["checks"]["window"] = True
            finally:
                server.stop()
        report["ok"] = True
    except Exception as exc:
        # Do not log arbitrary exception messages: they can include URLs/keys.
        report["error_type"] = type(exc).__name__
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if sys.stdout is not None:
        print(json.dumps(report))
    if not report["ok"] and sys.platform == "win32" and not (args.self_check or args.smoke):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "The desktop check failed. Run with --self-check --report result.json for details. Microsoft Edge WebView2 Runtime is required.", "Lightning desktop check", 0x10)
    return 0 if report["ok"] else 1
