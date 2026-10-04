"""The docs stay cheap to read: the rules in AGENTS.md section 2, checked so they cannot drift."""

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _guideline_tool():
    spec = importlib.util.spec_from_file_location("guideline", ROOT / "tools" / "guideline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_hand_off_is_short_and_has_its_parts():
    text = (ROOT / "NOW.md").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 6000, "NOW.md must stay under 6,000 bytes: move finished work to CHANGELOG.md"
    for heading in ("## Claude", "## Codex", "## Next", "## For the owner"):
        assert re.search(rf"^{re.escape(heading)}", text, re.M), f"NOW.md lost its {heading!r} part"
    overview = (DOCS / "PROJECT_OVERVIEW.md").read_text(encoding="utf-8")
    assert "## Now and next" not in overview, "the hand-off lives in NOW.md only"


def test_docs_holds_only_the_carrying_files_and_proposals():
    allowed = {"PROJECT_OVERVIEW.md", "ARCHITECTURE.md", "GLOSSARY.md", "BRAND_GUIDELINE.html", "proposals"}
    extra = {path.name for path in DOCS.iterdir()} - allowed
    assert not extra, f"new files under docs/ (AGENTS.md section 1): {sorted(extra)}"
    assert all(path.suffix == ".md" for path in (DOCS / "proposals").iterdir())


def test_every_long_doc_lists_all_its_sections():
    for name in ("PROJECT_OVERVIEW.md", "ARCHITECTURE.md", "GLOSSARY.md"):
        text = (DOCS / name).read_text(encoding="utf-8")
        contents = text.split("## Contents", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"^\| ([^|]+?) \|", contents, re.M)) - {"Section"}
        headings = set(re.findall(r"^## (.+)$", text, re.M)) - {"Contents"}
        assert headings == listed, f"{name}: Contents and headings differ: {sorted(headings ^ listed)}"


def test_unreleased_comes_first_newest_first():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", text, re.M)[0] == "[Unreleased]"
    unreleased = text.split("\n## [Unreleased]\n", 1)[1].split("\n## ", 1)[0]
    dates = re.findall(r"^- (\d{4}-\d{2}-\d{2}) ·", unreleased, re.M)
    assert dates == sorted(dates, reverse=True), "add new changelog entries at the top of Unreleased"


def test_agents_md_carries_the_guidelines_a16_checklist():
    tool = _guideline_tool()
    html = (DOCS / "BRAND_GUIDELINE.html").read_text(encoding="utf-8")
    section = next(block for number, _, block in tool.sections(html) if number == "A16")
    items = re.findall(r"<div><b>([^<]+)</b>([^<]+)</div>", section)
    assert len(items) >= 10, "could not read A16's items; update this test with the guideline's markup"
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    checklist = agents.split("**Before it ships (guideline A16).**", 1)[1].split("\n", 1)[0]
    missing = [f"{name}: {rule}" for name, rule in items if f"{name}: {rule}" not in checklist]
    assert not missing, f"AGENTS.md's A16 list is missing: {missing}"


def test_the_guideline_tool_prints_one_section_as_text():
    tool = _guideline_tool()
    html = (DOCS / "BRAND_GUIDELINE.html").read_text(encoding="utf-8")
    found = tool.sections(html)
    assert [n for n, _, _ in found if n.startswith("A")][-1] == "A16"
    a16 = tool.as_text(next(block for number, _, block in found if number == "A16"))
    assert "Before it ships" in a16 and "<" not in a16 and len(a16) < 2000
