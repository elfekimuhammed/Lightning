"""Exports Lightning's phone screens for Figma: PNGs (390 wide, 2x), self-contained HTML (for the html.to.design
plugin), and the design tokens (Tokens Studio JSON). Runs the app on dummy data (Mohab's sample household).

    python figma-export/export_screens.py <out folder>
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LIGHTNING_THEME_REVIEW"] = "1"

SCREENS = (
    ("04-home", "/home"), ("06-add", "/accounts/add-transaction?return_to=/home"),
    ("07-transaction", "/transactions/10/sheet?return_to=/activity"),
    ("09-budget-categories", "/budget"), ("10-budget-spending", "/budget?view=spending"), ("11-budget-edit-plan", "/budget/plan"),
    ("12-one-category", "/budget/category/5/sheet"),
    ("13-plan-coming-up", "/plan"), ("14-plan-recurring", "/plan/recurring"), ("15-plan-loans", "/plan/loans"),
    ("16-plan-reserves", "/plan/reserves"),
    ("17-money", "/money"), ("18-activity", "/activity"), ("19-to-review", "/activity?tab=review"),
    ("20-investments", "/investments"), ("21-one-account", "/accounts/1"), ("22-settings", "/settings"),
)
THEMED = ("04-home", "09-budget-categories", "13-plan-coming-up", "17-money")
THEMES = ("dendera", "royal-obsidian-gold")

INLINE = """async () => {
  const take = async (url, type) => { const r = await fetch(url); return type === 'text' ? r.text() : r.arrayBuffer(); };
  const b64 = (buf) => { let s = ''; const b = new Uint8Array(buf); for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000)); return btoa(s); };
  for (const link of [...document.querySelectorAll('link[rel=stylesheet]')]) {
    let css = await take(link.href, 'text');
    const base = new URL(link.href);
    for (const m of [...css.matchAll(/url\\(["']?([^)"']+\\.woff2[^)"']*)["']?\\)/g)]) {
      const data = b64(await take(new URL(m[1], base).href, 'buf'));
      css = css.split(m[0]).join('url(data:font/woff2;base64,' + data + ')');
    }
    const style = document.createElement('style'); style.textContent = css; link.replaceWith(style);
  }
  for (const img of document.querySelectorAll('img[src^="/"]')) {
    const r = await fetch(img.src); const type = r.headers.get('content-type') || 'image/svg+xml';
    img.src = 'data:' + type + ';base64,' + b64(await r.arrayBuffer());
  }
  document.querySelectorAll('script').forEach(s => s.remove());
  return '<!doctype html>' + document.documentElement.outerHTML;
}"""

TOKENS = """() => {
  const out = {};
  const grab = (rule) => { for (const i of rule.style) if (i.startsWith('--')) (out[rule.selectorText] ||= {})[i] = rule.style.getPropertyValue(i).trim(); };
  for (const sheet of document.styleSheets) { try { for (const rule of sheet.cssRules) {
    if (rule.selectorText && (rule.selectorText === ':root' || /^html\\[data-theme="[a-z-]+"\\]$/.test(rule.selectorText))) grab(rule); } } catch (e) {} }
  return out;
}"""


def main(out: Path) -> None:
    from playwright.sync_api import sync_playwright
    from lightning.runtime.app import profile_app
    from lightning.runtime.devices import Devices
    from lightning.runtime.http import Host

    for sub in ("png/en", "png/ar", "png/themes", "html/en", "html/ar", "html/themes", "tokens", "brand"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        host = Host(lambda c: profile_app(c, root / "docs", devices=Devices(root / "app", port=0), phone=True)).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)

                def shoot(name: str, folder_: str) -> None:
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(out / "png" / folder_ / f"{name}.png"), full_page=True)
                    (out / "html" / folder_ / f"{name}.html").write_text(page.evaluate(INLINE), encoding="utf-8")

                def post(path: str, **fields) -> None:
                    page.evaluate("""async ([path, fields]) => { const t = document.querySelector('meta[name=lightning-session]').content;
                        await fetch(path, {method: 'POST', body: new URLSearchParams({__session: t, ...fields})}); }""", [path, fields])

                page.goto(host.launch_url)
                shoot("01-welcome", "en")
                page.goto(host.origin + "/profiles/new")
                shoot("02-your-profile", "en")
                page.fill("input[name=name]", "Mohab")
                for field in ("password", "confirm"):
                    page.fill(f"input[name={field}]", "a dummy phone password")
                page.fill("input[name=answer]", "Dummy")
                if page.locator("select[name=question]").count():
                    page.select_option("select[name=question]", index=1)
                elif page.locator("input[name=question]").count():
                    page.fill("input[name=question]", "Dummy question?")
                page.click("form[action='/profiles/new'] button[type=submit]")
                key = re.search(r"\d{4}-\d{4}-\d{4}", page.content()).group(0)
                shoot("03-recovery-key", "en")
                if page.locator("form[action='/profiles/confirm'] input[name=recovery][type=text]").count():
                    page.fill("input[name=recovery]", key)
                page.click("form[action='/profiles/confirm'] button[type=submit]")
                page.goto(host.origin + "/home")
                shoot("05-home-first-day", "en")
                page.goto(host.origin + "/")
                post("/demo")
                for locale, folder_ in (("en", "en"), ("ar", "ar")):
                    page.goto(host.origin + "/money")
                    post("/settings/locale", locale=locale)
                    for name, path in SCREENS:
                        page.goto(host.origin + path)
                        shoot(name, folder_)
                page.goto(host.origin + "/money")
                post("/settings/locale", locale="en")
                page.goto(host.origin + "/home")
                tokens = {"default": page.evaluate(TOKENS)}
                for theme in THEMES:
                    page.goto(host.origin + "/money")
                    post("/settings/theme", theme=theme)
                    for name in THEMED:
                        page.goto(host.origin + dict(SCREENS)[name])
                        shoot(f"{name}-{theme}", "themes")
                    page.goto(host.origin + "/home")
                    tokens[theme] = page.evaluate(TOKENS)
                browser.close()
        finally:
            host.stop()
    (out / "tokens" / "raw-css-variables.json").write_text(json.dumps(tokens, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
