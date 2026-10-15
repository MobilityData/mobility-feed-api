-- Issue #1766: Add is_producer_url_unstable to the feed table.
-- Marks whether a feed's producer URL is known to be unstable/non-permanent
-- (e.g. it contains a date/time or the transit provider updates it periodically).
-- Nullable three-state boolean: TRUE = unstable, FALSE = stable, NULL = unknown (default).
ALTER TABLE feed ADD COLUMN IF NOT EXISTS is_producer_url_unstable BOOLEAN;
