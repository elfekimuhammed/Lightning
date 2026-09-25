"""Category workflows: a rename also refreshes search text of affected transactions."""

from __future__ import annotations

from lightning.categories.service import CategoryService
from lightning.database.connection import Database
from lightning.transactions.service import TransactionService


class CategoryWorkflows:
    def __init__(self, db: Database, categories: CategoryService, transactions: TransactionService):
        self.db = db
        self.categories = categories
        self.transactions = transactions

    def update_category(self, category_id: int, name: str, code: str | None = None, active: bool = True,
                        default_reimbursable: bool | None = None) -> None:
        with self.db.transaction():
            changed = self.categories.update(category_id, name=name, code=code, active=active,
                                             default_reimbursable=default_reimbursable)
            self.transactions.rebuild_search_for_categories(changed)
