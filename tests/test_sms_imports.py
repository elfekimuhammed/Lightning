"""Milestone 3: bank SMS read into the reviewed bank import (`lightning/sms_imports.py`).

Every sample in tests/fixtures/bank_sms.json is read and checked: inflow or outflow, kind, amount, the account's
ending, the date and time, and who or where. Then a batch goes through the bank import's review like a CSV."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from lightning.sms_imports import SALARY_ENDING, parse_sms

SAMPLES = json.loads((Path(__file__).parent / "fixtures" / "bank_sms.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sample", SAMPLES["samples"], ids=lambda s: f"{s['bank']}-{s['kind']}-{s['received']}")
def test_every_sample_reads_as_labelled(sample):
    found = parse_sms(sample["text"], sender=sample["sender"], received=datetime.fromisoformat(sample["received"]))
    assert found is not None, sample["text"]
    assert found.kind == sample["kind"] and found.bank == sample["bank"]
    assert found.inflow == (sample["direction"] == "inflow")
    for key, value in sample["expect"].items():
        got = getattr(found, key)
        assert (got == Decimal(value)) if key in ("amount", "balance") else (got == value), (key, got, value)


@pytest.mark.parametrize("text", SAMPLES["not_money"])
def test_codes_declines_and_offers_are_not_transactions(text):
    assert parse_sms(text) is None


def test_messages_go_to_review_once_and_each_ending_is_asked_once(c, setup):
    accounts, _ = setup
    picked = [s for s in SAMPLES["samples"] if s["bank"] == "NBE"]
    messages = [(s["sender"], s["text"], datetime.fromisoformat(s["received"])) for s in picked]
    first = c.sms_imports.read(messages)
    assert first["staged"] == {} and first["waiting"] == len(picked)  # endings unknown: nothing guessed
    endings = {group["ending"] for group in c.sms_imports.waiting()}
    assert endings == {"2093", "6628"}
    batch = c.sms_imports.assign("6628", accounts["cib"].id)
    _, rows = c.bank_imports.preview(batch)
    assert sorted(Decimal(r["Amount"]) for r in rows) == [Decimal("-10000.00"), Decimal("30.00"),
                                                          Decimal("700.00"), Decimal("4000.00")]
    assert {r["Reference"] for r in rows} >= {"517703926481"}
    again = c.sms_imports.read(messages)  # the inbox read again: nothing new
    assert again["staged"] == {} and again["skipped"] == len(picked)
    later = picked[0] | {"text": picked[0]["text"].replace("147.87", "99.10"), "received": "2026-10-07T08:00"}
    assert c.sms_imports.read([(later["sender"], later["text"], datetime(2026, 10, 7, 8))])["waiting"] == 8  # still asks for 2093


def test_cash_withdrawal_is_a_transfer_and_salary_has_its_own_choice(c, setup):
    accounts, _ = setup
    cib = [s for s in SAMPLES["samples"] if s["bank"] == "CIB"]
    c.sms_imports.read([(s["sender"], s["text"], datetime.fromisoformat(s["received"])) for s in cib])
    assert {g["ending"] for g in c.sms_imports.waiting()} == {"7351", "4410", SALARY_ENDING}
    _, rows = c.bank_imports.preview(c.sms_imports.assign("7351", accounts["cib"].id))
    assert rows[0]["Category"] == "Transfer" and "transfer to Wallet" in rows[0]["Notes"]
    _, rows = c.bank_imports.preview(c.sms_imports.assign(SALARY_ENDING, accounts["cib"].id))
    assert rows[0]["Amount"] == "19584.66" and rows[0]["Category"] == "Salary"


def test_paste_then_say_the_account_then_review(c, setup, tmp_path):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    accounts, _ = setup
    client = TestClient(create_app(c))
    nbe = [s["text"] for s in SAMPLES["samples"] if s["bank"] == "NBE" and s["kind"] == "purchase"][:2]
    page = client.post("/sms/paste", data={"messages": "\n\n".join(nbe)})
    assert "2 waiting for their account" in page.text and "Which account ends with 2093?" in page.text
    review = client.post("/sms/assign", data={"ending": "2093", "account_id": str(accounts["cib"].id)})
    assert "/import/" in str(review.url) and "Uber" in review.text


@pytest.mark.parametrize("sample", SAMPLES["reworded"], ids=lambda s: s["why"])
def test_a_reworded_message_is_still_read_and_flagged_to_check(sample):
    found = parse_sms(sample["text"], received=datetime(2026, 10, 7, 13))
    assert found is not None and found.inflow == (sample["direction"] == "inflow")
    for key, value in sample["expect"].items():
        got = getattr(found, key)
        assert (got == Decimal(value)) if key == "amount" else (got == value), (key, got, value)


def test_money_no_rule_reads_is_kept_for_the_owner_never_dropped(c, setup):
    text = SAMPLES["unreadable"][0]
    assert parse_sms(text) is None
    result = c.sms_imports.read([("NBE", text, datetime(2026, 10, 7, 13))])
    assert result["unread"] == 1 and c.sms_imports.unread()[0]["text"] == text
    c.sms_imports.dismiss(c.sms_imports.unread()[0]["id"])
    assert c.sms_imports.unread() == []


def test_from_sms_shows_what_it_could_not_read(c, setup):
    from fastapi.testclient import TestClient
    from lightning.ui.web import create_app
    client = TestClient(create_app(c))
    page = client.post("/sms/paste", data={"messages": SAMPLES["unreadable"][0]})
    assert "1 to read yourself" in page.text and "could not read these" in page.text


class FakeSource:
    """The phone's inbox, as lightning_android.AndroidSms gives it."""

    def __init__(self, inbox, permission="granted"):
        self.inbox, self.state, self.asked, self.shared = inbox, permission, 0, []

    def permission(self):
        return self.state

    def request(self):
        self.asked += 1

    def since(self, after_ms):
        return [m for m in self.inbox if m[2] > after_ms]

    def take_shared(self):
        texts, self.shared = self.shared, []
        return texts


def _ms(text):
    return int(datetime.fromisoformat(text).timestamp() * 1000)


def test_the_phone_inbox_is_read_once_and_people_are_never_read(c, setup):
    nbe = [s for s in SAMPLES["samples"] if s["bank"] == "NBE"]
    inbox = [("NBE", s["text"], _ms(s["received"])) for s in nbe]
    inbox.append(("+201001234567", nbe[0]["text"].replace("147.87", "60.00"), _ms("2026-10-06T12:00")))  # a person
    source = FakeSource(inbox)
    first = c.sms_imports.read_source(source, now=datetime(2026, 10, 7, 9))
    assert first["waiting"] == len(nbe)  # within 30 days, people's numbers skipped
    assert c.sms_imports.read_source(source, now=datetime(2026, 10, 7, 10)) is None  # nothing new since
    source.inbox.append(("NBE", nbe[0]["text"].replace("147.87", "77.00"), _ms("2026-10-07T09:30")))
    source.shared.append(SAMPLES["samples"][0]["text"])
    later = c.sms_imports.read_source(source, now=datetime(2026, 10, 7, 11))
    assert later["waiting"] == len(nbe) + 2


def test_without_permission_only_shared_messages_are_read(c, setup):
    source = FakeSource([("NBE", SAMPLES["samples"][6]["text"], _ms("2026-10-06T11:14"))], permission="not_granted")
    assert c.sms_imports.read_source(source) is None
    source.shared.append(SAMPLES["samples"][6]["text"])
    assert c.sms_imports.read_source(source)["waiting"] == 1


def test_the_phone_app_asks_then_reads_on_overview(tmp_path):
    from fastapi.testclient import TestClient
    from lightning.runtime.app import profile_app
    from lightning.runtime.devices import Devices
    from lightning.runtime.http import Credentials
    from test_profile_app import create, token
    nbe = [s for s in SAMPLES["samples"] if s["bank"] == "NBE"][:3]
    source = FakeSource([("NBE", s["text"], int(datetime.now().timestamp() * 1000) - i) for i, s in enumerate(nbe)],
                        permission="not_granted")
    cfg = Credentials("http://127.0.0.1:9851")
    app = profile_app(cfg, tmp_path / "docs", devices=Devices(tmp_path / "app", port=0), phone=True, sms=source)
    with TestClient(app, base_url=cfg.origin, headers={"Origin": cfg.origin}) as phone:
        phone.get("/__launch", params={"code": cfg.launch_code})
        create(phone)
        from test_devices_app import add_account
        add_account(phone, "NBE current")
        page = phone.get("/sms").text
        assert "Allow reading SMS" in page and "never from people" in page
        phone.post("/sms/allow", data={"__session": token(page, "__session")})
        assert source.asked == 1
        source.state = "granted"
        overview = phone.get("/").text
        assert "Bank SMS need their account" in overview
