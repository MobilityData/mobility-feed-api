-- Issue #1774: Add seasonal to the feed table.
-- Marks whether a feed is seasonal, i.e. it only provides service during recurring
-- periods of the year (e.g. a summer-only or winter-only service).
-- Seasonal feeds are excluded from the rolling 7-day service coverage checks.
-- Boolean flag defaulting to FALSE (a feed is considered non-seasonal unless explicitly marked).
ALTER TABLE feed ADD COLUMN IF NOT EXISTS seasonal BOOLEAN NOT NULL DEFAULT FALSE;
