-- Financial assets say where they trade (owner's request, 2026-10-05): the venue as an ISO 10383 MIC
-- (XCAI is the Egyptian Exchange, shown as EGX), the country as ISO 3166 alpha-2, and the key of the
-- instrument in the market file once matched. Stocks recorded so far are EGX listings and funds are
-- Egyptian. docs/proposals/market_data.md › Financial assets in the app.
ALTER TABLE financial_assets ADD COLUMN mic TEXT;
ALTER TABLE financial_assets ADD COLUMN country TEXT;
ALTER TABLE financial_assets ADD COLUMN market_key TEXT;
UPDATE financial_assets SET mic = 'XCAI', country = 'EG', market_key = 'EG:' || substr(code, 5) WHERE code LIKE 'STK:%';
UPDATE financial_assets SET country = 'EG' WHERE code LIKE 'FND:%';
