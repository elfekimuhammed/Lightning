ALTER TABLE cash_reserves ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'NONE'
    CHECK (recurrence IN ('NONE','WEEKLY','MONTHLY','YEARLY'));
ALTER TABLE cash_reserves ADD COLUMN recurrence_day INTEGER
    CHECK (recurrence_day IS NULL OR recurrence_day BETWEEN 1 AND 31);
