CREATE TABLE budget_carryover (
    category_id INTEGER NOT NULL REFERENCES categories(id),
    month TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (category_id, month)
);

CREATE INDEX idx_budget_carryover_month ON budget_carryover(month, category_id);
