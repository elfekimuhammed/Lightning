CREATE TABLE investment_liquidation_factors (
    asset_class_id INTEGER PRIMARY KEY REFERENCES asset_classes(id),
    factor REAL NOT NULL CHECK(factor >= 0 AND factor <= 100)
);

INSERT INTO investment_liquidation_factors(asset_class_id, factor)
SELECT DISTINCT a.asset_class_id,
       CAST(COALESCE((SELECT value FROM settings WHERE key='investment_liquidation_factor'), '95') AS REAL)
FROM financial_assets a WHERE a.is_cash=0;

INSERT OR IGNORE INTO investment_liquidation_factors(asset_class_id, factor)
SELECT DISTINCT a.cash_class_id,
       CAST(COALESCE((SELECT value FROM settings WHERE key='investment_liquidation_factor'), '95') AS REAL)
FROM accounts a WHERE a.account_type IN ('DEPOSIT','OTHER_ASSET','PHYSICAL_ASSET');

INSERT OR IGNORE INTO investment_liquidation_factors(asset_class_id, factor)
SELECT id, CAST(COALESCE((SELECT value FROM settings WHERE key='investment_liquidation_factor'), '95') AS REAL)
FROM asset_classes WHERE code IN ('STOCK','FUND.EQUITY','FUND.MONEY_MARKET','FUND.FIXED_INCOME','FUND.GOLD','FUND.OTHER','GOLD','OTHER');
