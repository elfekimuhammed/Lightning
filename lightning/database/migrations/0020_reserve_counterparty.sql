ALTER TABLE cash_reserves ADD COLUMN counterparty_id INTEGER REFERENCES counterparties(id);
CREATE INDEX ix_cash_reserves_counterparty ON cash_reserves(counterparty_id,status);
