from __future__ import annotations

import os

import pytest

# Tests use dates across 2026; pin "today" so future-date rules don't depend on when they run.
os.environ["LIGHTNING_TODAY"] = "2026-12-31"

from lightning.bootstrap import Container, build


@pytest.fixture(autouse=True)
def fixed_audit_clock(monkeypatch):
    # Historical fixtures also depend on record creation timestamps, not only
    # LIGHTNING_TODAY. Keep them independent of the host clock and timezone.
    from datetime import datetime, timezone
    from lightning.core import dates
    monkeypatch.setattr(dates, "_local_now", lambda: datetime(2026, 9, 30, 12, tzinfo=timezone.utc))


@pytest.fixture
def c(tmp_path) -> Container:
    container = build(tmp_path / "test.db")
    yield container
    container.db.close()


@pytest.fixture
def setup(c):
    """A typical household: bank, wallet, a CD, THNDR cash."""
    f = c.account_flows
    accounts = {
        "cib": f.open_account("CIB Current", "BANK", "2026-09-01", "50,000", institution="CIB"),
        "wallet": f.open_account("Wallet", "CASH", "2026-09-01", "1200"),
        "cd": f.open_account("CIB CD", "DEPOSIT", "2026-09-01", "5000", institution="CIB"),
        "thndr": f.open_account("THNDR", "BROKERAGE", "2026-09-01", "0", institution="THNDR"),
    }
    cats = {code: c.categories.get_by_code(code) for code in (
        "EXP.PERSONAL.FOOD", "EXP.WORK.SOFTWARE", "EXP.WORK.SALARY", "EXP.INVEST.INTEREST")}
    return accounts, cats
