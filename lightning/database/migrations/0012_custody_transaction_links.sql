-- Link custody cash adjustments to their source transaction, and track investments
-- beneficially owned by someone else without removing them from account holdings.
ALTER TABLE money_from_others ADD COLUMN transaction_id INTEGER REFERENCES transactions(id);
CREATE INDEX ix_money_from_others_transaction
    ON money_from_others(transaction_id) WHERE transaction_id IS NOT NULL;

CREATE TABLE investment_custody_events (
    id INTEGER PRIMARY KEY,
    transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    owner TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
    units_e6 INTEGER NOT NULL CHECK (units_e6 <> 0),
    created_at TEXT NOT NULL
);
CREATE INDEX ix_investment_custody_position
    ON investment_custody_events(account_id, asset_id, owner, date);

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,created_at,updated_at)
SELECT 'EXP.PERSONAL.CUSTODY','Money Held for Others',id,'INFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,999,datetime('now'),datetime('now')
FROM categories p
WHERE p.code='EXP.PERSONAL'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.PERSONAL.CUSTODY');
