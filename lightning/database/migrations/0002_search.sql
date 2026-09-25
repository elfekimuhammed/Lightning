-- @optional
-- Full-text search over each transaction's one-line summary.
-- Requires SQLite FTS5 (bundled with standard Python). If unavailable, the app
-- skips this migration and falls back to LIKE search.

CREATE VIRTUAL TABLE transactions_fts USING fts5(
    search_text,
    content = 'transactions',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER transactions_fts_insert AFTER INSERT ON transactions BEGIN
    INSERT INTO transactions_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;

CREATE TRIGGER transactions_fts_delete AFTER DELETE ON transactions BEGIN
    INSERT INTO transactions_fts(transactions_fts, rowid, search_text) VALUES ('delete', old.id, old.search_text);
END;

CREATE TRIGGER transactions_fts_update AFTER UPDATE OF search_text ON transactions BEGIN
    INSERT INTO transactions_fts(transactions_fts, rowid, search_text) VALUES ('delete', old.id, old.search_text);
    INSERT INTO transactions_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;
