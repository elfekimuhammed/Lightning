-- 0004 — simplify account types (2026-09-25)
--   * A savings account is a bank account: DEPOSIT now means a certificate / time deposit (CD).
--   * Lightning does not track debts: credit card, loan and "money held for others" accounts are retired.
-- Existing data is kept: savings accounts move to BANK; nothing else changes.

-- Guard: stop (and change nothing) if any debt account exists, so no balance is ever lost silently.
CREATE TEMP TABLE _guard_no_liability_accounts (found TEXT CHECK (found IS NULL));
INSERT INTO _guard_no_liability_accounts
    SELECT code FROM accounts WHERE account_type IN ('CREDIT_CARD', 'LOAN', 'PAYABLE');
DROP TABLE _guard_no_liability_accounts;

-- Savings accounts become bank accounts, reported as Bank Balance.
UPDATE accounts
   SET account_type = 'BANK',
       cash_class_id = (SELECT id FROM asset_classes WHERE code = 'CASH.BANK')
 WHERE cash_class_id = (SELECT id FROM asset_classes WHERE code = 'DEPOSIT.SAVINGS');

-- From now on the reporting group always follows the account type (the manual picker is gone).
UPDATE accounts SET cash_class_id = (SELECT id FROM asset_classes WHERE code = CASE account_type
        WHEN 'CASH'           THEN 'CASH.PHYSICAL'
        WHEN 'BANK'           THEN 'CASH.BANK'
        WHEN 'DEPOSIT'        THEN 'DEPOSIT.CD'
        WHEN 'BROKERAGE'      THEN 'CASH.BROKERAGE'
        WHEN 'RECEIVABLE'     THEN 'RECEIVABLE'
        ELSE 'OTHER' END);

-- Remove the asset classes nothing uses any more (children first).
DELETE FROM asset_classes
 WHERE code IN ('LIABILITY.CREDIT_CARD', 'LIABILITY.LOAN', 'LIABILITY.PAYABLE', 'DEPOSIT.SAVINGS')
   AND id NOT IN (SELECT cash_class_id FROM accounts)
   AND id NOT IN (SELECT asset_class_id FROM financial_assets);
DELETE FROM asset_classes
 WHERE code = 'LIABILITY'
   AND id NOT IN (SELECT parent_id FROM asset_classes WHERE parent_id IS NOT NULL)
   AND id NOT IN (SELECT cash_class_id FROM accounts);
