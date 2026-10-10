-- 0052 — group ledger exceptions under one visible System Categories family.
UPDATE categories
   SET name='System Categories', updated_at=datetime('now')
 WHERE code='EXP.SYSTEM';

UPDATE categories
   SET code='EXP.SYSTEM.ADJUSTMENT',
       parent_id=(SELECT id FROM categories WHERE code='EXP.SYSTEM'),
       updated_at=datetime('now')
 WHERE code='EXP.PERSONAL.ADJUSTMENT';

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,direction,created_at,updated_at)
SELECT 'EXP.SYSTEM.TRANSFERS','Internal transfers',id,'OUTFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,92,'BOTH',datetime('now'),datetime('now')
FROM categories
WHERE code='EXP.SYSTEM'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.SYSTEM.TRANSFERS');

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,direction,created_at,updated_at)
SELECT 'EXP.SYSTEM.CAPITAL','Capital allocation',id,'OUTFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,93,'BOTH',datetime('now'),datetime('now')
FROM categories
WHERE code='EXP.SYSTEM'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.SYSTEM.CAPITAL');

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,direction,created_at,updated_at)
SELECT 'EXP.SYSTEM.ADJUSTMENT','Adjustment',id,'OUTFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,94,'BOTH',datetime('now'),datetime('now')
FROM categories
WHERE code='EXP.SYSTEM'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.SYSTEM.ADJUSTMENT');
