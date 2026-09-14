-- Issue #1831: gtfsfile has no index on gtfs_dataset_id, so "does this dataset contain
-- calendar.txt?" reads all 2M rows. The seal criteria ask it once per dataset, which made a
-- one-feed backfill take 370 s instead of 2.27 s.
-- CONCURRENTLY, so this runs outside a transaction - see feat_1831_indexes.xml.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gtfsfile_gtfs_dataset_id
  ON gtfsfile (gtfs_dataset_id);
