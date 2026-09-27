ALTER TABLE financial_assets ADD COLUMN allocation_bucket TEXT;
ALTER TABLE financial_assets ADD COLUMN investment_horizon TEXT;

CREATE TABLE investment_targets (
    bucket TEXT PRIMARY KEY,
    target_weight REAL NOT NULL CHECK(target_weight >= 0 AND target_weight <= 100),
    updated_at TEXT NOT NULL
);
