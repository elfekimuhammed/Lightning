-- Add value-only REVALUATION postings and the per-asset checkpoint detail.
-- Existing row IDs and all current ledger columns are copied unchanged.
DROP VIEW IF EXISTS v_ledger;
DROP VIEW IF EXISTS v_balances;
DROP INDEX IF EXISTS ix_ledger_account_date;
DROP INDEX IF EXISTS ix_ledger_asset_date;
DROP INDEX IF EXISTS ix_ledger_category_date;
DROP INDEX IF EXISTS ix_ledger_transaction;
ALTER TABLE ledger_entries RENAME TO ledger_entries_before_reevaluation;
CREATE TABLE ledger_entries (
    id INTEGER PRIMARY KEY,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    date TEXT NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
    quantity_e6 INTEGER NOT NULL,
    unit_price_e6 INTEGER NOT NULL,
    amount_e6 INTEGER NOT NULL,
    fx_rate_e6 INTEGER NOT NULL,
    amount_base_e6 INTEGER NOT NULL,
    effect TEXT NOT NULL CHECK (effect IN ('INFLOW','OUTFLOW','INTERNAL','OPENING','REVALUATION')),
    category_id INTEGER REFERENCES categories(id),
    memo TEXT NOT NULL DEFAULT '',
    UNIQUE(transaction_id,line_no),
    CHECK (effect='REVALUATION' OR quantity_e6<>0),
    CHECK (effect NOT IN ('INFLOW','OUTFLOW') OR category_id IS NOT NULL)
);
INSERT INTO ledger_entries(id,transaction_id,line_no,date,account_id,asset_id,quantity_e6,unit_price_e6,
                           amount_e6,fx_rate_e6,amount_base_e6,effect,category_id,memo)
SELECT id,transaction_id,line_no,date,account_id,asset_id,quantity_e6,unit_price_e6,amount_e6,fx_rate_e6,
       amount_base_e6,effect,category_id,memo FROM ledger_entries_before_reevaluation;
CREATE TEMP TABLE _reeval_copy_check(ok INTEGER CHECK(ok=1));
INSERT INTO _reeval_copy_check SELECT
    (SELECT COUNT(*) FROM ledger_entries_before_reevaluation)=(SELECT COUNT(*) FROM ledger_entries);
DROP TABLE _reeval_copy_check;
DROP TABLE ledger_entries_before_reevaluation;
CREATE INDEX ix_ledger_account_date ON ledger_entries(account_id,date);
CREATE INDEX ix_ledger_asset_date ON ledger_entries(asset_id,date);
CREATE INDEX ix_ledger_category_date ON ledger_entries(category_id,date);
CREATE INDEX ix_ledger_transaction ON ledger_entries(transaction_id);

CREATE VIEW v_ledger AS
SELECT t.ref || '/' || le.line_no AS line_ref,le.date AS date,t.type AS type,t.status AS status,
       a.code || ' · ' || a.name AS account,fa.code AS asset,
       printf('%.6f',le.quantity_e6/1000000.0) AS quantity,
       printf('%.2f',le.amount_e6/1000000.0) AS amount,fa.currency AS currency,
       printf('%.2f',le.amount_base_e6/1000000.0) AS amount_base,le.effect AS effect,
       CASE WHEN c.id IS NULL THEN '' ELSE c.code || ' · ' || c.name END AS category,
       t.description AS description,t.counterparty AS counterparty
FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id
JOIN accounts a ON a.id=le.account_id JOIN financial_assets fa ON fa.id=le.asset_id
LEFT JOIN categories c ON c.id=le.category_id;
CREATE VIEW v_balances AS
SELECT a.code || ' · ' || a.name AS account,fa.code AS asset,
       printf('%.2f',SUM(le.quantity_e6)/1000000.0) AS balance,fa.currency AS currency
FROM ledger_entries le JOIN transactions t ON t.id=le.transaction_id AND t.status='POSTED'
JOIN accounts a ON a.id=le.account_id JOIN financial_assets fa ON fa.id=le.asset_id
GROUP BY a.id,fa.id;

CREATE TABLE reevaluation_periods (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('MONTH_END','SALE')),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','POSTED')),
    created_at TEXT NOT NULL,
    UNIQUE(date,reason)
);
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
    UNIQUE(period_id,account_id,asset_id)
);
CREATE INDEX ix_reevaluation_asset_date ON reevaluation_entries(asset_id,period_id);
CREATE INDEX ix_reevaluation_journal ON reevaluation_entries(journal_transaction_id);
CREATE TABLE reevaluation_account_posts (
    period_id INTEGER NOT NULL REFERENCES reevaluation_periods(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
    amount_base_e6 INTEGER NOT NULL,
    PRIMARY KEY(period_id,account_id)
);
