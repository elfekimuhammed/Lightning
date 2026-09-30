-- 0034 — cash planning (2026-09-30)
--   * planned_items: recurring bills, subscriptions and income, and loans / installment plans.
--     Amounts are positive per payment; the kind gives the direction (INCOME comes in, the rest go out).
--     A schedule is a frequency (every `interval_count` weeks/months/…), a first date, and an
--     optional end date or number of payments (loans).
--   * planned_payments: which scheduled payment was settled, and by which posted transaction.
--     A payment is PAID (linked to a transaction) or SKIPPED (the user says it will not happen).
-- Nothing here posts to the ledger. Only unpaid due payments and loans still to pay count as
-- what you owe; forecasts never change net worth or free cash.

CREATE TABLE planned_items (
    id             INTEGER PRIMARY KEY,
    kind           TEXT NOT NULL CHECK (kind IN ('BILL','SUBSCRIPTION','INCOME','LOAN')),
    name           TEXT NOT NULL CHECK (length(trim(name)) > 0),
    amount_e6      INTEGER NOT NULL CHECK (amount_e6 > 0),
    frequency      TEXT NOT NULL CHECK (frequency IN ('ONCE','WEEKLY','MONTHLY','QUARTERLY','YEARLY')),
    interval_count INTEGER NOT NULL DEFAULT 1 CHECK (interval_count BETWEEN 1 AND 52),
    start_date     TEXT NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    end_date       TEXT CHECK (end_date IS NULL OR end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    payment_count  INTEGER CHECK (payment_count IS NULL OR payment_count BETWEEN 1 AND 600),
    account_id     INTEGER REFERENCES accounts(id),
    category_id    INTEGER REFERENCES categories(id),
    counterparty_id INTEGER REFERENCES counterparties(id),
    principal_e6   INTEGER CHECK (principal_e6 IS NULL OR principal_e6 > 0),
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    CHECK (kind <> 'LOAN' OR payment_count IS NOT NULL OR end_date IS NOT NULL)
);
CREATE INDEX ix_planned_items_active ON planned_items(active, kind);

CREATE TABLE planned_payments (
    id              INTEGER PRIMARY KEY,
    planned_item_id INTEGER NOT NULL REFERENCES planned_items(id) ON DELETE CASCADE,
    due_date        TEXT NOT NULL CHECK (due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status          TEXT NOT NULL CHECK (status IN ('PAID','SKIPPED')),
    transaction_id  INTEGER REFERENCES transactions(id),
    amount_e6       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    UNIQUE (planned_item_id, due_date),
    CHECK (status <> 'PAID' OR transaction_id IS NOT NULL)
);
CREATE UNIQUE INDEX ux_planned_payments_transaction ON planned_payments(transaction_id)
    WHERE transaction_id IS NOT NULL;
