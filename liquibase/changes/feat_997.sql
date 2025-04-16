-- Index to get the latest validation report for each GBFS version
CREATE INDEX IF NOT EXISTS idx_validationreport_version_validated_at ON gbfsvalidationreport (gbfs_version_id, validated_at DESC);

-- Add system_id to gbfsfeed table
ALTER TABLE gbfsfeed ADD COLUMN IF NOT EXISTS system_id varchar(255) UNIQUE;

-- Use the first external id to populate existing system_ids
UPDATE gbfsfeed
SET system_id = (
  SELECT
    associated_id
  FROM
    externalid
  WHERE
    gbfsfeed.id = externalid.feed_id
  AND
      externalid.source = 'gbfs'
  LIMIT 1
)
WHERE system_id IS NULL;

-- Populate provider in the feed entity with the operator from the gbfsfeed table
UPDATE feed
SET provider = (
  SELECT
    operator
  FROM
    gbfsfeed
  WHERE
    feed.id = gbfsfeed.id
)
WHERE provider IS NULL and data_type = 'gbfs';

-- Populate producer_url in the feed entity with the autodiscovery_url from the gbfsfeed table
UPDATE feed
SET producer_url = (
  SELECT
    auto_discovery_url
  FROM
    gbfsfeed
  WHERE
    feed.id = gbfsfeed.id
)
WHERE producer_url IS NULL and data_type = 'gbfs';


-- Update search
REFRESH MATERIALIZED VIEW feedsearch;