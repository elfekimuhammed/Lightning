-- Existing installations already have their starter categories. Mark them as seeded
-- before the startup seeder changes to one-time behavior, preserving user code edits.
INSERT INTO settings(key, value, updated_at)
SELECT 'category_seed_version', '1', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE EXISTS (SELECT 1 FROM categories)
ON CONFLICT(key) DO NOTHING;
