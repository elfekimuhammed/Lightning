-- Task 20: a statement row can be LINKED to a transaction you already recorded,
-- instead of being skipped (losing its provenance) or posted twice. A link moves
-- no money. One imported row per account at most stands behind each transaction,
-- so two equal purchases can never both claim the same entry; a transfer between
-- two of your accounts can still be backed by each bank's statement once.
DROP INDEX ix_bank_import_reference;
ALTER TABLE bank_import_rows RENAME TO bank_import_rows_before_links;
CREATE TABLE bank_import_rows (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES bank_import_batches(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    bank_reference TEXT,
    transaction_id INTEGER REFERENCES transactions(id),
    status TEXT NOT NULL CHECK (status IN ('REVIEW','POSTED','LINKED','DUPLICATE','SKIPPED')),
    UNIQUE (batch_id, row_number)
);
INSERT INTO bank_import_rows(id,batch_id,account_id,row_number,raw_json,bank_reference,transaction_id,status)
SELECT r.id,r.batch_id,b.account_id,r.row_number,r.raw_json,r.bank_reference,r.transaction_id,r.status
FROM bank_import_rows_before_links r JOIN bank_import_batches b ON b.id=r.batch_id;
DROP TABLE bank_import_rows_before_links;
CREATE INDEX ix_bank_import_reference ON bank_import_rows(bank_reference) WHERE bank_reference IS NOT NULL;
CREATE UNIQUE INDEX ux_bank_import_transaction ON bank_import_rows(transaction_id, account_id)
    WHERE status IN ('POSTED','LINKED');
