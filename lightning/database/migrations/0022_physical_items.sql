CREATE TABLE physical_items (
    asset_id INTEGER PRIMARY KEY REFERENCES financial_assets(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    item_kind TEXT NOT NULL,
    net_gold_grams_e6 INTEGER NOT NULL CHECK (net_gold_grams_e6 > 0),
    karat INTEGER NOT NULL CHECK (karat IN (18,21,22,24)),
    reference_asset_id INTEGER NOT NULL REFERENCES financial_assets(id),
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX ix_physical_items_account ON physical_items(account_id, asset_id);

CREATE TABLE physical_item_valuations (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES physical_items(asset_id),
    date TEXT NOT NULL,
    quantity_e6 INTEGER NOT NULL CHECK (quantity_e6 > 0),
    total_value_e6 INTEGER NOT NULL CHECK (total_value_e6 >= 0),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX ix_physical_item_valuation_date ON physical_item_valuations(asset_id, date);

CREATE TABLE physical_item_trade_details (
    transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id),
    asset_id INTEGER NOT NULL REFERENCES physical_items(asset_id),
    action TEXT NOT NULL CHECK (action IN ('BUY','SEL','OPN')),
    workmanship_cost_e6 INTEGER NOT NULL DEFAULT 0 CHECK (workmanship_cost_e6 >= 0),
    notes TEXT NOT NULL DEFAULT ''
);
