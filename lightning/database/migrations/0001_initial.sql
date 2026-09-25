-- Lightning schema v1 (M0/M1)
-- Conventions:
--   * ids are internal integers; people use `code` (master data) and `ref` (documents)
--   * dates are TEXT 'yyyy-mm-dd'; timestamps are TEXT ISO-8601 with offset
--   * money/quantities are INTEGER scaled by 1,000,000 (suffix _e6) so SUM() is exact;
--     the v_* views show normal decimals for people browsing the file

CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- What wealth consists of: an editable tree (Liquid Cash > Bank Balance, Funds > Gold Fund, ...)
CREATE TABLE asset_classes (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES asset_classes(id),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- A specific thing you can own a quantity of (EGP cash, COMI shares, 21K gold grams, ...)
CREATE TABLE financial_assets (
    id                 INTEGER PRIMARY KEY,
    code               TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    asset_class_id     INTEGER NOT NULL REFERENCES asset_classes(id),
    currency           TEXT NOT NULL CHECK (length(currency) = 3),
    unit               TEXT NOT NULL,
    quantity_decimals  INTEGER NOT NULL CHECK (quantity_decimals BETWEEN 0 AND 6),
    is_cash            INTEGER NOT NULL DEFAULT 0 CHECK (is_cash IN (0, 1)),
    exposure           TEXT NOT NULL CHECK (exposure IN ('CASH','EQUITY','GOLD','FIXED_INCOME','REAL_ESTATE','OTHER')),
    liquidity          TEXT NOT NULL CHECK (liquidity IN ('IMMEDIATE','DAYS','LOCKED')),
    purity_e6          INTEGER,
    isin               TEXT,
    price_source       TEXT NOT NULL DEFAULT 'NONE' CHECK (price_source IN ('YAHOO','GOLD_CALC','GOLD_LOCAL','MANUAL','NONE')),
    external_symbol    TEXT,
    active             INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    notes              TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_financial_assets_cash_currency ON financial_assets(currency) WHERE is_cash = 1;
CREATE INDEX ix_financial_assets_class ON financial_assets(asset_class_id);

-- Where value is held
CREATE TABLE accounts (
    id             INTEGER PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    institution    TEXT NOT NULL DEFAULT '',
    account_type   TEXT NOT NULL CHECK (account_type IN
                     ('CASH','BANK','DEPOSIT','BROKERAGE','PHYSICAL_ASSET','RECEIVABLE','OTHER_ASSET',
                      'CREDIT_CARD','LOAN','PAYABLE')),
    currency       TEXT NOT NULL CHECK (length(currency) = 3),
    cash_class_id  INTEGER NOT NULL REFERENCES asset_classes(id),
    opening_date   TEXT NOT NULL CHECK (opening_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    is_system      INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
    last4          TEXT CHECK (last4 IS NULL OR (length(last4) = 4 AND last4 GLOB '[0-9][0-9][0-9][0-9]')),
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    sort_order     INTEGER NOT NULL DEFAULT 0,
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX ix_accounts_type ON accounts(account_type);

-- Why money moved: an editable tree (Expenses > Personal > Food, Income > Salary, ...)
CREATE TABLE categories (
    id                    INTEGER PRIMARY KEY,
    code                  TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    parent_id             INTEGER REFERENCES categories(id),
    movement              TEXT NOT NULL CHECK (movement IN ('INFLOW','OUTFLOW')),
    scope                 TEXT CHECK (scope IS NULL OR scope IN ('PERSONAL','WORK')),
    income_class          TEXT CHECK (income_class IS NULL OR income_class IN ('HOUSEHOLD','INVESTMENT')),
    default_reimbursable  INTEGER NOT NULL DEFAULT 0 CHECK (default_reimbursable IN (0, 1)),
    is_system             INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
    active                INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    sort_order            INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX ix_categories_parent ON categories(parent_id);

-- The document the user sees (one transfer = one row here)
CREATE TABLE transactions (
    id               INTEGER PRIMARY KEY,
    ref              TEXT NOT NULL UNIQUE,
    type             TEXT NOT NULL CHECK (type IN ('OPN','IN','OUT','TRF','CNV','BUY','SEL','DIV','VAL','ADJ')),
    date             TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    description      TEXT NOT NULL DEFAULT '',
    counterparty     TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','VOID')),
    source           TEXT NOT NULL DEFAULT 'MANUAL' CHECK (source IN ('MANUAL','IMPORT','MARKET_DATA','SYSTEM')),
    import_batch_id  INTEGER,
    notes            TEXT NOT NULL DEFAULT '',
    search_text      TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX ix_transactions_date ON transactions(date);
CREATE INDEX ix_transactions_type_date ON transactions(type, date);
CREATE INDEX ix_transactions_status ON transactions(status);

-- The effect: every balance and report is derived from these lines only
CREATE TABLE ledger_entries (
    id              INTEGER PRIMARY KEY,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    line_no         INTEGER NOT NULL,
    date            TEXT NOT NULL,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    asset_id        INTEGER NOT NULL REFERENCES financial_assets(id),
    quantity_e6     INTEGER NOT NULL,
    unit_price_e6   INTEGER NOT NULL,
    amount_e6       INTEGER NOT NULL,
    fx_rate_e6      INTEGER NOT NULL,
    amount_base_e6  INTEGER NOT NULL,
    effect          TEXT NOT NULL CHECK (effect IN ('INFLOW','OUTFLOW','INTERNAL','OPENING')),
    category_id     INTEGER REFERENCES categories(id),
    claim_id        INTEGER,
    memo            TEXT NOT NULL DEFAULT '',
    UNIQUE (transaction_id, line_no),
    CHECK (effect NOT IN ('INFLOW','OUTFLOW') OR category_id IS NOT NULL)
);
CREATE INDEX ix_ledger_account_date  ON ledger_entries(account_id, date);
CREATE INDEX ix_ledger_asset_date    ON ledger_entries(asset_id, date);
CREATE INDEX ix_ledger_category_date ON ledger_entries(category_id, date);
CREATE INDEX ix_ledger_transaction   ON ledger_entries(transaction_id);

-- Prices and FX (filled from M3/M4; created now so valuation logic has one shape)
CREATE TABLE price_history (
    id          INTEGER PRIMARY KEY,
    asset_id    INTEGER NOT NULL REFERENCES financial_assets(id),
    date        TEXT NOT NULL,
    price_e6    INTEGER NOT NULL CHECK (price_e6 >= 0),
    currency    TEXT NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE (asset_id, date, source)
);
CREATE INDEX ix_price_asset_date ON price_history(asset_id, date);

CREATE TABLE fx_rates (
    id          INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,
    base        TEXT NOT NULL,
    quote       TEXT NOT NULL,
    rate_e6     INTEGER NOT NULL CHECK (rate_e6 > 0),
    source      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (date, base, quote, source)
);

-- Every edit and void keeps a before/after record
CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    at           TEXT NOT NULL,
    entity       TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    action       TEXT NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    before_json  TEXT,
    after_json   TEXT
);
CREATE INDEX ix_audit_entity ON audit_log(entity, entity_id);
