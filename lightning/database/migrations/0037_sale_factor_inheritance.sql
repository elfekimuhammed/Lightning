-- 0037 — Sale factors inherit down the asset-class tree (2026-10-01)
--   A class without its own factor uses its nearest parent's. Every class was given a factor
--   in 0029, so a child that only repeats its parent's factor is cleared: it now follows the
--   parent, and every estimate stays the same.
DELETE FROM investment_liquidation_factors
 WHERE asset_class_id IN (
   SELECT child.id
     FROM asset_classes child
     JOIN asset_classes parent ON parent.id = child.parent_id
     JOIN investment_liquidation_factors cf ON cf.asset_class_id = child.id
     JOIN investment_liquidation_factors pf ON pf.asset_class_id = parent.id
    WHERE cf.factor = pf.factor);
