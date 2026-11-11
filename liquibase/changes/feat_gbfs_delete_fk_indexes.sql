-- This SQL script indexes the foreign key columns hit by ON DELETE CASCADE when a GBFS feed is deleted.
-- Without them every cascaded delete does a sequential scan of the child table, which made deleting
-- deprecated GBFS feeds in populate_db_gbfs.py take up to ~90s per feed.
-- The http access log tables already have a composite primary key, but gbfs_feed_id/gbfs_endpoint_id
-- is its second column, so it cannot be used for lookups by that column alone.

CREATE INDEX IF NOT EXISTS idx_gbfsnotice_validation_report_id
  ON gbfsnotice (validation_report_id);

CREATE INDEX IF NOT EXISTS idx_gbfsendpointhttpaccesslog_gbfs_endpoint_id
  ON gbfsendpointhttpaccesslog (gbfs_endpoint_id);

CREATE INDEX IF NOT EXISTS idx_gbfsfeedhttpaccesslog_gbfs_feed_id
  ON gbfsfeedhttpaccesslog (gbfs_feed_id);
