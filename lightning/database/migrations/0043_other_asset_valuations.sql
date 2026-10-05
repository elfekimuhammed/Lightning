CREATE TABLE other_asset_valuations (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    effective_date TEXT NOT NULL,
    value_e6 INTEGER NOT NULL CHECK (value_e6 >= 0),
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, effective_date)
);
CREATE INDEX ix_other_asset_valuations_account_date
    ON other_asset_valuations(account_id, effective_date DESC);
