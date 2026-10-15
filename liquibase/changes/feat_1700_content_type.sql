-- Add content_type and is_zip columns to gtfs_feed_availability_check (issue #1700).
-- content_type stores the HTTP Content-Type header value from the availability check response.
-- is_zip indicates whether the response body is a ZIP file (verified via magic bytes on GET
-- fallback, or inferred from Content-Type on HEAD-only checks).
ALTER TABLE gtfs_feed_availability_check
    ADD COLUMN IF NOT EXISTS content_type TEXT,
    ADD COLUMN IF NOT EXISTS is_zip BOOLEAN;
