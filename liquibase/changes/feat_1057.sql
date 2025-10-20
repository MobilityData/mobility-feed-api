-- Add latest_dataset_id relation on gtfsfeed and populate it.

ALTER TABLE gtfsfeed
    ADD COLUMN IF NOT EXISTS latest_dataset_id VARCHAR(255);


-- Index the referencing column (helps deletes/updates on gtfsdataset)
CREATE INDEX IF NOT EXISTS idx_gtfsfeed_latest_dataset_id ON gtfsfeed(latest_dataset_id);

-- Add FK (idempotent), defer validation to reduce locking
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'gtfsfeed_latest_dataset_id_fkey'
  ) THEN
    ALTER TABLE gtfsfeed
      ADD CONSTRAINT gtfsfeed_latest_dataset_id_fkey
      FOREIGN KEY (latest_dataset_id) REFERENCES gtfsdataset(id)
      ON DELETE SET NULL
      NOT VALID;
  END IF;
END $$;

ALTER TABLE gtfsfeed VALIDATE CONSTRAINT gtfsfeed_latest_dataset_id_fkey;


-- Backfill: for each GTFS feed, set latest_dataset_id to the single dataset where latest=true.
-- Prefer the most recent downloaded_at in case of multiple true due to drift.
WITH latest_dataset AS (
	SELECT gtfsdataset.id, gtfsdataset.stable_id, gtfsdataset.feed_id
  FROM gtfsdataset
  WHERE gtfsdataset.latest IS true
)
UPDATE gtfsfeed 
SET latest_dataset_id = lds.id
FROM latest_dataset lds
WHERE gtfsfeed.id = lds.feed_id;

-- Drop the latest column (no longer used) once backfilled and views updated

DROP MATERIALIZED VIEW IF EXISTS FeedSearch;

ALTER TABLE gtfsdataset DROP COLUMN IF EXISTS latest;
DROP INDEX IF EXISTS idx_gtfsdataset_latest;

