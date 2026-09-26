CREATE TABLE reserve_transaction_links (
    id INTEGER PRIMARY KEY,
    reserve_id INTEGER NOT NULL REFERENCES cash_reserves(id) ON DELETE CASCADE,
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    amount_e6 INTEGER NOT NULL CHECK (amount_e6 > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(reserve_id,transaction_id)
);
CREATE INDEX ix_reserve_transaction_links_txn ON reserve_transaction_links(transaction_id);
CREATE TRIGGER tr_ledger_edit_clears_reserve_links
AFTER DELETE ON ledger_entries
BEGIN
    DELETE FROM reserve_transaction_links WHERE transaction_id=OLD.transaction_id;
END;
