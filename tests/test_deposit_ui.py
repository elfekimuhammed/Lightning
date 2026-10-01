from datetime import date

from fastapi.testclient import TestClient

from lightning.core.errors import NotFoundError
from lightning.ui.web import create_app


class DepositStub:
    def __init__(self):
        self.terms = {}
        self.saved = None

    def get(self, account_id):
        if account_id not in self.terms:
            raise NotFoundError("Deposit terms not found.")
        return self.terms[account_id]

    def save(self, *args, **kwargs):
        self.saved = (args, kwargs)
        account_id = args[0]
        self.terms[account_id] = {
            "start_date": args[1], "maturity_date": args[2], "principal": args[3],
            "annual_rate": args[4], "interest_method": args[5], "payout_frequency": args[6],
            "destination_account_id": args[7], **kwargs,
        }

    def delete(self, account_id):
        self.terms.pop(account_id, None)


def _terms(cd, destination, **overrides):
    values = {
        "start_date": "2026-09-01", "maturity_date": "2027-09-01", "lockup_end_date": "2027-03-01",
        "principal": "5000", "annual_rate": "12.5", "interest_method": "SIMPLE",
        "compounding_frequency": "MONTHLY", "payout_frequency": "MONTHLY",
        "destination_account_id": str(destination.id),
    }
    return values | overrides


def test_cd_terms_link_and_form_save_separate_compounding_frequency(c, setup):
    accounts, _ = setup
    cd, bank = accounts["cd"], accounts["cib"]
    c.deposits = DepositStub()
    client = TestClient(create_app(c), follow_redirects=False)

    listing = client.get("/accounts")
    assert f'href="/deposits/{cd.id}"' in listing.text
    page = client.get(f"/deposits/{cd.id}")
    assert page.status_code == 200
    assert "Earliest withdrawal date" in page.text
    assert "Compounding frequency" in page.text and "Payout schedule" in page.text
    assert 'name="destination_account_id" data-own-picker' in page.text
    before_transactions = c.transactions.count_for_account(cd.id)
    assert "not create cash in the forecast" in page.text

    response = client.post(f"/deposits/{cd.id}", data=_terms(cd, bank, interest_method="COMPOUND",
                            compounding_frequency="QUARTERLY", payout_frequency="AT_MATURITY",
                            lockup_end_date=""))
    assert response.status_code == 303
    args, kwargs = c.deposits.saved
    assert args[5:8] == ("COMPOUND", "AT_MATURITY", bank.id)
    assert kwargs == {"lockup_end_date": "2027-09-01", "compounding_frequency": "QUARTERLY"}
    assert c.transactions.count_for_account(cd.id) == before_transactions


def test_compound_payout_and_dates_are_validated_server_side(c, setup):
    accounts, _ = setup
    cd, bank = accounts["cd"], accounts["cib"]
    c.deposits = DepositStub()
    client = TestClient(create_app(c), follow_redirects=False)

    response = client.post(f"/deposits/{cd.id}", data=_terms(cd, bank, interest_method="COMPOUND",
                            payout_frequency="MONTHLY"))
    assert response.status_code == 400 and "Compound interest is paid at maturity only." in response.text
    assert c.deposits.saved is None

    response = client.post(f"/deposits/{cd.id}", data=_terms(cd, bank, lockup_end_date="2027-10-01"))
    assert response.status_code == 400 and "between the start and maturity dates" in response.text


def test_lockup_status_estimate_and_maturity_use_cd_sale_factor(c, setup, monkeypatch):
    accounts, _ = setup
    cd = accounts["cd"]
    c.deposits = DepositStub()
    c.deposits.terms[cd.id] = {
        "start_date": "2026-09-01", "maturity_date": "2027-09-01", "lockup_end_date": "2027-03-01",
        "principal": "5000", "annual_rate": "12", "interest_method": "SIMPLE",
        "compounding_frequency": "MONTHLY", "payout_frequency": "MONTHLY",
        "destination_account_id": str(accounts["cib"].id),
    }
    client = TestClient(create_app(c), follow_redirects=False)
    page = client.get(f"/deposits/{cd.id}")
    assert "Not withdrawable yet." in page.text

    from lightning.ui.routes import deposits
    monkeypatch.setattr(deposits, "today", lambda: date(2027, 4, 1))
    page = client.get(f"/deposits/{cd.id}")
    assert "Early proceeds estimate" in page.text
    assert "95% class-wide CD sale factor" in page.text
    assert "not a guaranteed bank quote" in page.text

    monkeypatch.setattr(deposits, "today", lambda: date(2027, 9, 1))
    page = client.get(f"/deposits/{cd.id}")
    assert "At maturity:" in page.text and "5,000.00 EGP" in page.text
