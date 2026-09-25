from __future__ import annotations

from lightning.bank_imports import decode_csv
from lightning.transactions.domain import TxnSource


def test_parser_supports_utf8_bom_grouped_amounts_and_column_mapping():
    # Quoted thousands-grouped numbers are valid CSV values.
    data = "\ufeffWhen,Merchant,Net\n25/09/2026,Café,\"-1,200.50\"\n".encode()
    headers, rows = decode_csv(data)
    assert headers == ["When", "Merchant", "Net"]
    assert rows[0]["Net"] == "-1,200.50"


def test_import_stages_posts_and_same_file_is_idempotent(c, setup):
    accounts, cats = setup
    data = ("\ufeffDate,Counterparty,Amount,Category,Notes,Reference\n"
            "2026-09-20,Talabaat,-125,Food & Groceries,late meal,R-100\n").encode()
    batch_id, repeated = c.bank_imports.stage(accounts["cib"].id, "september.csv", data)
    assert not repeated
    batch, rows = c.bank_imports.preview(batch_id)
    row = rows[0]
    posted = c.bank_imports.confirm(batch_id, {row["_import_row_id"]: {
        "new_counterparty": "Talabat", "category_id": cats["EXP.PERSONAL.FOOD"].id
    }})
    assert posted["posted"] == 1 and posted["skipped"] == posted["duplicates"] == 0
    transaction = c.db.one("SELECT t.source,t.counterparty_id FROM transactions t JOIN bank_import_rows r "
                           "ON r.transaction_id=t.id WHERE r.batch_id=?", (batch_id,))
    assert transaction["source"] == TxnSource.IMPORT.value
    assert transaction["counterparty_id"] == c.counterparties.resolve("Talabaat")["id"]
    duplicate_batch, repeated = c.bank_imports.stage(accounts["cib"].id, "september.csv", data)
    assert duplicate_batch == batch_id and repeated
    assert c.reporting.account_balance(accounts["cib"].id) == 50000 - 125


def test_reference_duplicate_is_flagged_and_not_posted(c, setup):
    accounts, cats = setup
    first = b"Date,Counterparty,Amount,Category,Reference\n2026-09-20,Kiosk,-5,Food & Groceries,REF-X\n"
    first_id, _ = c.bank_imports.stage(accounts["cib"].id, "one.csv", first)
    _, first_rows = c.bank_imports.preview(first_id)
    c.bank_imports.confirm(first_id, {first_rows[0]["_import_row_id"]: {"category_id": cats["EXP.PERSONAL.FOOD"].id, "new_counterparty": "Kiosk"}})
    second = b"Date,Counterparty,Amount,Category,Reference\n2026-09-21,Kiosk,-6,Food & Groceries,REF-X\n"
    second_id, _ = c.bank_imports.stage(accounts["cib"].id, "two.csv", second)
    _, rows = c.bank_imports.preview(second_id)
    assert rows[0]["_reference_duplicate"]
    assert c.bank_imports.confirm(second_id, {rows[0]["_import_row_id"]: {}})["duplicates"] == 1
    assert c.reporting.account_balance(accounts["cib"].id) == 49995


def test_malformed_rows_are_previewed_and_can_be_skipped(c, setup):
    accounts, _ = setup
    data = b"Date,Counterparty,Amount\nnot-a-date,Shop,bad\n"
    batch_id, _ = c.bank_imports.stage(accounts["cib"].id, "broken.csv", data)
    _, rows = c.bank_imports.preview(batch_id)
    assert rows[0]["_errors"] and c.bank_imports.confirm(batch_id, {rows[0]["_import_row_id"]: {}})["skipped"] == 1


def test_ui_upload_review_and_post(c, setup):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    accounts, cats = setup
    client = TestClient(create_app(c))
    account_id = accounts["cib"].id
    csv = b"Date,Counterparty,Amount\n2026-09-22,Shop,-14\n"
    upload = client.post(f"/accounts/{account_id}/import", files={"file": ("month.csv", csv, "text/csv")}, follow_redirects=False)
    assert upload.status_code == 303
    preview = client.get(upload.headers["location"])
    assert preview.status_code == 200 and "Confirm and post selected rows" in preview.text
    batch_id = int(upload.headers["location"].rsplit("/", 1)[-1])
    _, rows = c.bank_imports.preview(batch_id)
    row_id = rows[0]["_import_row_id"]
    import hashlib
    group = hashlib.sha1(b"shop").hexdigest()[:12]
    posted = client.post(f"/accounts/{account_id}/import/{batch_id}/confirm", data={
        f"counterparty_{group}": "new", f"canonical_name_{group}": "Shop", f"category_{row_id}": str(cats["EXP.PERSONAL.FOOD"].id)
    }, follow_redirects=False)
    assert posted.status_code == 303 and "Import%20complete" in posted.headers["location"]
    assert c.reporting.account_balance(account_id) == 50000 - 14


def test_ui_requires_explicit_counterparty_for_unknown(c, setup):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    accounts, cats = setup
    client = TestClient(create_app(c))
    account_id = accounts["cib"].id
    csv = b"Date,Counterparty,Amount,Category\n2026-09-22,New Shop,-14,Food & Groceries\n"
    upload = client.post(f"/accounts/{account_id}/import", files={"file": ("m.csv", csv, "text/csv")}, follow_redirects=False)
    batch_id = int(upload.headers["location"].rsplit("/", 1)[-1])
    _, rows = c.bank_imports.preview(batch_id)
    row_id = rows[0]["_import_row_id"]
    import hashlib
    group = hashlib.sha1(b"new shop").hexdigest()[:12]
    response = client.post(f"/accounts/{account_id}/import/{batch_id}/confirm", data={
        f"counterparty_{group}": "", f"category_{row_id}": str(cats["EXP.PERSONAL.FOOD"].id)
    }, follow_redirects=False)
    assert response.status_code == 400 and "Choose or create one Counterparty" in response.text
    assert c.db.scalar("SELECT COUNT(*) FROM transactions WHERE source='IMPORT'") == 0


def test_ui_maps_nonstandard_headers_once_and_can_reverse_sign(c, setup):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    accounts, _ = setup
    client = TestClient(create_app(c))
    account_id = accounts["cib"].id
    first = b"When,Merchant,Net\n25/09/2026,Shop,14\n"
    response = client.post(f"/accounts/{account_id}/import", files={"file": ("sep.csv", first, "text/csv")}, follow_redirects=False)
    assert response.status_code == 200 and "Match your columns" in response.text
    import re
    payload = re.search(r'name="payload" value="([^"]+)"', response.text).group(1)
    mapped = client.post(f"/accounts/{account_id}/import/map", data={
        "payload": payload, "filename": "sep.csv", "map_Date": "When",
        "map_Counterparty": "Merchant", "map_Amount": "Net", "amount_sign": "invert"
    }, follow_redirects=False)
    assert mapped.status_code == 303
    batch_id = int(mapped.headers["location"].rsplit("/", 1)[-1])
    _, rows = c.bank_imports.preview(batch_id)
    assert rows[0]["Date"] == "2026-09-25" and rows[0]["Amount"] == "-14"
    second = b"When,Merchant,Net\n26/09/2026,Shop,22\n"
    auto = client.post(f"/accounts/{account_id}/import", files={"file": ("oct.csv", second, "text/csv")}, follow_redirects=False)
    assert auto.status_code == 303 and "/import/map" not in auto.headers["location"]
    second_id = int(auto.headers["location"].rsplit("/", 1)[-1])
    _, rows = c.bank_imports.preview(second_id)
    assert rows[0]["Date"] == "2026-09-26" and rows[0]["Amount"] == "-22"
