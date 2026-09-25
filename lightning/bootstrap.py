"""Composition root: builds the database and wires every service together.

This is the only place that knows how modules connect. The UI receives a ready Container.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.budgeting.service import BudgetService
from lightning.categories.service import CategoryService
from lightning.database.audit import AuditLog
from lightning.database.backup import backup
from lightning.database.connection import Database
from lightning.database.migrator import migrate
from lightning.database.seed import seed
from lightning.database.settings import SettingsStore
from lightning.investments.service import InvestmentService
from lightning.reporting.service import ReportingService
from lightning.transactions.service import TransactionService
from lightning.workflows.accounts import AccountWorkflows

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass
class Container:
    db: Database
    data_dir: Path
    settings: SettingsStore
    audit: AuditLog
    assets: AssetService
    categories: CategoryService
    accounts: AccountService
    transactions: TransactionService
    reporting: ReportingService
    budgets: BudgetService
    investments: InvestmentService
    account_flows: AccountWorkflows

    @property
    def base_currency(self) -> str:
        return self.settings.base_currency

    def backup_now(self) -> Path | None:
        return backup(self.db, self.data_dir / "backups")


def build(db_path: str | Path | None = None, backup_on_start: bool = False) -> Container:
    db_path = Path(db_path) if db_path else DEFAULT_DATA_DIR / "lightning.db"
    data_dir = db_path.parent
    db = Database(db_path)
    if backup_on_start and db_path.exists():
        backup(db, data_dir / "backups")
    migrate(db)
    seed(db)
    settings = SettingsStore(db)
    base = settings.base_currency
    audit = AuditLog(db)
    assets = AssetService(db, base)
    categories = CategoryService(db)
    accounts = AccountService(db, assets, base)
    transactions = TransactionService(db, accounts, assets, categories, audit, base)
    reporting = ReportingService(db, accounts, assets, categories, base)
    return Container(
        db=db,
        data_dir=data_dir,
        settings=settings,
        audit=audit,
        assets=assets,
        categories=categories,
        accounts=accounts,
        transactions=transactions,
        reporting=reporting,
        budgets=BudgetService(db, categories, reporting),
        investments=InvestmentService(db, accounts, assets, categories, transactions, reporting),
        account_flows=AccountWorkflows(db, accounts, transactions, reporting),
    )
