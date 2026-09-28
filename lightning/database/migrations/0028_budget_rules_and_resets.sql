-- Additive Budget rule support; existing amounts and monthly history stay intact.
ALTER TABLE budgets ADD COLUMN income_percent_e6 INTEGER CHECK (income_percent_e6 IS NULL OR income_percent_e6 >= 0);
CREATE TABLE budget_carryover_resets (
    category_id INTEGER NOT NULL REFERENCES categories(id),
    month TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(category_id, month)
);
CREATE INDEX ix_budget_carryover_resets_month ON budget_carryover_resets(category_id, month);
