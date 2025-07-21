-- This SQL script adds indexes that enhance the GBFS SQL queries

CREATE INDEX IF NOT EXISTS idx_gbfsversion_feed_id
  ON gbfsversion (feed_id);

CREATE INDEX IF NOT EXISTS idx_redirectingid_source_id
  ON redirectingid (source_id);

CREATE INDEX IF NOT EXISTS idx_redirectingid_target_id
  ON redirectingid (target_id);

CREATE INDEX IF NOT EXISTS idx_externalid_feed_id
  ON externalid (feed_id);

CREATE INDEX IF NOT EXISTS idx_officialstatushistory_feed_id
  ON officialstatushistory (feed_id);

CREATE INDEX IF NOT EXISTS idx_gbfsendpoint_gv_id
  ON gbfsendpoint (gbfs_version_id);
