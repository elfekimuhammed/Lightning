-- 0006 — simplification (2026-09-25), from the architecture review
--   * Search runs directly over transactions, accounts and categories at query time, so nothing derived
--     is stored: the full-text index, its triggers and the stored search_text column are removed.
--   * Columns reserved for far-off milestones are removed; each milestone adds what it uses:
--     ledger_entries.claim_id (reimbursements, M5), transactions.import_batch_id (imports, M7).
-- No financial data changes.

DROP TRIGGER IF EXISTS transactions_fts_insert;
DROP TRIGGER IF EXISTS transactions_fts_delete;
DROP TRIGGER IF EXISTS transactions_fts_update;
DROP TABLE IF EXISTS transactions_fts;

ALTER TABLE transactions DROP COLUMN search_text;
ALTER TABLE transactions DROP COLUMN import_batch_id;
ALTER TABLE ledger_entries DROP COLUMN claim_id;
