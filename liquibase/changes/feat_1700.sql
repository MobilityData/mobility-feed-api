-- Add table to store GTFS feed availability check results (issue #1700).
-- Supports feed availability analysis as described in epic #1699.
CREATE TABLE IF NOT EXISTS gtfsfeedavailabilitycheck (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    feed_id      VARCHAR(255) NOT NULL,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    request_url  TEXT NOT NULL,
    status_code  INTEGER,
    latency_ms   DOUBLE PRECISION,

    error_message TEXT,
    error_type   VARCHAR(255),

    success      BOOLEAN NOT NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT gtfsfeedavailabilitycheck_feed_id_fkey
        FOREIGN KEY (feed_id)
        REFERENCES gtfsfeed(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gtfsfeedavailabilitycheck_feed_checked_at
    ON gtfsfeedavailabilitycheck (feed_id, checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_gtfsfeedavailabilitycheck_checked_at
    ON gtfsfeedavailabilitycheck (checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_gtfsfeedavailabilitycheck_feed_success_checked_at
    ON gtfsfeedavailabilitycheck (feed_id, success, checked_at DESC);
