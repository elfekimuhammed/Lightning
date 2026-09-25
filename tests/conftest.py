from __future__ import annotations

import pytest

from lightning.bootstrap import Container, build


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
        "EXP.PERSONAL.FOOD", "EXP.WORK.SOFTWARE", "INC.SALARY", "INC.INVEST.INTEREST", "EXP.FEES.BANK")}
    return accounts, cats
