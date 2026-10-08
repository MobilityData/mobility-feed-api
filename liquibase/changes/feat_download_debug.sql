-- Add request/response debugging columns to gtfs_feed_availability_check.
-- source distinguishes rows written by the daily availability task from rows written
-- when a dataset download fails in batch_process_dataset.
-- request_headers, response_headers and resolved_url are sanitized before being stored:
-- credential-bearing header values and query parameters are replaced with a redaction marker.
-- external_ip is the egress IP observed for the request, captured best-effort on failures only.
ALTER TABLE gtfs_feed_availability_check
    ADD COLUMN IF NOT EXISTS source TEXT,
    ADD COLUMN IF NOT EXISTS request_headers JSONB,
    ADD COLUMN IF NOT EXISTS response_headers JSONB,
    ADD COLUMN IF NOT EXISTS redirect_urls JSONB,
    ADD COLUMN IF NOT EXISTS external_ip TEXT,
    ADD COLUMN IF NOT EXISTS resolved_url TEXT;

UPDATE gtfs_feed_availability_check
SET source = 'availability_check'
WHERE source IS NULL;

CREATE INDEX IF NOT EXISTS idx_gtfs_feed_availability_check_source_checked_at
    ON gtfs_feed_availability_check (source, checked_at);
