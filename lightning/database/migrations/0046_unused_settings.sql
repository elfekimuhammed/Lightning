-- Two settings nothing reads any more: the app's name (fixed in the code) and the investment
-- liquidation factor, which migration 0029 moved into investment_liquidation_factors.
DELETE FROM settings WHERE key IN ('app_name', 'investment_liquidation_factor');
