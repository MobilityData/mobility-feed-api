-- Recreate the table rather than relying on CREATE TABLE IF NOT EXISTS: an earlier
-- revision of this changeset (while the feature was in review) created feedinfo as
-- one row per dataset, and environments that applied it would otherwise silently
-- keep that stale shape. Safe to drop: the rows are a cache of parsed
-- feed_info.txt, rebuilt by re-running the gtfs_file_data_extractor function.
DROP TABLE IF EXISTS feedinfo CASCADE;

-- Store parsed feed_info.txt fields (issue #1775).
-- One row per distinct feed_info.txt content, referenced by every GTFS dataset
-- whose feed_info.txt has that content (one feedinfo -> many gtfsdataset).
-- Populated by the gtfs_file_data_extractor cloud function.
CREATE TABLE feedinfo (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- SHA-256 of the feed_info.txt this row was parsed from (gtfsfile.hash).
    -- Every column below is a pure function of that file content, which is what
    -- makes the row safe to share across datasets: never store per-dataset data
    -- here, and never mutate a row except to re-parse the same content.
    file_hash           VARCHAR(255) NOT NULL,
    feed_publisher_name TEXT,
    feed_publisher_url  TEXT,
    feed_lang           VARCHAR(255),
    default_lang        VARCHAR(255),
    feed_start_date     DATE,
    feed_end_date       DATE,
    feed_version        TEXT,
    feed_contact_email  TEXT,
    feed_contact_url    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT feedinfo_file_hash_key UNIQUE (file_hash)
);

-- Datasets point at the shared feedinfo row. SET NULL rather than CASCADE: the
-- row belongs to the file content, not to any one dataset, so it must survive
-- the deletion of a dataset that references it.
ALTER TABLE gtfsdataset ADD COLUMN IF NOT EXISTS feed_info_id UUID;

-- The FK is dropped with the table above, so it is always re-added here.
ALTER TABLE gtfsdataset
    ADD CONSTRAINT fk_gtfsdataset_feed_info
    FOREIGN KEY (feed_info_id)
    REFERENCES feedinfo(id)
    ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_gtfsdataset_feed_info_id
    ON gtfsdataset (feed_info_id);
