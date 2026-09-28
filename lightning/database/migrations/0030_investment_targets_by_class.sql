ALTER TABLE investment_targets ADD COLUMN asset_class_id INTEGER REFERENCES asset_classes(id);
UPDATE investment_targets
SET asset_class_id=(SELECT MIN(id) FROM asset_classes WHERE active=1 AND name=investment_targets.bucket)
WHERE (SELECT COUNT(*) FROM asset_classes WHERE active=1 AND name=investment_targets.bucket)=1;
CREATE UNIQUE INDEX ux_investment_targets_asset_class ON investment_targets(asset_class_id) WHERE asset_class_id IS NOT NULL;
