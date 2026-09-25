-- Human-readable views for anyone opening the database in a SQLite browser.
-- Display only: the app itself always computes with exact integers.

CREATE VIEW v_ledger AS
SELECT
    t.ref || '/' || le.line_no                  AS line_ref,
    le.date                                     AS date,
    t.type                                      AS type,
    t.status                                    AS status,
    a.code || ' · ' || a.name                   AS account,
    fa.code                                     AS asset,
    printf('%.6f', le.quantity_e6 / 1000000.0)  AS quantity,
    printf('%.2f', le.amount_e6 / 1000000.0)    AS amount,
    fa.currency                                 AS currency,
    printf('%.2f', le.amount_base_e6 / 1000000.0) AS amount_base,
    le.effect                                   AS effect,
    CASE WHEN c.id IS NULL THEN '' ELSE c.code || ' · ' || c.name END AS category,
    t.description                               AS description,
    t.counterparty                              AS counterparty
FROM ledger_entries le
JOIN transactions t      ON t.id = le.transaction_id
JOIN accounts a          ON a.id = le.account_id
JOIN financial_assets fa ON fa.id = le.asset_id
LEFT JOIN categories c   ON c.id = le.category_id;

CREATE VIEW v_balances AS
SELECT
    a.code || ' · ' || a.name                   AS account,
    fa.code                                     AS asset,
    printf('%.2f', SUM(le.quantity_e6) / 1000000.0) AS balance,
    fa.currency                                 AS currency
FROM ledger_entries le
JOIN transactions t      ON t.id = le.transaction_id AND t.status = 'POSTED'
JOIN accounts a          ON a.id = le.account_id
JOIN financial_assets fa ON fa.id = le.asset_id
GROUP BY a.id, fa.id;
