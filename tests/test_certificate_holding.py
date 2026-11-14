"""IV-12J: a certificate reads as a certificate. Its own holding page (PC and phone) in the bank's words, a value that
grows as interest is earned when the bank pays at maturity, and dated rate changes for a variable certificate."""
from __future__ import annotations

import html
import re
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lightning.deposits import schedule
from lightning.ui.web import create_app

STOCK_WORDS = re.compile(r"\b(price|units?|average cost|unrealized|buy more)\b", re.I)


def _client(c, phone=False, locale="en"):
    app = create_app(c)
    if phone:
        inner = app

        async def phone_app(scope, receive, send):
            if scope["type"] == "http":
                scope.setdefault("state", {})["phone"] = True
            await inner(scope, receive, send)
        app = phone_app
    client = TestClient(app, follow_redirects=False)
    if locale != "en":
        assert client.post("/settings/locale", data={"locale": locale}).status_code == 303
    return client


def _text(page: str) -> str:
    body = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", page)
    body = re.sub(r"(?s)<nav\b.*?</nav>", " ", body)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def _monthly(c, accounts, **overrides):
    args = dict(name="CIB 3-year certificate", start_date="2026-09-01", lockup_end_date="2027-03-01",
                maturity_date="2029-09-01", principal="12000", annual_rate="20", interest_method="SIMPLE",
                payout_frequency="MONTHLY", compounding_frequency="MONTHLY",
                destination_account_id=accounts["cib"].id, funding_account_id=accounts["cib"].id)
    args.update(overrides)
    certificate, _ = c.deposits.purchase(accounts["cd"].id, **args)
    return certificate


def _compound(c, accounts):
    return _monthly(c, accounts, name="CIB compound certificate", principal="10000", annual_rate="24",
                    interest_method="COMPOUND", payout_frequency="AT_MATURITY", compounding_frequency="YEARLY",
                    lockup_end_date="2026-09-01", maturity_date="2028-09-01")


@pytest.mark.parametrize("phone", [False, True])
def test_the_certificate_page_speaks_of_rate_payouts_and_maturity_not_prices(c, setup, phone):
    accounts, cats = setup
    certificate = _monthly(c, accounts)
    # Three monthly payouts of 200 reached CIB from the bank: the October one is missing.
    for day in ("2026-11-01", "2026-12-01"):
        c.transactions.record_inflow(day, accounts["cib"].id, "200", cats["EXP.INVEST.INTEREST"].id,
                                     counterparty="CIB")

    page = _client(c, phone).get(f"/investments/holding/{certificate.terms.asset_id}")

    assert page.status_code == 200, page.text[:400]
    text = _text(page.text)
    for words in ("20% a year", "Interest paid monthly", 
                  "Its terms expected 600 by now", "Next payment", "1 Jan 2027", "in 1 day",
                  "Locked until 1 Mar 2027, in 60 days", "1 Sep 2029", "36 interest payments"):
        assert words in text, words
    assert re.search(r"Interest received\D*400\b", text)
    assert not STOCK_WORDS.search(text), STOCK_WORDS.search(text)
    assert "/investments/new?kind=buy" not in page.text
    assert f"/deposits/{accounts['cd'].id}" in page.text


def test_the_holding_figures_come_from_the_deposit_service(c, setup):
    accounts, _ = setup
    certificate = _monthly(c, accounts)
    factor = Decimal("90")

    info = c.deposits.holding(certificate, date(2027, 6, 15), Decimal("1800"), factor)

    assert info["expected"] == Decimal("1800")                    # 9 monthly payouts of 12,000 x 20% / 12
    assert info["next_date"] == "2027-07-01" and info["next_amount"] == Decimal("200")
    assert info["unlock_days"] is None and info["maturity_days"] == (date(2029, 9, 1) - date(2027, 6, 15)).days
    assert info["value"] == Decimal("12000")                      # it pays as it goes, so it stays at principal
    assert info["cash_in"] == Decimal("10800.00")                 # unlocked: 90% sale factor
    assert info["interest_payments"] == 36
    locked = c.deposits.holding(certificate, date(2026, 12, 31), Decimal("0"), factor)
    assert locked["cash_in"] is None and locked["unlock_days"] == 60


def test_the_certificates_page_leads_with_the_list_and_opens_the_buy_form_from_a_button(c, setup):
    accounts, _ = setup
    certificate = _monthly(c, accounts)
    holding = f'href="/investments/holding/{certificate.terms.asset_id}?account={accounts["cd"].id}"'

    pc = _client(c).get(f"/deposits/{accounts['cd'].id}").text
    assert pc.index("<table") < pc.index('id="buy-certificate"') and holding in pc
    assert re.search(r'<details class="card" id="buy-certificate"[^>]*>\s*<summary', pc)
    assert 'id="buy-certificate" style="margin-top:16px" open' not in pc   # it opens from its button
    head = _text(pc[pc.index("<thead"):pc.index("</thead>")]).split()
    assert head == ["Certificate", "Interest", "rate", "Next", "payment", "Maturity", "Status"]
    assert "1 Jan 2027" in _text(pc[pc.index("<tbody"):pc.index("</tbody>")])

    phone = _client(c, phone=True).get(f"/deposits/{accounts['cd'].id}").text
    rows = phone[phone.index('id="certificate-'):phone.index('id="buy-certificate"')]
    assert "<table" not in rows and holding in rows   # rows, never a table cut at the phone's edge
    assert all(words in _text(rows) for words in ("CIB 3-year certificate", "20%", "Next payment", "1 Jan 2027",
                                                    "Maturity", "1 Sep 2029", "Locked"))
