CREATE TABLE reevaluation_suppressed_accounts (
    period_id INTEGER NOT NULL REFERENCES reevaluation_periods(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (period_id, account_id)
);
