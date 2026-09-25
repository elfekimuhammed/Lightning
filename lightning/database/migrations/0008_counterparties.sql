-- Canonical counterparties and reusable spellings/categories for monthly imports.
CREATE TABLE counterparties (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    default_category_id INTEGER REFERENCES categories(id),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE counterparty_aliases (
    id INTEGER PRIMARY KEY,
    counterparty_id INTEGER NOT NULL REFERENCES counterparties(id),
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

ALTER TABLE transactions ADD COLUMN counterparty_id INTEGER REFERENCES counterparties(id);
CREATE INDEX ix_transactions_counterparty ON transactions(counterparty_id);

-- Staging retains source rows and makes preview/review and idempotent re-upload possible.
CREATE TABLE bank_import_batches (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    file_hash TEXT NOT NULL,
    file_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('REVIEW','POSTED','CANCELLED')),
    created_at TEXT NOT NULL,
    posted_at TEXT,
    UNIQUE (account_id, file_hash)
);

CREATE TABLE bank_import_rows (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES bank_import_batches(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    bank_reference TEXT,
    transaction_id INTEGER REFERENCES transactions(id),
    status TEXT NOT NULL CHECK (status IN ('REVIEW','POSTED','DUPLICATE','SKIPPED')),
    UNIQUE (batch_id, row_number)
);
CREATE INDEX ix_bank_import_reference ON bank_import_rows(bank_reference) WHERE bank_reference IS NOT NULL;
