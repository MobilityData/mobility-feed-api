-- Remove feeds mdb-3504 and mdb-3505 (Sao Paulo) and every record related to them.
--
-- Deleting the feed row cascades (ON DELETE CASCADE) to:
--   gtfsfeed / gtfsrealtimefeed, externalid, feed_license_change, feed_reliability_seal,
--   feedlocationgrouppoint, feedosmlocationgroup, feedrelatedlink, locationfeed,
--   officialstatushistory, redirectingid (as source or target), seal_criterion,
--   seal_criterion_snapshot, entitytypefeed, feedreference, gtfs_dataset_changelog,
--   gtfs_feed_availability_check, gtfsdataset
-- and from gtfsdataset to:
--   gtfsfile, notice, location_gtfsdataset, validationreportgtfsdataset
--
-- Not covered by cascades, handled explicitly below:
--   gtfsfeed.bounding_box_dataset_id / visualization_dataset_id (no ON DELETE rule)
--   config_value_feed (no foreign key to feed)
--   validationreport and feedinfo rows that would be left orphaned
--   feedsearch materialized view

CREATE TEMP TABLE sp_feeds_to_delete ON COMMIT DROP AS
SELECT f.id
FROM feed f
WHERE f.stable_id IN ('mdb-3504', 'mdb-3505');

CREATE TEMP TABLE sp_datasets_to_delete ON COMMIT DROP AS
SELECT g.id, g.feed_info_id
FROM gtfsdataset g
WHERE g.feed_id IN (SELECT id FROM sp_feeds_to_delete);

-- Validation reports used exclusively by the datasets being deleted
CREATE TEMP TABLE sp_validation_reports_to_delete ON COMMIT DROP AS
SELECT DISTINCT vrd.validation_report_id AS id
FROM validationreportgtfsdataset vrd
WHERE vrd.dataset_id IN (SELECT id FROM sp_datasets_to_delete)
  AND NOT EXISTS (
    SELECT 1
    FROM validationreportgtfsdataset other
    WHERE other.validation_report_id = vrd.validation_report_id
      AND other.dataset_id NOT IN (SELECT id FROM sp_datasets_to_delete)
  );

-- Feed info rows used exclusively by the datasets being deleted
CREATE TEMP TABLE sp_feed_infos_to_delete ON COMMIT DROP AS
SELECT DISTINCT d.feed_info_id AS id
FROM sp_datasets_to_delete d
WHERE d.feed_info_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM gtfsdataset other
    WHERE other.feed_info_id = d.feed_info_id
      AND other.id NOT IN (SELECT id FROM sp_datasets_to_delete)
  );

-- Clear dataset references that have no ON DELETE rule
UPDATE gtfsfeed
SET bounding_box_dataset_id = NULL
WHERE bounding_box_dataset_id IN (SELECT id FROM sp_datasets_to_delete);

UPDATE gtfsfeed
SET visualization_dataset_id = NULL
WHERE visualization_dataset_id IN (SELECT id FROM sp_datasets_to_delete);

DELETE FROM config_value_feed
WHERE feed_id IN (SELECT id FROM sp_feeds_to_delete);

-- Cascades to all feed-level and dataset-level tables listed above
DELETE FROM feed
WHERE id IN (SELECT id FROM sp_feeds_to_delete);

-- Cascades to notice and featurevalidationreport
DELETE FROM validationreport
WHERE id IN (SELECT id FROM sp_validation_reports_to_delete);

DELETE FROM feedinfo
WHERE id IN (SELECT id FROM sp_feed_infos_to_delete);

REFRESH MATERIALIZED VIEW feedsearch;
