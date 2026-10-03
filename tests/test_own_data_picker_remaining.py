from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def template(name):
    return (ROOT / "lightning/ui/templates" / name).read_text()


def test_remaining_own_data_selects_use_type_and_pick():
    expectations = {
        "bank_import_preview.html": [
            # One decision per name: the choices sit on the name, not on every row.
            'name="group_counterparty_choice_{{ i }}" data-own-picker',
            'name="group_category_{{ i }}" data-own-picker',
            'name="group_transfer_account_id_{{ i }}" data-own-picker',
            'name="group_owner_choice_{{ i }}" data-own-picker',
            'name="group_counterparty_{{ i }}" value="{{ g.counterparty }}" list=',
        ],
        "transactions/form_popup.html": [
            'name="to_account_id" data-own-picker',
            'name="category_id" data-own-picker',
            'name="owner_id" data-own-picker',
            'name="counterparty" value="{{ values.counterparty }}" list="popup-counterparties" data-own-suggestions',
        ],
        "transactions/detail.html": [
            'name="split_category_id" aria-label="Expense category" data-own-picker',
            'name="reserve_id" required aria-label="Reserve" data-own-picker',
        ],
        "investments/form.html": [
            'name="account_id" required data-own-picker',
            'name="asset_id" required data-own-picker',
            'name="cash_account_id" data-own-picker',
            'name="owner_id" data-own-picker',
        ],
        "physical_item_form.html": [
            'name="reference_asset_id" required data-karat-reference data-own-picker',
            'name="karat"',
        ],
        "physical_account.html": [
            'name="cash_account_id" required data-cash-for-trade data-own-picker',
            'name="owner" list="owners" data-own-suggestions',
        ],
        "counterparties.html": [
            'name="default_category_id" data-own-picker',
            'name="default_category_id" aria-label="Suggested category" data-submit-on-change data-own-picker',
        ],
        "register.html": [
            'name="account_id" required class=',
            'data-own-picker',
            'list="counterparty-options" data-own-suggestions',
        ],
    }
    for name, markers in expectations.items():
        source = template(name)
        for marker in markers:
            assert marker in source, f"{name} is missing {marker!r}"


def test_redundant_search_fields_are_removed_without_changing_submission_fields():
    source = template("bank_import_preview.html")
    assert "data-option-filter" not in source
    assert 'name="group_counterparty_choice_{{ i }}"' in source
    assert 'name="group_category_{{ i }}"' in source
    assert 'name="group_owner_choice_{{ i }}"' in source
    assert 'name="group_transfer_account_id_{{ i }}"' in source
    assert 'name="group_of_{{ rid }}"' in source

    popup = template("transactions/form_popup.html")
    assert "data-owner-filter" not in popup
    assert 'name="owner_id" data-own-picker' in popup

    investment = template("investments/form.html")
    assert "data-owner-filter" not in investment
    assert 'name="owner_id" data-own-picker' in investment


def test_dynamic_and_fixed_select_behavior_is_preserved():
    physical = template("physical_item_form.html")
    assert 'data-karat-reference data-own-picker' in physical
    assert 'option.disabled = !match' not in physical  # filtering remains in app.js

    trade = template("physical_account.html")
    assert 'data-cash-for-trade data-own-picker' in trade
    assert 'name="action"' in trade

    investment = template("investments/form.html")
    assert 'id="dividend-basis"' in investment
    assert 'name="dividend_basis" id="dividend-basis"' in investment

    item = template("physical_item_form.html")
    assert 'name="karat" data-own-picker' not in item
