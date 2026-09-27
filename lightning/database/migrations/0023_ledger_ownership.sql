ALTER TABLE ledger_entries ADD COLUMN owner_id INTEGER REFERENCES counterparties(id);
CREATE INDEX ix_ledger_owner_balance ON ledger_entries(account_id, asset_id, owner_id, date);
