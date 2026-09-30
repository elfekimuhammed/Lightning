-- 0035 — Loan payments category (2026-09-30)
--   Loan and installment payments count as spending when paid. They land in
--   Personal › Loan payments unless the user picks another category, so they show
--   in the budget and cash flow like any other expense. The balance still to pay
--   is tracked by cash planning (what you owe), never as a ledger debt.
INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,
                       default_reimbursable,is_system,active,sort_order,created_at,updated_at)
SELECT 'EXP.PERSONAL.LOANS','Loan payments',id,'OUTFLOW','PERSONAL',NULL,'PERSONAL',
       0,0,1,21,datetime('now'),datetime('now')
FROM categories p
WHERE p.code='EXP.PERSONAL'
  AND NOT EXISTS (SELECT 1 FROM categories WHERE code='EXP.PERSONAL.LOANS');
