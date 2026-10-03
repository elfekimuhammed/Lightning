"""Regression coverage for transient accessible status messages and register layout."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_server_rendered_messages_have_live_region_semantics():
    template = (ROOT / "lightning/ui/templates/base.html").read_text(encoding="utf-8")

    assert 'class="flash" role="status" aria-live="polite" aria-atomic="true">{{ msg }}' in template
    assert 'class="flash error" role="alert" aria-live="assertive" aria-atomic="true">{{ error }}' in template


def test_flash_behavior_covers_errors_popups_and_late_insertions():
    app_js = (ROOT / "lightning/ui/static/app.js").read_text(encoding="utf-8")
    stylesheet = (ROOT / "lightning/ui/static/style.css").read_text(encoding="utf-8")

    assert 'isError ? "alert" : "status"' in app_js
    assert 'isError ? "assertive" : "polite"' in app_js
    assert "}, 5000));" in app_js
    assert "new MutationObserver" in app_js and "characterData: true" in app_js
    assert 'flashObserver.observe(popupFlashRoot,' in app_js
    assert 'flashObserver.observe(document.body' not in app_js
    assert "initFlashMessages(content, true)" in app_js  # popup responses, including validation errors
    assert "initFlashMessages(flash, true)" in app_js  # message restored after a popup save
    assert ".flash.error { background: var(--rose-soft); color: var(--ink); }" in stylesheet
    assert "@media(prefers-reduced-motion:reduce)" in stylesheet


def test_register_keeps_balance_inside_a_horizontally_scrollable_table():
    register = (ROOT / "lightning/ui/templates/register.html").read_text(encoding="utf-8")
    stylesheet = (ROOT / "lightning/ui/static/style.css").read_text(encoding="utf-8")

    assert '<div class="register-table-scroll"><table>' in register
    scroll_rule = re.search(r"\.main \.register-table-scroll\s*\{([^}]*)\}", stylesheet)
    table_rule = re.search(r"\.main \.register-table-scroll\s*>\s*table\s*\{([^}]*)\}", stylesheet)
    number_rule = re.search(r"\.num\s*\{([^}]*)\}", stylesheet)
    assert scroll_rule and "overflow-x:auto" in scroll_rule.group(1)
    assert table_rule and "min-width:1120px" in table_rule.group(1)
    assert number_rule and "white-space: nowrap" in number_rule.group(1)
