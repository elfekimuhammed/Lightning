CREATE TABLE bank_import_column_maps (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    header_signature TEXT NOT NULL,
    mapping_json TEXT NOT NULL,
    invert_amount INTEGER NOT NULL DEFAULT 0 CHECK (invert_amount IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (account_id, header_signature)
);
