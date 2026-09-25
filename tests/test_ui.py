"""The HTML UI end to end: every page renders, forms create real records."""

import re

import pytest
from fastapi.testclient import TestClient

from lightning.ui.web import create_app


@pytest.fixture
def client(c):
    return TestClient(create_app(c))


def test_welcome_then_first_account(client, c):
    r = client.get("/")
    assert r.status_code == 200 and "Let's start with your accounts" in r.text
    r = client.post("/accounts/new", data={"name": "CIB Current", "institution": "CIB", "account_type": "BANK",
                                           "opening_date": "2026-09-01", "opening_balance": "50,000"})
    assert r.status_code == 200 and "CIB-CUR-EGP · CIB Current" in r.text
    r = client.get("/")
    assert "Net worth" in r.text and "50,000.00" in r.text


def test_full_flow(client, c):
    client.post("/accounts/new", data={"name": "CIB Current", "account_type": "BANK", "institution": "CIB",
                                       "opening_date": "2026-09-01", "opening_balance": "50000"})
    client.post("/accounts/new", data={"name": "Wallet", "account_type": "CASH",
                                       "opening_date": "2026-09-01", "opening_balance": "1000"})
    cib = c.accounts.get_by_code("CIB-CUR-EGP")
    wallet = c.accounts.get_by_code("WALLET-CSH-EGP")
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD")

    # the sidebar lists every account with its balance
    page = client.get(f"/accounts/{cib.id}")
    assert "All accounts" in page.text and "51,000.00" in page.text and "CIB-CUR-EGP" in page.text

    r = client.post(f"/accounts/{cib.id}/register", data={"date": "2026-09-25", "to": "Carrefour",
                    "category": "Personal › Food & Groceries", "amount": "-450", "notes": "Groceries"})
    assert r.status_code == 200 and "Saved OUT-2026-09-25-001" in r.text
    txn = c.transactions.get_by_ref("OUT-2026-09-25-001")

    # one of your accounts in To = a transfer (no category needed)
    r = client.post(f"/accounts/{cib.id}/register", data={"date": "2026-09-26", "to": "Wallet", "amount": "-2000"})
    assert "Saved TRF-2026-09-26-001" in r.text

    # validation errors re-render the register with the message and the typed values
    r = client.post(f"/accounts/{cib.id}/register", data={"date": "26/09/2026", "category": "food & groceries",
                    "amount": "-12"})
    assert r.status_code == 400 and "yyyy-mm-dd" in r.text and 'value="-12"' in r.text

    # search inside the register
    r = client.get(f"/accounts/{cib.id}?q=carrefour")
    assert "Carrefour" in r.text and 'class="pill transfer"' not in r.text

    # edit in place: the row becomes a form, saving keeps the ref
    r = client.get(f"/accounts/{cib.id}?edit={txn.id}&acct={cib.id}")
    assert 'id="f-edit"' in r.text and 'value="-450.00"' in r.text
    r = client.post(f"/accounts/{cib.id}/register/{txn.id}", data={"date": "2026-09-25", "to": "Carrefour",
                    "category": "Personal › Food & Groceries", "amount": "-540", "notes": ""})
    assert "Saved OUT-2026-09-25-001" in r.text
    assert c.reporting.account_balance(cib.id) == 50000 - 540 - 2000

    # void from the edit bar returns to the register
    r = client.post(f"/transactions/{txn.id}/void?back=/accounts/{cib.id}")
    assert "is void" in r.text and r.url.path == f"/accounts/{cib.id}"
    r = client.post(f"/transactions/{txn.id}/restore")
    assert "restored" in r.text

    r = client.get("/?month=2026-09")
    assert "Checks out to 0.00" in r.text

    r = client.post(f"/accounts/{wallet.id}/deactivate")
    assert "Move the balance" in r.text

    assert client.get("/t/OUT-2026-09-25-001", follow_redirects=False).status_code == 303


def test_all_accounts_register(client, c, setup):
    accounts, cats = setup
    wallet, cib = accounts["wallet"], accounts["cib"]
    r = client.post("/transactions/register", data={"date": "2026-09-20", "account_id": wallet.id, "to": "Kiosk",
                    "category": "Food & Groceries", "amount": "-30"})
    assert "Saved OUT-2026-09-20-001" in r.text
    t = client.post("/transactions/register", data={"date": "2026-09-21", "account_id": cib.id,
                    "to": wallet.label, "amount": "-100"})
    assert "Saved TRF" in t.text
    page = client.get("/transactions")
    assert page.text.count('class="pill transfer"') == 2  # one row per account
    r = client.post("/transactions/register", data={"date": "2026-09-21", "to": "Wallet", "amount": "-100"})
    assert r.status_code == 400 and "Choose an account" in r.text


def test_edit_changing_kind_replaces_transaction(client, c, setup):
    accounts, cats = setup
    w, cib = accounts["wallet"], accounts["cib"]
    txn = c.transactions.record_transfer("2026-09-10", cib.id, w.id, "100")
    r = client.post(f"/accounts/{w.id}/register/{txn.id}", data={"date": "2026-09-10", "to": "Kiosk",
                    "category": "Food & Groceries", "amount": "-100"})
    assert "Saved OUT-2026-09-10-001" in r.text
    assert c.transactions.get(txn.id).is_void
    assert c.reporting.account_balance(w.id) == 1100


@pytest.mark.parametrize("path", ["/", "/accounts", "/accounts/new", "/transactions", "/transactions?q=x&month=2026-09",
                                  "/accounts/1", "/accounts/1?month=2026-09", "/categories", "/settings",
                                  "/categories/new?parent=1", "/transactions/1"])
def test_pages_render(client, setup, path):
    assert client.get(path).status_code == 200


def test_not_found(client):
    assert client.get("/accounts/999").status_code == 404
    assert client.get("/t/OUT-2000-01-01-001").status_code == 404


def test_category_pages(client, c):
    personal = c.categories.get_by_code("EXP.PERSONAL")
    r = client.post(f"/categories/new?parent={personal.id}", data={"name": "Pets", "code": ""})
    assert "Added Personal › Pets" in r.text
    pets = c.categories.get_by_code("EXP.PERSONAL.PETS")
    r = client.post(f"/categories/{pets.id}/edit", data={"name": "Pets & Vet", "code": "PETS", "active": "1"})
    assert "Category saved" in r.text and c.categories.get(pets.id).name == "Pets & Vet"


def test_backup_button(client):
    r = client.post("/settings/backup")
    assert "Backup saved as lightning_" in r.text


def test_register_entry(client, c, setup):
    accounts, cats = setup
    wallet, cib = accounts["wallet"], accounts["cib"]
    page = client.get(f"/accounts/{wallet.id}")
    assert 'action="/accounts/%d/register"' % wallet.id in page.text
    assert 'list="category-options"' in page.text and "<select form=\"f-new\" name=\"choice\"" not in page.text
    assert "Payee" not in page.text and ">To<" in page.text
    assert "EXP.PERSONAL" not in page.text  # plain names only

    r = client.post(f"/accounts/{wallet.id}/register", data={"date": "2026-09-20", "to": "Carrefour",
                    "category": "Personal › Food & Groceries", "amount": "-150", "notes": "milk"})
    assert "Saved OUT-2026-09-20-001" in r.text and "Personal › Food &amp; Groceries" in r.text
    assert c.reporting.account_balance(wallet.id) == 1200 - 150

    r = client.post(f"/accounts/{wallet.id}/register", data={"date": "2026-09-21", "to": "CIB Current",
                    "amount": "500"})
    assert "Saved TRF-2026-09-21-001" in r.text
    assert c.reporting.account_balance(wallet.id) == 1200 - 150 + 500
    assert c.reporting.account_balance(cib.id) == 50000 - 500

    # wrong sign for the category -> friendly error, typed values kept
    r = client.post(f"/accounts/{wallet.id}/register", data={"date": "2026-09-22", "to": "Employer",
                    "category": "Salary", "amount": "-99"})
    assert r.status_code == 400 and "make the amount positive" in r.text and 'value="-99"' in r.text

    # an ambiguous category name asks which one
    r = client.post(f"/accounts/{wallet.id}/register", data={"date": "2026-09-22", "category": "Transportation",
                    "amount": "-10"})
    assert r.status_code == 400 and "Which one" in r.text

    # a transfer to the same account is refused
    r = client.post(f"/accounts/{wallet.id}/register", data={"date": "2026-09-22", "to": "Wallet", "amount": "-1"})
    assert r.status_code == 400 and "same account" in r.text

    # To remembers its category
    page = client.get(f"/accounts/{wallet.id}")
    assert "Carrefour" in page.text and "Personal › Food &amp; Groceries" in page.text


def test_account_form_has_no_class_picker(client):
    r = client.get("/accounts/new")
    assert "cash_class_code" not in r.text and "Liquid Cash › Bank Balance" in r.text
    assert "Credit card" not in r.text and "Loan" not in r.text


def test_categories_page_is_plain(client):
    r = client.get("/categories")
    assert "Food &amp; Groceries" in r.text and "EXP.PERSONAL.FOOD" not in r.text
