"""Composition root: builds the database and wires every service together.

This is the only place that knows how modules connect. The UI receives a ready Container.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lightning.accounts.service import AccountService
from lightning.assets.service import AssetService
from lightning.budgeting.service import BudgetService
from lightning.planning.forecast import CashForecaster
from lightning.planning.position import PositionService
from lightning.planning.service import PlanningService
from lightning.bank_imports import BankImportService
from lightning.categories.service import CategoryService
from lightning.counterparties import CounterpartyService
from lightning.database.audit import AuditLog
from lightning.database.backup import backup, list_backups
from lightning.database.connection import Database
from lightning.database.migrator import inspect_schema, migrate
from lightning.database.seed import seed
from lightning.database.settings import SettingsStore
from lightning.deposits import DepositService
from lightning.investments.service import InvestmentService
from lightning.integrity import IntegrityService
from lightning.money_from_others import MoneyFromOthersService
from lightning.ownership_migration import migrate_legacy_ownership
from lightning.physical_items import PhysicalItemService
from lightning.reporting.service import ReportingService
from lightning.reconciliation import ReconciliationService
from lightning.reserves import CashReserveService
from lightning.reevaluations import ReevaluationService
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
    counterparties: CounterpartyService
    bank_imports: BankImportService
    accounts: AccountService
    transactions: TransactionService
    reporting: ReportingService
    reconciliation: ReconciliationService
    reserves: CashReserveService
    reevaluations: ReevaluationService
    money_from_others: MoneyFromOthersService
    physical_items: PhysicalItemService
    budgets: BudgetService
    investments: InvestmentService
    deposits: DepositService
    account_flows: AccountWorkflows
    integrity: IntegrityService
    planning: PlanningService
    forecaster: CashForecaster
    position: PositionService
    backup_dir: Path | None = None

    @property
    def base_currency(self) -> str:
        return self.settings.base_currency

    def backup_now(self) -> Path | None:
        return backup(self.db, self.backup_dir or self.data_dir / "backups")

    def backup_files(self) -> list[Path]:
        folder = self.backup_dir or self.data_dir / "backups"
        current = [entry.path for entry in list_backups(folder, self.db.path)]
        # Preserve visibility of old-format files; never automatically prune or
        # restore legacy copies whose profile identity is not in their filename.
        import re
        legacy = [p for p in folder.iterdir() if p.is_file() and re.fullmatch(
            r"lightning_\d{4}-\d{2}-\d{2}_\d{4}(?:_\d+)?\.db", p.name
        )] if folder.is_dir() else []
        return current + sorted(legacy, key=lambda p: p.name, reverse=True)


def build(db_path: str | Path | None = None, backup_on_start: bool = False, *,
          key: bytes | None = None, backup_dir: Path | None = None) -> Container:
    db_path = Path(db_path) if db_path else DEFAULT_DATA_DIR / "lightning.db"
    data_dir = db_path.parent
    existed = db_path.is_file() and db_path.stat().st_size > 0
    db = Database(db_path, key=key)
    try:
        inspection = inspect_schema(db)  # Refuse newer schemas before any write.
        if existed and (inspection.needs_backup or backup_on_start):
            saved = backup(db, backup_dir or data_dir / "backups",
                           pre_upgrade=inspection.needs_backup)
            if saved is None:
                raise RuntimeError("A verified backup is required before upgrading")
        migrate(db)
        seed(db)
        migrate_legacy_ownership(db)
    except BaseException:
        db.close()
        raise
    settings = SettingsStore(db)
    base = settings.base_currency
    audit = AuditLog(db)
    assets = AssetService(db, base)
    categories = CategoryService(db)
    accounts = AccountService(db, assets, base)
    transactions = TransactionService(db, accounts, assets, categories, audit, base)
    counterparties = CounterpartyService(db)
    reserves = CashReserveService(db)
    money_from_others = MoneyFromOthersService(db, accounts, transactions)
    physical_items = PhysicalItemService(db, accounts, assets, audit)
    bank_imports = BankImportService(db, accounts, categories, counterparties, transactions, money_from_others, reserves)
    reporting = ReportingService(db, accounts, assets, categories, base, money_from_others)
    budgets = BudgetService(db, categories, reporting)
    reevaluations = ReevaluationService(db, accounts, transactions, reporting)
    planning = PlanningService(db, accounts, categories, counterparties, transactions)
    budgets.scheduled_loans = planning.loan_payments_by_category
    investments = InvestmentService(db, accounts, assets, categories, transactions, reporting, reevaluations)
    deposits = DepositService(db, accounts, assets, transactions)
    position = PositionService(reporting, assets, investments, money_from_others, reserves, planning, deposits)
    forecaster = CashForecaster(planning, reporting, reserves, budgets, categories, position, deposits)
    return Container(
        db=db,
        data_dir=data_dir,
        settings=settings,
        audit=audit,
        assets=assets,
        categories=categories,
        counterparties=counterparties,
        bank_imports=bank_imports,
        accounts=accounts,
        transactions=transactions,
        reporting=reporting,
        reconciliation=ReconciliationService(db, categories, transactions),
        reserves=reserves,
        reevaluations=reevaluations,
        money_from_others=money_from_others,
        physical_items=physical_items,
        budgets=budgets,
        investments=investments,
        deposits=deposits,
        account_flows=AccountWorkflows(db, accounts, transactions, reporting),
        integrity=IntegrityService(reporting, reserves, budgets, planning),
        planning=planning,
        forecaster=forecaster,
        position=position,
        backup_dir=backup_dir,
    )
