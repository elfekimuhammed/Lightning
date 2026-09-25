-- 0007 — optional rolling-average budgets (2026-09-25)
-- NULL keeps existing manual behavior; 3/6 derives a budget from the preceding complete months.
ALTER TABLE budgets ADD COLUMN average_months INTEGER CHECK (average_months IN (3, 6));
