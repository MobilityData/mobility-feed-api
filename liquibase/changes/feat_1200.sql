-- This SQL updates the producer's url to autodiscovery_url for all GBFS feeds

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
REFRESH MATERIALIZED VIEW CONCURRENTLY feedsearch;