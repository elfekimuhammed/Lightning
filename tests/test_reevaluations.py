from decimal import Decimal


def test_monthly_returns_create_one_account_journal_linked_from_each_asset(c):
    account = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "10000")
    first = c.assets.create_investment("First fund", "FUND.EQUITY", "F1")
    second = c.assets.create_investment("Second fund", "FUND.EQUITY", "F2")
    c.investments.add_holding(account.id, first.id, "10", "1000", "2026-09-01")
    c.investments.add_holding(account.id, second.id, "20", "1000", "2026-09-02")
    c.assets.set_price(first.id, "2026-09-30", "110")
    c.assets.set_price(second.id, "2026-09-30", "55")

    assert c.reevaluations.process_date("2026-09-30", "MONTH_END")
    detail = c.db.all("SELECT * FROM reevaluation_entries ORDER BY asset_id")
    assert len(detail) == 2
    assert {row["journal_transaction_id"] for row in detail} == {detail[0]["journal_transaction_id"]}
    journal = c.transactions.get(detail[0]["journal_transaction_id"])
    assert journal.type.value == "VAL" and journal.source.value == "SYSTEM"
    assert journal.lines[0].effect.value == "REVALUATION"
    assert journal.lines[0].amount_base == Decimal("200")
    assert len(journal.lines) == 1
    assert c.reporting.account_balance(account.id) == Decimal("10000")
    assert c.db.scalar("SELECT status FROM reevaluation_periods WHERE date='2026-09-30'") == "POSTED"
    assert c.reevaluations.process_date("2026-09-30", "MONTH_END")  # idempotent on reopen
    assert c.db.scalar("SELECT COUNT(*) FROM transactions WHERE type='VAL'") == 1


def test_sale_forces_same_day_revaluation_at_trade_price(c):
    account = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "10000")
    asset = c.assets.create_investment("COMI", "STOCK", "COMI")
    c.investments.add_holding(account.id, asset.id, "10", "1000", "2026-09-01")
    c.assets.set_price(asset.id, "2026-09-30", "120")
    assert c.reevaluations.process_date("2026-09-30", "MONTH_END")

    c.investments.sell("2026-10-05", account.id, asset.id, "5", "130")
    sale_period = c.db.one("SELECT id,status FROM reevaluation_periods WHERE date='2026-10-05' AND reason='SALE'")
    assert sale_period["status"] == "POSTED"
    detail = c.db.one("SELECT * FROM reevaluation_entries WHERE period_id=?", (sale_period["id"],))
    assert detail["price_source"] == "TRADE"
    assert Decimal(detail["return_base_e6"]) / 1_000_000 == Decimal("100")
    assert detail["journal_transaction_id"] is not None
    linked = c.db.scalar("SELECT transaction_id FROM reevaluation_account_posts WHERE period_id=?",
                         (sale_period["id"],))
    assert linked == detail["journal_transaction_id"]


def test_pending_month_end_price_is_explicit_and_completes_after_manual_entry(c):
    account = c.account_flows.open_account("THNDR", "BROKERAGE", "2026-09-01", "10000")
    asset = c.assets.create_investment("Fund no feed", "FUND.EQUITY", "NOFEED")
    c.investments.add_holding(account.id, asset.id, "10", "1000", "2026-09-01")
    assert not c.reevaluations.process_date("2026-09-30", "MONTH_END")
    assert c.reevaluations.pending_prices()[0]["asset_id"] == asset.id

    c.reevaluations.record_manual_price(asset.id, "2026-09-30", Decimal("120"))
    assert c.db.scalar("SELECT status FROM reevaluation_periods WHERE date='2026-09-30'") == "POSTED"
    assert c.reevaluations.pending_prices() == []
