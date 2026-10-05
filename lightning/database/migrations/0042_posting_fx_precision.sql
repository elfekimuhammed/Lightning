ALTER TABLE ledger_entries ADD COLUMN fx_rate_e12 INTEGER NOT NULL DEFAULT 1000000000000
    CHECK (fx_rate_e12 > 0);
UPDATE ledger_entries SET fx_rate_e12 = fx_rate_e6 * 1000000;
