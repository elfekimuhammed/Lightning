import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_own_data_fields_use_progressive_type_and_pick_enhancement():
    templates = [
        "lightning/ui/templates/register.html",
        "lightning/ui/templates/reserves.html",
        "lightning/ui/templates/planning/item_form.html",
        "lightning/ui/templates/planning/pay.html",
        "lightning/ui/templates/accounts/form.html",
    ]
    for template in templates:
        assert "data-own-picker" in (ROOT / template).read_text()

    app = (ROOT / "lightning/ui/static/app.js").read_text()
    assert 'root.matches?.(selector) ? [root] : []' in app
    assert 'find("select[data-own-picker]")' in app
    assert "initOwnDataPickers();" in app
    # Popup content is enhanced right after it is inserted (other set-up calls may sit in between).
    assert re.search(r"content\.innerHTML = html;(?:\n[^\n]*){0,3}?\n\s*initOwnDataPickers\(content\);", app)
    assert 'select.dataset.ownPickerReady' in app
    assert 'input.dataset.ownSuggestionsReady' in app
    assert 'setAttribute("role", "combobox")' in app
    assert 'setAttribute("role", "listbox")' in app
    assert 'select.dispatchEvent(new Event("change", { bubbles: true }))' in app
    assert 'input.autocomplete = "off"' in app
    assert 'input[data-own-suggestions][list]' in app
    assert '!el.hidden && !el.matches("[data-own-picker]")' in app


def test_fixed_enum_selects_are_not_marked_as_own_data():
    account_form = (ROOT / "lightning/ui/templates/accounts/form.html").read_text()
    planning_form = (ROOT / "lightning/ui/templates/planning/item_form.html").read_text()
    reserves = (ROOT / "lightning/ui/templates/reserves.html").read_text()

    assert 'id="account_type" name="account_type" data-groups' in account_form
    assert 'id="kind" name="kind"' in planning_form
    assert 'id="frequency" name="frequency"' in planning_form
    assert 'name="recurrence"' in reserves
    # Match by is a segment now (one choice, one field; owner, 2026-10-06), and never an own-data picker.
    assert 'type="radio" name="match_by"' in reserves and 'data-reserve-match' in reserves


def test_external_form_picker_input_keeps_form_validation_association():
    register = (ROOT / "lightning/ui/templates/register.html").read_text()
    app = (ROOT / "lightning/ui/static/app.js").read_text()

    assert 'select form="{{ form_id }}" name="account_id" required' in register
    assert 'if (select.hasAttribute("form")) input.setAttribute("form", select.getAttribute("form"));' in app
    assert 'input.setCustomValidity(select.value ? "" : "Choose an option from the list."); select.required = false;' in app
