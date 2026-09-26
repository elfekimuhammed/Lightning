ALTER TABLE ledger_entries ADD COLUMN cleared INTEGER NOT NULL DEFAULT 0 CHECK (cleared IN (0, 1));
UPDATE ledger_entries SET cleared=1
WHERE transaction_id IN (SELECT id FROM transactions WHERE type='OPN' AND status='POSTED');
CREATE INDEX ix_ledger_account_cleared ON ledger_entries(account_id, cleared, date);
