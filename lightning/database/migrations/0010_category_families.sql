ALTER TABLE categories ADD COLUMN family TEXT
    CHECK (family IS NULL OR family IN ('PERSONAL','WORK','INVESTMENT'));

UPDATE categories SET family = scope WHERE scope IN ('PERSONAL','WORK');

-- The existing expense tree becomes the one user-facing activity tree.
UPDATE categories SET name='Activities' WHERE code='EXP';

-- Move employment income under Work, personal income under Personal, and
-- investment income under Investment. Category IDs remain stable for history.
UPDATE categories SET code='EXP.WORK.SALARY', parent_id=(SELECT id FROM categories WHERE code='EXP.WORK'), family='WORK'
 WHERE code='INC.SALARY';
UPDATE categories SET code='EXP.WORK.BONUS', parent_id=(SELECT id FROM categories WHERE code='EXP.WORK'), family='WORK'
 WHERE code='INC.BONUS';
UPDATE categories SET code='EXP.WORK.BUSINESS', parent_id=(SELECT id FROM categories WHERE code='EXP.WORK'), family='WORK'
 WHERE code='INC.BUSINESS';
UPDATE categories SET code='EXP.PERSONAL.GIFTS_RECEIVED', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL'), family='PERSONAL'
 WHERE code='INC.GIFT';
UPDATE categories SET code='EXP.PERSONAL.OTHER_INCOME', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL'), family='PERSONAL'
 WHERE code='INC.OTHER';

UPDATE categories SET code='EXP.INVEST', name='Investment', parent_id=(SELECT id FROM categories WHERE code='EXP'),
 family='INVESTMENT', is_system=0, active=1 WHERE code='INC.INVEST';
UPDATE categories SET code='EXP.INVEST.INTEREST', parent_id=(SELECT id FROM categories WHERE code='EXP.INVEST'), family='INVESTMENT'
 WHERE code='INC.INVEST.INTEREST';
UPDATE categories SET code='EXP.INVEST.DIVIDEND', parent_id=(SELECT id FROM categories WHERE code='EXP.INVEST'), family='INVESTMENT'
 WHERE code='INC.INVEST.DIVIDEND';

UPDATE categories SET family='PERSONAL' WHERE code LIKE 'EXP.PERSONAL%';
UPDATE categories SET family='WORK' WHERE code LIKE 'EXP.WORK%';

UPDATE categories SET code='EXP.PERSONAL.FEES', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL'), family='PERSONAL'
 WHERE code='EXP.FEES';
UPDATE categories SET code='EXP.PERSONAL.FEES.BANK', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL.FEES'), family='PERSONAL'
 WHERE code='EXP.FEES.BANK';
UPDATE categories SET code='EXP.PERSONAL.FEES.INTEREST', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL.FEES'), family='PERSONAL'
 WHERE code='EXP.FEES.INTEREST';
UPDATE categories SET code='EXP.PERSONAL.TAXES', parent_id=(SELECT id FROM categories WHERE code='EXP.PERSONAL'), family='PERSONAL'
 WHERE code='EXP.TAX';
UPDATE categories SET family='PERSONAL' WHERE code='EXP.UNACCOUNTED';

-- Preserve any user-created subcategories below the former income/fee leaves.
UPDATE categories SET code='EXP.WORK.SALARY'||substr(code,length('INC.SALARY')+1) WHERE code LIKE 'INC.SALARY.%';
UPDATE categories SET code='EXP.WORK.BONUS'||substr(code,length('INC.BONUS')+1) WHERE code LIKE 'INC.BONUS.%';
UPDATE categories SET code='EXP.WORK.BUSINESS'||substr(code,length('INC.BUSINESS')+1) WHERE code LIKE 'INC.BUSINESS.%';
UPDATE categories SET code='EXP.PERSONAL.GIFTS_RECEIVED'||substr(code,length('INC.GIFT')+1) WHERE code LIKE 'INC.GIFT.%';
UPDATE categories SET code='EXP.PERSONAL.OTHER_INCOME'||substr(code,length('INC.OTHER')+1) WHERE code LIKE 'INC.OTHER.%';
UPDATE categories SET code='EXP.INVEST.INTEREST'||substr(code,length('INC.INVEST.INTEREST')+1) WHERE code LIKE 'INC.INVEST.INTEREST.%';
UPDATE categories SET code='EXP.INVEST.DIVIDEND'||substr(code,length('INC.INVEST.DIVIDEND')+1) WHERE code LIKE 'INC.INVEST.DIVIDEND.%';
UPDATE categories SET code='EXP.PERSONAL.FEES.BANK'||substr(code,length('EXP.FEES.BANK')+1) WHERE code LIKE 'EXP.FEES.BANK.%';
UPDATE categories SET code='EXP.PERSONAL.FEES.INTEREST'||substr(code,length('EXP.FEES.INTEREST')+1) WHERE code LIKE 'EXP.FEES.INTEREST.%';
UPDATE categories SET code='EXP.PERSONAL.TAXES'||substr(code,length('EXP.TAX')+1) WHERE code LIKE 'EXP.TAX.%';

UPDATE categories SET family='PERSONAL',scope='PERSONAL' WHERE code='EXP.PERSONAL' OR code LIKE 'EXP.PERSONAL.%';
UPDATE categories SET family='WORK',scope='WORK' WHERE code='EXP.WORK' OR code LIKE 'EXP.WORK.%';
UPDATE categories SET family='INVESTMENT',scope=NULL WHERE code='EXP.INVEST' OR code LIKE 'EXP.INVEST.%';
UPDATE categories SET sort_order=1 WHERE code='EXP.PERSONAL';
UPDATE categories SET sort_order=2 WHERE code='EXP.WORK';
UPDATE categories SET sort_order=3 WHERE code='EXP.INVEST';

INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,default_reimbursable,is_system,active,sort_order,created_at,updated_at)
SELECT 'EXP.INVEST.FEES','Investment Fees',id,'OUTFLOW',NULL,NULL,'INVESTMENT',0,0,1,1,datetime('now'),datetime('now')
FROM categories WHERE code='EXP.INVEST';
INSERT INTO categories(code,name,parent_id,movement,scope,income_class,family,default_reimbursable,is_system,active,sort_order,created_at,updated_at)
SELECT 'EXP.INVEST.OTHER','Other Investment',id,'OUTFLOW',NULL,NULL,'INVESTMENT',0,0,1,2,datetime('now'),datetime('now')
FROM categories WHERE code='EXP.INVEST';
