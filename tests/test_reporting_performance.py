"""Guard the reporting hot paths against per-row metadata queries."""

from decimal import Decimal
from time import perf_counter


def _add_synthetic_transfers(c, accounts, count=319, sequence_start=0):
    """Add a compact, internally balanced 319-transfer read-load fixture."""
    cash_id = c.assets.cash_asset("EGP").id
    with c.db.transaction():
        for sequence in range(sequence_start, sequence_start + count):
            day = (sequence % 29) + 2  # after the opening position, within September
            date = f"2026-09-{day:02}"
            ref = f"PERF-{sequence:04}"
            cursor = c.db.execute(
                "INSERT INTO transactions(ref,type,date,description,status,source,created_at,updated_at) "
                "VALUES (?,'TRF',?,'Synthetic performance transfer','POSTED','MANUAL',?,?)",
                (ref, date, date + "T12:00:00", date + "T12:00:00"),
            )
            transaction_id = cursor.lastrowid
            for line_no, account_id, signed in (
                (1, accounts["cib"].id, -10_000_000),
                (2, accounts["thndr"].id, 10_000_000),
            ):
                c.db.execute(
                    "INSERT INTO ledger_entries(transaction_id,line_no,date,account_id,asset_id,quantity_e6,"
                    "unit_price_e6,amount_e6,fx_rate_e6,amount_base_e6,effect) "
                    "VALUES (?,?,?,?,?,?,1000000,?,?,?,'INTERNAL')",
                    (transaction_id, line_no, date, account_id, cash_id, signed, signed, 1_000_000, signed),
                )


def test_holdings_loads_metadata_in_batches_and_reflects_new_transactions(c, setup, monkeypatch):
    accounts, cats = setup
    counts = {"account_get": 0, "asset_get": 0, "class_get": 0}
    original_account_get = c.accounts.get
    original_asset_get = c.assets.get_asset
    original_class_get = c.assets.get_class

    def account_get(*args, **kwargs):
        counts["account_get"] += 1
        return original_account_get(*args, **kwargs)

    def asset_get(*args, **kwargs):
        counts["asset_get"] += 1
        return original_asset_get(*args, **kwargs)

    def class_get(*args, **kwargs):
        counts["class_get"] += 1
        return original_class_get(*args, **kwargs)

    monkeypatch.setattr(c.accounts, "get", account_get)
    monkeypatch.setattr(c.assets, "get_asset", asset_get)
    monkeypatch.setattr(c.assets, "get_class", class_get)

    earlier, _ = c.reporting.holdings("2026-09-30")
    assert counts == {"account_get": 0, "asset_get": 0, "class_get": 0}
    assert sum((row.value or Decimal(0) for row in earlier), Decimal(0)) == Decimal("56200")

    c.transactions.record_inflow("2026-10-01", accounts["cib"].id, "1200", cats["EXP.WORK.SALARY"].id)
    counts.update(account_get=0, asset_get=0, class_get=0)
    later, _ = c.reporting.holdings("2026-10-01")
    assert sum((row.value or Decimal(0) for row in later), Decimal(0)) == Decimal("57400")
    assert counts == {"account_get": 0, "asset_get": 0, "class_get": 0}


def test_investment_report_does_not_fetch_asset_metadata_per_ledger_row(c, setup, monkeypatch):
    accounts, _ = setup
    count = 0
    original_get = c.assets.get_asset

    def get_asset(*args, **kwargs):
        nonlocal count
        count += 1
        return original_get(*args, **kwargs)

    monkeypatch.setattr(c.assets, "get_asset", get_asset)
    from lightning.investments.report import build_investment_report

    def measure(end):
        statements = []
        c.db.conn.set_trace_callback(statements.append)
        start = perf_counter()
        result = build_investment_report(c.db, c.accounts, c.assets, c.reporting,
                                         "2026-09-01", end)
        elapsed = (perf_counter() - start) * 1000
        c.db.conn.set_trace_callback(None)
        selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        return result, len(selects), elapsed

    before, _, _ = measure("2026-09-01")
    assert before["investment_cash"] == Decimal(0)
    _add_synthetic_transfers(c, accounts, 12)
    small, small_queries, small_ms = measure("2026-09-15")
    assert small["investment_cash"] == Decimal("120")
    count_before_load = count
    _add_synthetic_transfers(c, accounts, 307, sequence_start=12)
    after, after_queries, after_ms = measure("2026-09-30")
    assert after["investment_cash"] == Decimal("3190")
    assert count - count_before_load <= 2  # bounded by distinct assets resolved for the final report
    assert after_queries == small_queries  # not proportional to ledger row count

    rows = c.db.all(
        "SELECT le.asset_id FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id "
        "WHERE t.status='POSTED' AND t.type<>'VAL' AND le.owner_id IS NULL AND le.date<='2026-09-30'")
    lookup_sql = []
    c.db.conn.set_trace_callback(lookup_sql.append)
    lookup_start = perf_counter()
    for row in rows:  # reproduce the removed one-get_asset-per-ledger-row behavior
        c.assets.get_asset(row["asset_id"])
    lookup_ms = (perf_counter() - lookup_start) * 1000
    c.db.conn.set_trace_callback(None)
    legacy_lookup_queries = sum(sql.lstrip().upper().startswith("SELECT") for sql in lookup_sql)
    assert legacy_lookup_queries == len(rows)
    print(f"investment_report SQL={small_queries}/{after_queries} "
          f"service_ms={small_ms:.1f}/{after_ms:.1f} (12/319 transfers); "
          f"former row lookup loop={legacy_lookup_queries} SQL, {lookup_ms:.1f}ms; "
          f"optimized total queries={after_queries}, former estimated total={after_queries - 1 + legacy_lookup_queries}")
