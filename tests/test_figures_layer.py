"""The figures layer stays in one place (Architecture › Figures layer): services compute, the drawing
code only draws. These checks fail when a page starts reading the ledger or doing money arithmetic
on its own, which is how two screens end up showing two numbers for one figure."""
import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "lightning" / "ui"


def test_the_drawing_code_never_reads_the_ledger():
    for path in (UI / "visuals.py", UI / "charts.py", UI / "keynotes.py"):
        text = path.read_text()
        assert not re.search(r"\.db\.|\.q\.|from_e6|to_e6|_e6\b", text), path.name


def test_routes_read_figures_from_services_not_the_database():
    for path in (UI / "routes").glob("*.py"):
        text = path.read_text()
        reads = re.findall(r"\.db\.(?:all|one|scalar|execute)\(|\.q\.\w+\(", text)
        assert not reads, f"{path.name} reads the database directly: {reads}"


def test_every_money_path_uses_the_one_rule():
    service = (UI.parent / "reporting" / "service.py").read_text()
    for name in ("cash_flow", "flows_by_date", "_money_out_by_category", "money_in_by_category",
                 "spending_by_category", "_spending"):
        body = service.split(f"    def {name}(", 1)[1].split("\n    def ", 1)[0]
        assert "flow_of(" in body, name
