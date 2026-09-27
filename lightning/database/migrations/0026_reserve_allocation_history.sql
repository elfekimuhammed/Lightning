CREATE TABLE reserve_allocation_history (
    id INTEGER PRIMARY KEY,
    reserve_id INTEGER NOT NULL,
    created_date TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    allocated_e6 INTEGER NOT NULL CHECK (allocated_e6 >= 0),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','COMPLETE','DELETED'))
);
CREATE INDEX ix_reserve_allocation_history_day ON reserve_allocation_history(reserve_id,effective_date,id);
INSERT INTO reserve_allocation_history(reserve_id,created_date,effective_date,allocated_e6,status)
SELECT id, substr(created_at,1,10), date('now','localtime'), allocated_e6, status FROM cash_reserves;
