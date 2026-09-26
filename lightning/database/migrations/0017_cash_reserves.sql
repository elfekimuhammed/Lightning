CREATE TABLE cash_reserves (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('EMERGENCY','PROJECT')),
    target_e6 INTEGER NOT NULL CHECK (target_e6 > 0),
    allocated_e6 INTEGER NOT NULL DEFAULT 0 CHECK (allocated_e6 >= 0),
    due_date TEXT CHECK (due_date IS NULL OR due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','COMPLETE')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_active_emergency_reserve ON cash_reserves(kind) WHERE kind='EMERGENCY' AND status='ACTIVE';
CREATE INDEX ix_cash_reserves_status_due ON cash_reserves(status,due_date);
