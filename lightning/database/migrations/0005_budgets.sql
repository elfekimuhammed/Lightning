-- 0005 — budgets (2026-09-25)
-- A budget is a monthly amount for a money-out category (or a group such as Personal).
--   * repeat until changed: a row applies from `month` onward, until a later row for the same category
--   * one_off = 1: applies to that single month only and wins over the repeating amount
--   * amount_e6 NULL = "no budget" from that month onward (or for that month, if one_off)
-- Actual spending is never stored here — it always comes from the ledger.

CREATE TABLE budgets (
    id           INTEGER PRIMARY KEY,
    category_id  INTEGER NOT NULL REFERENCES categories(id),
    month        TEXT NOT NULL CHECK (month GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]'),
    one_off      INTEGER NOT NULL DEFAULT 0 CHECK (one_off IN (0, 1)),
    amount_e6    INTEGER CHECK (amount_e6 IS NULL OR amount_e6 >= 0),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (category_id, month, one_off)
);
CREATE INDEX ix_budgets_category_month ON budgets(category_id, month);

CREATE VIEW v_budgets AS
SELECT c.code || ' · ' || c.name AS category,
       b.month,
       CASE b.one_off WHEN 1 THEN 'this month only' ELSE 'from this month' END AS applies,
       CASE WHEN b.amount_e6 IS NULL THEN 'no budget' ELSE printf('%.2f', b.amount_e6 / 1000000.0) END AS amount
FROM budgets b JOIN categories c ON c.id = b.category_id
ORDER BY c.code, b.month;
