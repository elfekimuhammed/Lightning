-- The budget's separate spending ceiling became the Savings rate limit in Financial health (owner
-- request 2026-10-05: a budget must leave the savings rate you set, so the two are one number). A
-- ceiling below 100% of income carries over as the savings target it implied, unless a savings limit
-- was already chosen; the old setting is then removed.
INSERT INTO settings (key, value, updated_at)
SELECT 'financial_health_limit_savings_rate', printf('%g', round(100 - CAST(value AS REAL), 1)),
       strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
FROM settings
WHERE key = 'budget_monthly_ceiling_percent'
  AND CAST(value AS REAL) >= 0 AND CAST(value AS REAL) < 100
  AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'financial_health_limit_savings_rate');
DELETE FROM settings WHERE key = 'budget_monthly_ceiling_percent';
