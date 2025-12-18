-- 1. Backfill existing rows
UPDATE feed
SET operational_status = 'published'
WHERE operational_status IS NULL;

-- 2. Set default for future inserts
ALTER TABLE feed
ALTER COLUMN operational_status
SET DEFAULT 'published';

-- 3. Enforce NOT NULL
ALTER TABLE feed
ALTER COLUMN operational_status
SET NOT NULL;
