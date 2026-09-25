"""Investments: buy, sell, dividends, holdings, prices, and the net-worth equation with revaluation."""

import random
from decimal import Decimal

import pytest

from lightning.core.errors import ConflictError, ValidationError
from lightning.core.money import ZERO
from lightning.transactions.domain import TxnFilter

D = Decimal


@pytest.fixture
def inv(c, setup):
    accounts, cats = setup
    comi = c.assets.create_investment("Commercial International Bank", "STOCK", "COMI")
    gold_fund = c.assets.create_investment("AZ Gold Fund", "FUND.GOLD", "AZ Gold")
    c.transactions.record_transfer("2026-09-02", accounts["cib"].id, accounts["thndr"].id, "30000")
    return c, accounts, cats, comi, gold_fund


def pos(c, account_id, asset_id, as_of="2026-12-31"):
    return next(p for p in c.investments.portfolio(as_of, account_id).positions if p.asset_id == asset_id)


class TestAssets:
    def test_codes_and_defaults(self, c):
        comi = c.assets.create_investment("Commercial International Bank", "STOCK", "comi")
        assert comi.code == "STK:COMI" and comi.unit == "share" and comi.quantity_decimals == 0
        fund = c.assets.create_investment("AZ Gold Fund", "FUND.GOLD", "AZ Gold")
        assert fund.code == "FND:AZ-GOLD" and fund.exposure.value == "GOLD"
        gold = c.assets.create_investment("Gold 21K", "GOLD", karat="21")
        assert gold.code == "GLD:21K" and gold.purity == D("0.875") and gold.unit == "gram"
        with pytest.raises(ConflictError):
            c.assets.create_investment("CIB again", "STOCK", "COMI")
        with pytest.raises(ValidationError):
            c.assets.create_investment("X", "CASH", "X")

    def test_prices(self, c):
        comi = c.assets.create_investment("CIB", "STOCK", "COMI")
        c.assets.set_price(comi.id, "2026-09-10", "95.5")
        c.assets.set_price(comi.id, "2026-09-10", "96")  # same day replaces
        assert [p.price for p in c.assets.price_history(comi.id)] == [D("96")]
        with pytest.raises(ValidationError):
            c.assets.set_price(comi.id, "2027-01-01", "1")  # future
        with pytest.raises(ValidationError):
            c.assets.set_price(comi.id, "2026-09-10", "0")


class TestTrades:
    def test_buy_is_a_conversion_at_cost(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        t = c.investments.buy("2026-09-10", thndr, comi.id, "100", "95", fees="50")
        assert t.ref == "BUY-2026-09-10-001"
        assert c.reporting.account_balance(thndr) == D("30000") - D("9550")  # cash only
        p = pos(c, thndr, comi.id)
        assert (p.quantity, p.cost_basis, p.average_cost) == (D("100"), D("9550"), D("95.5"))
        assert p.price == D("95") and p.price_source == "TRADE" and p.value == D("9500")
        assert p.unrealized == D("-50")  # the fee
        assert c.reporting.account_value(thndr, "2026-12-31") == D("20450") + D("9500")

    def test_sell_realizes_gain_on_average_cost(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "100", "95", fees="50")
        c.investments.buy("2026-09-15", thndr, comi.id, "100", "105")  # avg now (9550+10500)/200 = 100.25
        c.investments.sell("2026-09-20", thndr, comi.id, "50", "110", fees="25")
        p = pos(c, thndr, comi.id)
        assert p.quantity == D("150")
        assert p.cost_basis == D("15037.50")  # 150 × 100.25
        assert p.realized == D("5500") - D("25") - D("5012.50")  # proceeds − cost removed
        assert p.price == D("110") and p.value == D("16500")

    def test_cannot_sell_what_you_do_not_hold(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "10", "95")
        with pytest.raises(ValidationError, match="less than zero"):
            c.investments.sell("2026-09-12", thndr, comi.id, "11", "100")
        with pytest.raises(ValidationError, match="less than zero"):
            c.investments.sell("2026-09-09", thndr, comi.id, "5", "100")  # before the buy
        sale = c.investments.sell("2026-09-12", thndr, comi.id, "10", "100")
        buy_id = c.transactions.find(TxnFilter(search="BUY-"))[0][0].id
        with pytest.raises(ValidationError, match="less than zero"):
            c.transactions.void(buy_id)  # the later sale would have nothing to sell
        c.transactions.void(sale.id)
        c.transactions.void(buy_id)
        assert c.investments.holding(thndr, comi.id) == ZERO

    def test_gold_bought_with_wallet_cash(self, c, setup):
        accounts, _ = setup
        home = c.account_flows.open_account("Gold at home", "PHYSICAL_ASSET", "2026-09-01")
        gold = c.assets.create_investment("Gold 21K", "GOLD", karat="21")
        with pytest.raises(ValidationError, match="comes from"):
            c.investments.buy("2026-09-10", home.id, gold.id, "10", "4000")
        c.investments.buy("2026-09-10", home.id, gold.id, "10.5", "4000", fees="1500",
                          cash_account_id=accounts["cib"].id)
        assert c.reporting.account_balance(accounts["cib"].id) == D("50000") - D("43500")
        p = pos(c, home.id, gold.id)
        assert p.quantity == D("10.5") and p.cost_basis == D("43500") and p.value == D("42000")
        with pytest.raises(ValidationError, match="decimal"):
            c.investments.buy("2026-09-10", home.id, gold.id, "1.2345", "4000", cash_account_id=accounts["cib"].id)

    def test_only_investment_accounts_hold_investments(self, inv):
        c, accounts, _, comi, _ = inv
        with pytest.raises(ValidationError, match="brokerage"):
            c.investments.buy("2026-09-10", accounts["cib"].id, comi.id, "1", "95")

    def test_dividends_are_investment_income_per_holding(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "100", "95")
        d = c.investments.dividend("2026-09-28", thndr, comi.id, "250")
        assert d.type == "DIV" and d.counterparty == comi.name
        flow = c.reporting.cash_flow("2026-09-01", "2026-09-30")
        assert flow.investment_inflows == D("250") and flow.household_inflows == ZERO
        p = pos(c, thndr, comi.id)
        assert p.dividends == D("250") and p.total_return == D("250")

    def test_existing_holding_valued_at_cost_until_priced(self, inv):
        c, accounts, _, comi, fund = inv
        thndr = accounts["thndr"].id
        c.investments.add_holding(thndr, fund.id, "1000.5", "12,000")
        p = pos(c, thndr, fund.id)
        assert p.price_source == "COST" and p.value == D("12000") and p.unrealized == ZERO
        with pytest.raises(ConflictError):
            c.investments.add_holding(thndr, fund.id, "1", "1")
        c.assets.set_price(fund.id, "2026-09-30", "13")
        p = pos(c, thndr, fund.id)
        assert p.price_source == "MANUAL" and p.value == D("13006.50") and p.unrealized == D("1006.50")
        # the cash opening balance is untouched
        assert c.transactions.opening_balance(thndr) == ZERO
        assert c.account_flows.opening_of(accounts["thndr"]) == ZERO

    def test_manual_price_wins_on_the_same_day(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "10", "95")
        c.assets.set_price(comi.id, "2026-09-10", "96")
        assert pos(c, thndr, comi.id).price == D("96")
        c.investments.buy("2026-09-11", thndr, comi.id, "10", "97")  # newer trade price wins
        assert pos(c, thndr, comi.id).price == D("97")

    def test_edit_keeps_ref_and_values_round_trip(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        t = c.investments.buy("2026-09-10", thndr, comi.id, "100", "95", fees="50")
        values = c.investments.values_of(t.id)
        assert (values["quantity"], values["price"], values["fees"]) == (D("100"), D("95"), D("50"))
        edited = c.investments.update(t.id, date="2026-09-11", account_id=thndr, asset_id=comi.id, quantity="80",
                                      price="96", fees="10")
        assert edited.ref == t.ref and edited.date == "2026-09-11"
        assert pos(c, thndr, comi.id).cost_basis == D("7690")

    def test_register_shows_cash_only(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "100", "95", fees="50")
        rows = c.reporting.register(thndr, "1900-01-01", "9999-12-31")
        buy = next(r for r in rows if r.type == "BUY")
        assert buy.payment == D("9550") and "Buy 100 × STK:COMI @ 95" in buy.category_label
        assert all(r.balance is None or r.balance >= 0 for r in rows)


class TestNetWorth:
    def test_revaluation_explains_price_changes(self, inv):
        c, accounts, _, comi, _ = inv
        thndr = accounts["thndr"].id
        c.investments.buy("2026-09-10", thndr, comi.id, "100", "95", fees="50")
        c.assets.set_price(comi.id, "2026-09-30", "100")
        sep = c.reporting.bridge_for_month("2026-09")
        assert sep.revaluation == D("450")  # +500 price move, −50 fee
        assert sep.difference == ZERO
        c.assets.set_price(comi.id, "2026-10-31", "90")
        oct_ = c.reporting.bridge_for_month("2026-10")
        assert oct_.revaluation == D("-1000") and oct_.inflows == ZERO and oct_.difference == ZERO
        groups = {g.code: g.value for g in c.reporting.net_worth("2026-10-31").by_class}
        assert groups["STOCK"] == D("9000")

    def test_randomized_portfolio_always_reconciles(self, c):
        rng = random.Random(3)
        f = c.account_flows
        thndr = f.open_account("THNDR", "BROKERAGE", "2026-01-01", "200000", institution="THNDR")
        home = f.open_account("Gold at home", "PHYSICAL_ASSET", "2026-01-01")
        bank = f.open_account("Bank", "BANK", "2026-01-01", "500000")
        assets = [c.assets.create_investment(f"Stock {i}", "STOCK", f"S{i}") for i in range(3)]
        assets.append(c.assets.create_investment("Fund", "FUND.EQUITY", "F1"))
        gold = c.assets.create_investment("Gold 24K", "GOLD", karat="24")
        c.investments.add_holding(thndr.id, assets[0].id, "50", "4000", "2026-01-01")
        for _ in range(250):
            day = f"2026-{rng.randint(1, 6):02d}-{rng.randint(1, 28):02d}"
            roll = rng.random()
            asset = rng.choice(assets)
            price = D(rng.randint(500, 20000)) / 100
            try:
                if roll < 0.35:
                    c.investments.buy(day, thndr.id, asset.id, str(rng.randint(1, 40)), price, fees=str(rng.randint(0, 30)))
                elif roll < 0.55:
                    held = c.investments.holding(thndr.id, asset.id, day)
                    if held:
                        c.investments.sell(day, thndr.id, asset.id, str(rng.randint(1, int(held))), price,
                                           fees=str(rng.randint(0, 5)))
                elif roll < 0.7:
                    c.assets.set_price(asset.id, day, price)
                elif roll < 0.8:
                    c.investments.buy(day, home.id, gold.id, f"{rng.randint(1, 20)}.{rng.randint(0, 999):03d}",
                                      D(rng.randint(300000, 500000)) / 100, fees="100", cash_account_id=bank.id)
                elif roll < 0.9:
                    c.investments.dividend(day, thndr.id, asset.id, str(rng.randint(1, 500)))
                else:
                    c.assets.set_price(gold.id, day, D(rng.randint(300000, 500000)) / 100)
            except ValidationError:
                continue  # e.g. a sale dated before the units were bought
        for month in ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]:
            b = c.reporting.bridge_for_month(month)
            assert b.difference == ZERO, month
        # net worth = cash + every holding at its price
        nw = c.reporting.net_worth("2026-06-30")
        portfolio = c.investments.portfolio("2026-06-30")
        cash = sum((c.reporting.account_balance(a.id, "2026-06-30") for a in (thndr, home, bank)), ZERO)
        assert nw.total == cash + portfolio.value
        assert not nw.unvalued


class TestInvestmentPages:
    def test_full_investing_flow(self, c, setup):
        from fastapi.testclient import TestClient
        from lightning.ui.web import create_app
        accounts, _ = setup
        client = TestClient(create_app(c))
        thndr = accounts["thndr"]
        c.transactions.record_transfer("2026-09-02", accounts["cib"].id, thndr.id, "20000")
        assert "No holdings yet" in client.get("/investments").text
        r = client.post("/investments/assets/new?then=buy", data={"name": "Commercial International Bank",
                        "class_code": "STOCK", "symbol": "COMI"})
        assert "Added STK:COMI" in r.text and "Buy" in r.text
        comi = c.assets.get_asset_by_code("STK:COMI")
        r = client.post("/investments/new?kind=buy", data={"date": "2026-09-10", "account_id": thndr.id,
                        "asset_id": comi.id, "quantity": "100", "price": "95", "fees": "50"})
        assert "Saved BUY-2026-09-10-001" in r.text  # lands on the THNDR register
        assert "Holdings" in r.text and "Commercial International Bank" in r.text and "-9,550.00" in r.text
        r = client.post("/investments/prices", data={"date": "2026-09-30", f"p_{comi.id}": "100"})
        assert "Saved 1 price for 2026-09-30" in r.text and "+450.00" in r.text  # unrealized on the page
        r = client.post("/investments/new?kind=sell", data={"date": "2026-09-30", "account_id": thndr.id,
                        "asset_id": comi.id, "quantity": "500", "price": "100"})
        assert r.status_code == 400 and "less than zero" in r.text
        buy = c.transactions.get_by_ref("BUY-2026-09-10-001")
        page = client.get(f"/investments/{buy.id}/edit")
        assert page.status_code == 200 and 'value="95' in page.text
        r = client.post(f"/investments/{buy.id}/edit", data={"date": "2026-09-10", "account_id": thndr.id,
                        "asset_id": comi.id, "quantity": "100", "price": "94", "fees": "50"})
        assert "Saved BUY-2026-09-10-001" in r.text
        r = client.post("/investments/new?kind=dividend", data={"date": "2026-09-28", "account_id": thndr.id,
                        "asset_id": comi.id, "amount": "120"})
        assert "Saved DIV-2026-09-28-001" in r.text

    @pytest.mark.parametrize("path", ["/investments", "/investments/new?kind=buy", "/investments/new?kind=sell",
                                      "/investments/new?kind=dividend", "/investments/new?kind=holding",
                                      "/investments/assets/new", "/investments/prices"])
    def test_pages_render(self, c, setup, path):
        from fastapi.testclient import TestClient
        from lightning.ui.web import create_app
        assert TestClient(create_app(c)).get(path).status_code == 200
