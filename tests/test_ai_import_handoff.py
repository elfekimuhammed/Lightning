from fastapi.testclient import TestClient

from lightning.ui.web import create_app


def test_import_page_explains_supported_schema_and_explicit_downloads(c, setup):
    accounts, cats = setup
    c.counterparties.create("Prompt Test Merchant")
    client = TestClient(create_app(c))

    page = client.get(f"/accounts/{accounts['cib'].id}/import")
    assert page.status_code == 200
    assert "Date,Amount" in page.text
    assert "Date,Inflow,Outflow" in page.text
    assert "do not invent matches" in page.text
    assert "leave unknown or ambiguous categories blank" in page.text.lower()
    assert "Copy prompt" in page.text
    assert "ai-handoff.js" in page.text

    reference = client.get(f"/accounts/{accounts['cib'].id}/import/ai-reference.json")
    assert reference.status_code == 200
    assert "attachment" in reference.headers["content-disposition"]
    body = reference.json()
    assert body["account"] == accounts["cib"].name
    assert body["currency"] == accounts["cib"].currency
    assert "Prompt Test Merchant" in body["counterparties"]
    assert any(item["id"] == cats["EXP.PERSONAL.FOOD"].id for item in body["categories"])

    template = client.get(f"/accounts/{accounts['cib'].id}/import/ai-template.csv")
    assert template.status_code == 200
    assert "attachment" in template.headers["content-disposition"]
    assert template.text == "Date,Amount,Counterparty,Category,Notes,Reference\r\n"


def test_ai_handoff_downloads_are_scoped_to_valid_account(c, setup):
    client = TestClient(create_app(c))
    for url in ("/accounts/999/import/ai-reference.json", "/accounts/999/import/ai-template.csv"):
        assert client.get(url).status_code == 404
