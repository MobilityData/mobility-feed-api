-- Add table to store GTFS dataset changelog references (issue #1633).
-- Records that a changelog artifact exists and where to find it in GCS.
-- All diff content stays in GCS; this table enables lookup by feed or dataset ID.
CREATE TABLE IF NOT EXISTS gtfs_dataset_changelog (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_id             VARCHAR(255) NOT NULL,
    previous_dataset_id VARCHAR(255) NOT NULL,
    current_dataset_id  VARCHAR(255) NOT NULL,
    changelog_url       TEXT NOT NULL,
    diff_summary        JSONB NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT gtfs_dataset_changelog_feed_id_fkey
        FOREIGN KEY (feed_id)
        REFERENCES gtfsfeed(id)
        ON DELETE CASCADE,
    CONSTRAINT gtfs_dataset_changelog_previous_dataset_id_fkey
        FOREIGN KEY (previous_dataset_id)
        REFERENCES gtfsdataset(id)
        ON DELETE CASCADE,
    CONSTRAINT gtfs_dataset_changelog_current_dataset_id_fkey
        FOREIGN KEY (current_dataset_id)
        REFERENCES gtfsdataset(id)
        ON DELETE CASCADE,
    CONSTRAINT gtfs_dataset_changelog_previous_current_key
        UNIQUE (previous_dataset_id, current_dataset_id)
);

CREATE INDEX IF NOT EXISTS idx_gtfs_dataset_changelog_feed_id
    ON gtfs_dataset_changelog (feed_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_gtfs_dataset_changelog_current
    ON gtfs_dataset_changelog (current_dataset_id);
