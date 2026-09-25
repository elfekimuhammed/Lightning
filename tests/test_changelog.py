"""Every version must be logged in CHANGELOG.md."""

import re
from pathlib import Path

import lightning

ROOT = Path(__file__).resolve().parent.parent


def test_current_version_is_logged():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in text
    assert re.search(rf"^## \[{re.escape(lightning.__version__)}\] — \d{{4}}-\d{{2}}-\d{{2}}", text, re.M), (
        f"CHANGELOG.md has no entry for version {lightning.__version__}"
    )


def test_every_migration_is_logged():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for sql in (ROOT / "lightning" / "database" / "migrations").glob("*.sql"):
        assert sql.name in text, f"{sql.name} is not mentioned in CHANGELOG.md"
