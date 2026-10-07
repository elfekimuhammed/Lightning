-- 0048 — rules with conditions (2026-10-06)
--   * rules: one rule per row; match_all says whether every condition must hold or any one. Rules run most
--     specific first (rules.engine.rank), then by position.
--   * rule_conditions: field (counterparty, notes, amount, account, direction), op and value; `value_to` is
--     the top of a "between" range. Amounts are absolute EGP as text, so 100 matches both -100 and +100.
--   * rule_actions: set a category, add a #tag to the notes, or split part of an expense into another
--     category (fixed amount or percent; the rest goes to the rule's category).
-- Rules only suggest: an import still waits for review, and a register row still shows its category
-- before it is saved. Nothing here changes posted transactions except "apply to past", which the user asks for.

CREATE TABLE rules (
    id         INTEGER PRIMARY KEY,
    match_all  INTEGER NOT NULL DEFAULT 1 CHECK (match_all IN (0,1)),
    position   INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE rule_conditions (
    id       INTEGER PRIMARY KEY,
    rule_id  INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    field    TEXT NOT NULL CHECK (field IN ('counterparty','notes','amount','account','direction')),
    op       TEXT NOT NULL CHECK (op IN ('is','contains','one_of','between','about','more','less')),
    value    TEXT NOT NULL,
    value_to TEXT
);
CREATE INDEX ix_rule_conditions_rule ON rule_conditions(rule_id);

CREATE TABLE rule_actions (
    id          INTEGER PRIMARY KEY,
    rule_id     INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    action      TEXT NOT NULL CHECK (action IN ('category','tag','split')),
    category_id INTEGER REFERENCES categories(id),
    value       TEXT NOT NULL DEFAULT '',
    method      TEXT CHECK (method IS NULL OR method IN ('fixed','percent')),
    position    INTEGER NOT NULL DEFAULT 0,
    CHECK (action = 'tag' OR category_id IS NOT NULL)
);
CREATE INDEX ix_rule_actions_rule ON rule_actions(rule_id);
