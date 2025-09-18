-- This script fix a circular dependency between the gtfsdataset and feed tables

-- 1. Add the new column to gtfsfeed (if not already added)
ALTER TABLE gtfsfeed
  ADD COLUMN IF NOT EXISTS geolocation_file_dataset_id VARCHAR(255);

-- 2. Copy existing values from feed to gtfsfeed
--    (we assume gtfsfeed.id = feed.id, since gtfsfeed is a subtype of feed)
UPDATE gtfsfeed gf
SET geolocation_file_dataset_id = f.geolocation_file_dataset_id
FROM feed f
WHERE gf.id = f.id
  AND f.geolocation_file_dataset_id IS NOT NULL;

-- 3. Add the foreign key constraint on gtfsfeed
ALTER TABLE gtfsfeed
  ADD CONSTRAINT fk_gtfsfeed_geolocation_file_dataset
  FOREIGN KEY (geolocation_file_dataset_id) REFERENCES gtfsdataset(id)
  ON DELETE SET NULL;

-- 4. Drop the old constraint and column from feed
ALTER TABLE feed DROP CONSTRAINT IF EXISTS fk_feed_geolocation_file_dataset;
ALTER TABLE feed DROP COLUMN IF EXISTS geolocation_file_dataset_id;
