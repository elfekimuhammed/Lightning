from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lightning.planning.position import PositionService


def _position_service(c, deposits):
    return PositionService(c.reporting, c.assets, c.investments, c.money_from_others,
                           c.reserves, c.planning, deposits)


def _terms(c, account_id, destination_id, *, lockup_end, maturity, principal="5000"):
    return c.deposits.save(
        account_id=account_id,
        start_date="2026-09-01",
        lockup_end_date=lockup_end,
        maturity_date=maturity,
        principal=principal,
        annual_rate="10",
        interest_method="SIMPLE",
        payout_frequency="AT_MATURITY",
        destination_account_id=destination_id,
    )


@pytest.mark.parametrize(
    "as_of,expected_sale",
    [
        ("2027-02-28", Decimal("0")),
        ("2027-03-01", Decimal("3250")),
        ("2027-06-15", Decimal("3250")),
        ("2027-09-01", Decimal("5000")),
        ("2027-09-02", Decimal("5000")),
    ],
)
def test_cd_early_redemption_uses_lockup_and_maturity_dates(c, setup, as_of, expected_sale):
    accounts, _ = setup
    cd_class = c.assets.get_class_by_code("DEPOSIT.CD")
    c.investments.set_liquidation_factor(cd_class.id, "65")
    _terms(c, accounts["cd"].id, accounts["cib"].id,
           lockup_end="2027-03-01", maturity="2027-09-01")
    service = _position_service(c, c.deposits)

    before = c.reporting.account_balance(accounts["cd"].id, as_of)
    position = service.at(date.fromisoformat(as_of))
    cd_item = next(item for cls in position.classes for item in cls.items
                   if item.account_id == accounts["cd"].id)

    assert cd_item.value == before == Decimal("5000")
    assert c.reporting.account_balance(accounts["cd"].id, as_of) == before
    assert position.deposits == Decimal("5000")
    assert position.deposits_after_sale == expected_sale
    assert position.what_you_own == c.reporting.net_worth(as_of).total


def test_cd_valuation_only_changes_after_sale_estimate(c, setup):
    accounts, _ = setup
    cd_class = c.assets.get_class_by_code("DEPOSIT.CD")
    c.investments.set_liquidation_factor(cd_class.id, "65")
    plain = _position_service(c, None).at("2027-02-28")
    _terms(c, accounts["cd"].id, accounts["cib"].id,
           lockup_end="2027-03-01", maturity="2027-09-01")

    with_terms = _position_service(c, c.deposits).at("2027-02-28")

    assert with_terms.net_worth == plain.net_worth
    assert with_terms.deposits == plain.deposits == Decimal("5000")
    assert with_terms.free_cash == plain.free_cash
    assert plain.deposits_after_sale == Decimal("3250")
    assert with_terms.deposits_after_sale == Decimal("0")


def test_legacy_cd_without_terms_keeps_class_factor(c, setup):
    accounts, _ = setup
    cd_class = c.assets.get_class_by_code("DEPOSIT.CD")
    c.investments.set_liquidation_factor(cd_class.id, "65")

    position = _position_service(c, c.deposits).at("2027-02-28")

    assert position.deposits_after_sale == Decimal("3250")


def test_multiple_cds_apply_their_own_lockup_and_maturity(c, setup):
    accounts, _ = setup
    second = c.account_flows.open_account("Second CD", "DEPOSIT", "2026-09-01", "2000")
    cd_class = c.assets.get_class_by_code("DEPOSIT.CD")
    c.investments.set_liquidation_factor(cd_class.id, "65")
    _terms(c, accounts["cd"].id, accounts["cib"].id,
           lockup_end="2027-03-01", maturity="2027-04-01")
    _terms(c, second.id, accounts["cib"].id,
           lockup_end="2027-03-01", maturity="2027-09-01", principal="2000")

    position = _position_service(c, c.deposits).at("2027-04-01")

    assert position.deposits == Decimal("7000")
    assert position.deposits_after_sale == Decimal("6300")
