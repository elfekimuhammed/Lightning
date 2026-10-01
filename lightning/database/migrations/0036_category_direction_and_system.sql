-- 0036 — Category direction, L3 categories and the System group (2026-10-01)
--   direction: '+' income only (IN), '−' expense only (OUT) or both (BOTH). NULL means the
--   default for its movement (INFLOW → IN, OUTFLOW → OUT).
--   A fourth L1, System, holds categories the app itself relies on: money held for others
--   and loan payments. They keep their ids, so every transaction keeps its category; only the
--   code moves under EXP.SYSTEM. System counts as personal spending, like before.
ALTER TABLE categories ADD COLUMN direction TEXT
    CHECK (direction IS NULL OR direction IN ('IN','OUT','BOTH'));

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,created_at,updated_at)
SELECT 'EXP.SYSTEM','System',id,'OUTFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,90,datetime('now'),datetime('now')
FROM categories p
WHERE p.code='EXP'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.SYSTEM');

UPDATE categories
   SET code = 'EXP.SYSTEM.' || substr(code, length('EXP.PERSONAL.') + 1), updated_at = datetime('now')
 WHERE (code = 'EXP.PERSONAL.CUSTODY' OR code LIKE 'EXP.PERSONAL.CUSTODY.%'
        OR code = 'EXP.PERSONAL.LOANS' OR code LIKE 'EXP.PERSONAL.LOANS.%')
   AND EXISTS (SELECT 1 FROM categories WHERE code='EXP.SYSTEM');

UPDATE categories
   SET parent_id = (SELECT id FROM categories WHERE code='EXP.SYSTEM')
 WHERE code IN ('EXP.SYSTEM.CUSTODY', 'EXP.SYSTEM.LOANS');
