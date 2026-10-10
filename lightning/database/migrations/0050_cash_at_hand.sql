-- 0050 — distinguish cash held in hand from e-wallet accounts.
ALTER TABLE accounts ADD COLUMN cash_at_hand INTEGER NOT NULL DEFAULT 0
    CHECK (cash_at_hand IN (0, 1));
