"""Check every main page in the phone frame at 360 and 320 px wide (guideline C12): nothing may scroll
sideways. Starts the phone app on a dummy profile with the sample household. Needs Playwright and Chromium.

    python tools/phone_check.py [--shots folder]      # prints each page that overflows and its widest element
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PAGES = ("/", "/birdview/expenses", "/financial-health", "/budget", "/plan", "/plan/recurring", "/plan/loans",
         "/plan/reserves", "/investments", "/investments/planner", "/investments/prices", "/accounts", "/transactions",
         "/money-from-others", "/settings", "/categories", "/counterparties", "/checks", "/profiles",
         "/profiles/devices", "/accounts/1", "/accounts/1/transaction/new", "/accounts/add-transaction")
WIDEST = """() => { const w = innerWidth; let worst = null, right = w;
  for (const el of document.querySelectorAll('body *')) { const r = el.getBoundingClientRect();
    if (r.width && r.right > right + 0.5) { right = r.right; worst = el; } }
  if (!worst) return null;
  return {right: Math.round(right), tag: worst.tagName.toLowerCase(), cls: worst.className && worst.className.baseVal === undefined ? worst.className : '', text: (worst.innerText || '').slice(0, 40)}; }"""


def run(shots: Path | None = None) -> list[str]:
    from playwright.sync_api import sync_playwright
    from lightning.runtime.app import profile_app
    from lightning.runtime.devices import Devices
    from lightning.runtime.http import Host

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        host = Host(lambda c: profile_app(c, root / "docs", devices=Devices(root / "app", port=0), phone=True)).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
                page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=2, is_mobile=True,
                                        has_touch=True)
                page.goto(host.launch_url)
                page.goto(host.origin + "/profiles/new")
                page.fill("input[name=name]", "Mohab")
                for field in ("password", "confirm"):
                    page.fill(f"input[name={field}]", "a dummy phone password")
                page.fill("input[name=answer]", "Dummy")
                if page.locator("select[name=question]").count():
                    page.select_option("select[name=question]", index=1)
                elif page.locator("input[name=question]").count():
                    page.fill("input[name=question]", "Dummy question?")
                page.click("button[type=submit]")
                key = re.search(r"\d{4}-\d{4}-\d{4}", page.content()).group(0)
                page.fill("input[name=recovery]", key)
                page.click("form[action='/profiles/confirm'] button[type=submit]")
                page.goto(host.origin + "/")
                page.evaluate("""async () => { const t = document.querySelector('meta[name=lightning-session]').content;
                    await fetch('/demo', {method: 'POST', body: new URLSearchParams({__session: t})}); }""")
                for width in (360, 320):
                    page.set_viewport_size({"width": width, "height": 800})
                    for path in PAGES:
                        response = page.goto(host.origin + path)
                        if response is None or response.status >= 400:
                            problems.append(f"{width} {path}: HTTP {response.status if response else '?'}")
                            continue
                        over = page.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                        if over > 0:
                            problems.append(f"{width} {path}: {over}px sideways; widest {page.evaluate(WIDEST)}")
                        if shots is not None and width == 360:
                            shots.mkdir(parents=True, exist_ok=True)
                            name = path.strip("/").replace("/", "-") or "overview"
                            page.screenshot(path=str(shots / f"{name}.png"), full_page=True)
                browser.close()
        finally:
            host.stop()
    return problems


if __name__ == "__main__":
    shots = Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
    found = run(shots)
    print("\n".join(found) or "Nothing scrolls sideways at 360 or 320.")
    sys.exit(1 if found else 0)
