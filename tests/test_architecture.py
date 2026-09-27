"""Architecture rules from pyproject.toml, enforced as a test."""

import ast
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("lint-imports") is None, reason="import-linter not installed")
def test_import_contracts():
    result = subprocess.run(["lint-imports"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_float_money_in_financial_code():
    """Financial modules must never construct floats."""
    for folder in ("core", "accounts", "transactions", "reporting", "workflows"):
        for path in (ROOT / "lightning" / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "float(" not in text, f"{path} uses float()"


def test_ui_contains_no_sql():
    for path in (ROOT / "lightning" / "ui").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            text = node.value.lstrip()
            if re.match(r"(?is)^(SELECT\b.*\bFROM\b|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b)", text):
                raise AssertionError(f"SQL literal in UI route: {path}:{node.lineno}")
