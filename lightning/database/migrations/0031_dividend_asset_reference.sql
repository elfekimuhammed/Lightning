CREATE TABLE investment_dividend_assets (
    transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES financial_assets(id)
);

-- Only migrate legacy memo values that identify exactly one known asset code.
INSERT INTO investment_dividend_assets(transaction_id, asset_id)
SELECT DISTINCT le.transaction_id, fa.id
FROM ledger_entries le
JOIN transactions t ON t.id=le.transaction_id AND t.type='DIV'
JOIN financial_assets fa ON fa.code=le.memo AND fa.is_cash=0
WHERE (SELECT COUNT(*) FROM financial_assets match_asset
       WHERE match_asset.code=le.memo AND match_asset.is_cash=0)=1;
