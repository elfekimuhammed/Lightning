"""Starter data: asset-class tree, cash assets, and a category tree.

Idempotent: rows are inserted only if their code does not exist yet, so user edits
(renames, deactivations) are never overwritten. Everything here is editable in the app.
"""

from __future__ import annotations

from lightning.core.dates import now_iso

from .connection import Database
from .settings import DEFAULTS, SettingsStore

# (code, name) — parent is derived from the dotted path
ASSET_CLASSES: list[tuple[str, str]] = [
    ("CASH", "Liquid Cash"),
    ("CASH.PHYSICAL", "Physical Cash"),
    ("CASH.BANK", "Bank Balance"),
    ("CASH.BROKERAGE", "Brokerage Cash"),
    ("DEPOSIT", "Deposits"),
    ("DEPOSIT.CD", "CDs / Time Deposits"),
    ("STOCK", "Stocks"),
    ("FUND", "Funds"),
    ("FUND.EQUITY", "Equity Fund"),
    ("FUND.MONEY_MARKET", "Money Market Fund"),
    ("FUND.GOLD", "Gold Fund"),
    ("FUND.OTHER", "Other Fund"),
    ("GOLD", "Gold"),
    ("OTHER", "Other Investments"),
    ("RECEIVABLE", "Money Owed to You"),
]

# (code, name, unit) — one cash asset per currency
CASH_ASSETS: list[tuple[str, str]] = [
    ("EGP", "Egyptian Pound"),
    ("USD", "US Dollar"),
    ("EUR", "Euro"),
    ("GBP", "British Pound"),
    ("SAR", "Saudi Riyal"),
    ("AED", "UAE Dirham"),
]

# (code, name, extra) — movement/scope/income_class inherit from the parent unless given
CATEGORIES: list[tuple[str, str, dict]] = [
    ("INC", "Income", {"movement": "INFLOW", "income_class": "HOUSEHOLD"}),
    ("INC.SALARY", "Salary", {}),
    ("INC.BONUS", "Bonus", {}),
    ("INC.BUSINESS", "Business & Freelance", {}),
    ("INC.GIFT", "Gifts Received", {}),
    ("INC.OTHER", "Other Income", {}),
    ("INC.INVEST", "Investment Income", {"income_class": "INVESTMENT"}),
    ("INC.INVEST.INTEREST", "Interest", {}),
    ("INC.INVEST.DIVIDEND", "Dividends", {}),
    ("INC.UNACCOUNTED", "Unaccounted Money Found", {"is_system": 1}),
    ("EXP", "Expenses", {"movement": "OUTFLOW"}),
    ("EXP.PERSONAL", "Personal", {"scope": "PERSONAL"}),
    ("EXP.PERSONAL.FOOD", "Food & Groceries", {}),
    ("EXP.PERSONAL.DINING", "Eating Out", {}),
    ("EXP.PERSONAL.TRANSPORT", "Transportation", {}),
    ("EXP.PERSONAL.HOUSING", "Housing & Rent", {}),
    ("EXP.PERSONAL.UTILITIES", "Utilities & Bills", {}),
    ("EXP.PERSONAL.HEALTH", "Health", {}),
    ("EXP.PERSONAL.SHOPPING", "Shopping", {}),
    ("EXP.PERSONAL.ENTERTAINMENT", "Entertainment", {}),
    ("EXP.PERSONAL.EDUCATION", "Education", {}),
    ("EXP.PERSONAL.TRAVEL", "Travel", {}),
    ("EXP.PERSONAL.GIFTS", "Gifts & Donations", {}),
    ("EXP.PERSONAL.OTHER", "Other Personal", {}),
    ("EXP.WORK", "Work", {"scope": "WORK", "default_reimbursable": 1}),
    ("EXP.WORK.TRANSPORT", "Transportation", {}),
    ("EXP.WORK.SOFTWARE", "Software", {}),
    ("EXP.WORK.MEALS", "Meals", {}),
    ("EXP.WORK.OFFICE", "Office Supplies", {}),
    ("EXP.WORK.TRAVEL", "Travel", {}),
    ("EXP.WORK.OTHER", "Other Work", {}),
    ("EXP.FEES", "Fees & Charges", {"scope": "PERSONAL"}),
    ("EXP.FEES.BANK", "Bank Fees", {}),
    ("EXP.FEES.INTEREST", "Interest Paid", {}),
    ("EXP.TAX", "Taxes", {"scope": "PERSONAL"}),
    ("EXP.UNACCOUNTED", "Unaccounted Spending", {"scope": "PERSONAL", "is_system": 1}),
]


def _parent_id(db: Database, table: str, code: str) -> int | None:
    if "." not in code:
        return None
    parent_code = code.rsplit(".", 1)[0]
    return db.scalar(f"SELECT id FROM {table} WHERE code = ?", (parent_code,))


def seed(db: Database) -> None:
    now = now_iso()
    with db.transaction():
        settings = SettingsStore(db)
        for key, value in DEFAULTS.items():
            if db.scalar("SELECT 1 FROM settings WHERE key = ?", (key,)) is None:
                settings.set(key, value)

        for order, (code, name) in enumerate(ASSET_CLASSES):
            if db.scalar("SELECT 1 FROM asset_classes WHERE code = ?", (code,)):
                continue
            db.execute(
                "INSERT INTO asset_classes(code, name, parent_id, sort_order, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (code, name, _parent_id(db, "asset_classes", code), order, now, now),
            )

        cash_class = db.scalar("SELECT id FROM asset_classes WHERE code = 'CASH'")
        for currency, name in CASH_ASSETS:
            code = f"CASH:{currency}"
            if db.scalar("SELECT 1 FROM financial_assets WHERE code = ?", (code,)):
                continue
            db.execute(
                "INSERT INTO financial_assets(code, name, asset_class_id, currency, unit, quantity_decimals,"
                " is_cash, exposure, liquidity, price_source, created_at, updated_at)"
                " VALUES (?,?,?,?,?,2,1,'CASH','IMMEDIATE','NONE',?,?)",
                (code, name, cash_class, currency, currency, now, now),
            )

        for order, (code, name, extra) in enumerate(CATEGORIES):
            if db.scalar("SELECT 1 FROM categories WHERE code = ?", (code,)):
                continue
            parent_id = _parent_id(db, "categories", code)
            parent = (
                db.one("SELECT * FROM categories WHERE id = ?", (parent_id,)) if parent_id else None
            )
            movement = extra.get("movement") or (parent["movement"] if parent else None)
            scope = extra.get("scope", parent["scope"] if parent else None)
            income_class = extra.get("income_class", parent["income_class"] if parent else None)
            reimb = extra.get(
                "default_reimbursable", parent["default_reimbursable"] if parent else 0
            )
            db.execute(
                "INSERT INTO categories(code, name, parent_id, movement, scope, income_class,"
                " default_reimbursable, is_system, sort_order, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    code,
                    name,
                    parent_id,
                    movement,
                    scope if movement == "OUTFLOW" else None,
                    income_class if movement == "INFLOW" else None,
                    reimb,
                    extra.get("is_system", 0),
                    order,
                    now,
                    now,
                ),
            )
