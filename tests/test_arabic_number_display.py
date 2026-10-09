from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "lightning/ui/static/arabic-numbers.js"


def test_arabic_number_display_script_is_loaded_in_both_shared_shells():
    for template in ("base.html", "phone/base.html"):
        source = (ROOT / "lightning/ui/templates" / template).read_text(encoding="utf-8")
        assert "/static/arabic-numbers.js?v=1" in source


def test_arabic_display_localizes_numeric_tokens_but_keeps_identifiers():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable for the browser display helper test")
    result = subprocess.run(
        [node, "-e", "const {localizeNumericText:f}=require(process.argv[1]); process.stdout.write(f(process.argv[2]));",
         str(SCRIPT), "المتاح 12,345.67 ج.م · 2026-10-09 · 25% · TXN-2026-001 · V1.0.0-beta.1 · 9.7k"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert result == "المتاح ١٢٬٣٤٥٫٦٧ ج.م · ٢٠٢٦-١٠-٠٩ · ٢٥% · TXN-2026-001 · V1.0.0-beta.1 · ٩٫٧k"
