-- Add table to store GTFS feed availability check results (issue #1700).
-- Supports feed availability analysis as described in epic #1699.
CREATE TYPE availability_check_request_type AS ENUM (
    'http_head',
    'http_get'
);

CREATE TABLE IF NOT EXISTS gtfs_feed_availability_check (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    feed_id      VARCHAR(255) NOT NULL,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    request_url  TEXT NOT NULL,
    request_type availability_check_request_type NOT NULL,
    status_code  INTEGER,
    latency_ms   DOUBLE PRECISION,

    error_message TEXT,
    error_type   VARCHAR(255),

    success      BOOLEAN NOT NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT gtfs_feed_availability_check_feed_id_fkey
        FOREIGN KEY (feed_id)
        REFERENCES gtfsfeed(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gtfs_feed_availability_check_feed_checked_at
    ON gtfs_feed_availability_check (feed_id, checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_gtfs_feed_availability_check_checked_at
    ON gtfs_feed_availability_check (checked_at DESC);

CREATE INDEX IF NOT EXISTS idx_gtfs_feed_availability_check_feed_success_checked_at
    ON gtfs_feed_availability_check (feed_id, success, checked_at DESC);
