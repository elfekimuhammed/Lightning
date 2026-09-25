-- Another person's cash is custody, not an asset belonging to the user.
CREATE TABLE money_from_others (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    owner TEXT NOT NULL DEFAULT '',
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    amount_e6 INTEGER NOT NULL CHECK (amount_e6 <> 0),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX ix_money_from_others_account_date ON money_from_others(account_id,date,id);
UPDATE accounts SET account_type='OTHER_ASSET', cash_class_id=(SELECT id FROM asset_classes WHERE code='OTHER') WHERE account_type='RECEIVABLE';
UPDATE asset_classes SET name='Other (archived)', code='OTHER.ARCHIVED', active=0 WHERE code='RECEIVABLE';
