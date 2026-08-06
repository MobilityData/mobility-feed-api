-- Store parsed feed_info.txt fields per GTFS dataset (issue #1775).
-- One row per dataset; populated by the gtfs_file_data_extractor cloud function.
CREATE TABLE IF NOT EXISTS feedinfo (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gtfs_dataset_id     VARCHAR(255) NOT NULL,
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

    CONSTRAINT feedinfo_gtfs_dataset_id_fkey
        FOREIGN KEY (gtfs_dataset_id)
        REFERENCES gtfsdataset(id)
        ON DELETE CASCADE,
    CONSTRAINT feedinfo_gtfs_dataset_id_key
        UNIQUE (gtfs_dataset_id)
);

CREATE INDEX IF NOT EXISTS idx_feedinfo_gtfs_dataset_id
    ON feedinfo (gtfs_dataset_id);
