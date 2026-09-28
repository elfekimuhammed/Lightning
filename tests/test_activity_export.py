import csv
import io
from decimal import Decimal

from fastapi.testclient import TestClient

from lightning.ui.web import create_app


def _rows(response):
    assert response.status_code == 200
    assert 'attachment' in response.headers['content-disposition']
    return list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))


def test_activity_export_filters_and_preserves_precise_amounts(c, setup):
    accounts, cats = setup
    bank = accounts['cib']
    txn = c.transactions.record_outflow('2026-09-15', bank.id, '123.45',
        cats['EXP.PERSONAL.FOOD'].id, counterparty='متجر, groceries', notes='=danger')
    client = TestClient(create_app(c))
    rows = _rows(client.get(f'/accounts/{bank.id}?export=csv&date_from=2026-09-15&date_to=2026-09-15'))
    assert len(rows) == 1
    assert rows[0]['Transaction ID'] == str(txn.id)
    assert Decimal(rows[0]['Amount']) == Decimal('-123.45')
    assert rows[0]['Currency'] == 'EGP'
    assert rows[0]['Counterparty'] == 'متجر, groceries'
    assert rows[0]['Notes'] == "'=danger"
    category_rows = _rows(client.get(f'/transactions?export=csv&category_id={cats["EXP.PERSONAL.FOOD"].id}'))
    assert [r['Transaction ID'] for r in category_rows] == [str(txn.id)]
    assert _rows(client.get(f'/accounts/{bank.id}?export=csv&q=nomatch')) == []
    assert client.get('/transactions?export=csv&date_from=bad').status_code == 400


def test_activity_export_identifies_both_sides_of_transfer(c, setup):
    accounts, _ = setup
    txn = c.transactions.record_transfer('2026-09-16', accounts['cib'].id, accounts['wallet'].id, '50')
    rows = _rows(TestClient(create_app(c)).get('/transactions?export=csv&date_from=2026-09-16&date_to=2026-09-16'))
    assert len(rows) == 2
    assert {r['Transaction ID'] for r in rows} == {str(txn.id)}
    assert {r['Type'] for r in rows} == {'TRF'}
    assert sum(Decimal(r['Amount']) for r in rows) == 0
    assert all(r['Other account ID'] for r in rows)
