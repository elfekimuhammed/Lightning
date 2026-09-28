ALTER TABLE cash_reserves ADD COLUMN account_id INTEGER REFERENCES accounts(id);
CREATE INDEX ix_cash_reserves_account ON cash_reserves(account_id,status);
