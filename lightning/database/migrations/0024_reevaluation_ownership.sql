DROP INDEX ix_reevaluation_asset_date;
DROP INDEX ix_reevaluation_journal;
ALTER TABLE reevaluation_entries RENAME TO reevaluation_entries_before_owner;
CREATE TABLE reevaluation_entries (
    id INTEGER PRIMARY KEY,
    period_id INTEGER NOT NULL REFERENCES reevaluation_periods(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
    units_e6 INTEGER NOT NULL,
    price_e6 INTEGER,
    currency TEXT NOT NULL,
    value_base_e6 INTEGER,
    return_base_e6 INTEGER,
    price_source TEXT NOT NULL DEFAULT '',
    needs_price INTEGER NOT NULL DEFAULT 0 CHECK (needs_price IN (0,1)),
    journal_transaction_id INTEGER REFERENCES transactions(id),
    owner_id INTEGER REFERENCES counterparties(id)
);
INSERT INTO reevaluation_entries(id,period_id,account_id,asset_id,units_e6,price_e6,currency,value_base_e6,
                                 return_base_e6,price_source,needs_price,journal_transaction_id,owner_id)
SELECT id,period_id,account_id,asset_id,units_e6,price_e6,currency,value_base_e6,return_base_e6,price_source,
       needs_price,journal_transaction_id,NULL FROM reevaluation_entries_before_owner;
DROP TABLE reevaluation_entries_before_owner;
CREATE INDEX ix_reevaluation_asset_date ON reevaluation_entries(asset_id,period_id);
CREATE INDEX ix_reevaluation_journal ON reevaluation_entries(journal_transaction_id);
CREATE UNIQUE INDEX ix_reevaluation_asset_owner ON reevaluation_entries(
    period_id,account_id,asset_id,COALESCE(owner_id,-1));
