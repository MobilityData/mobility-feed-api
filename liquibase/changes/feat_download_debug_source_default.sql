-- Make gtfs_feed_availability_check.source always set, and fold dry runs into manual downloads.
-- The public availability endpoint and the Seal of Reliability keep only rows whose source
-- is 'availability_check' (see api/src/shared/common/availability_check_source.py). A row
-- written without a source would silently drop out of both, so a missing source means the
-- daily availability check, which is what every row before the column existed was.
UPDATE gtfs_feed_availability_check
SET source = 'availability_check'
WHERE source IS NULL;

-- Dry runs asked for through the operations API are recorded as manual downloads, like full
-- runs; the separate dry-run source is retired.
UPDATE gtfs_feed_availability_check
SET source = 'dataset_download_manual'
WHERE source = 'dataset_download_dry_run';

ALTER TABLE gtfs_feed_availability_check
    ALTER COLUMN source SET DEFAULT 'availability_check',
    ALTER COLUMN source SET NOT NULL;
