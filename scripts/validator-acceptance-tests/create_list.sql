-- Selects a single row per feed (by stable_id), including provider and location info
SELECT DISTINCT ON (f.stable_id)
    f.stable_id,           -- Unique stable identifier for the feed
    f.provider,            -- Provider name for the feed
    l.country_code,        -- Country code of the feed's location
    l.subdivision_name,    -- Subdivision (e.g., state/province) of the location
    l.municipality         -- Municipality (e.g., city) of the location
FROM feed AS f
    JOIN locationfeed AS lf ON lf.feed_id = f.id  -- Join feeds to their locations
    JOIN location AS l ON l.id = lf.location_id   -- Join to location details
WHERE f.data_type = 'gtfs'                        -- Only GTFS feeds
  AND f.stable_id LIKE 'mdb-%'                    -- Only feeds with stable_id starting with 'mdb-'
  AND f.status <> 'deprecated'                    -- Exclude deprecated feeds
  AND f.operational_status = 'published'          -- Only published feeds
  AND f.stable_id NOT IN ('mdb-784', 'mdb-1081', 'mdb-1078') -- Exclude specific feeds by stable_id
  AND (
    l.country_code <> 'US'                        -- Exclude US feeds unless exceptions below
    OR l.country_code IS NULL                     -- Include feeds with no country code
    OR f.provider ILIKE 'Chicago Transit Authority%' -- Exception: include Chicago Transit Authority
    OR l.subdivision_name ILIKE 'California%'        -- Exception: include California subdivision
    OR l.subdivision_name ILIKE 'New York%'          -- Exception: include New York subdivision
    OR f.provider ILIKE 'Miami-Dade Transit%'        -- Exception: include Miami-Dade Transit
  )
ORDER BY f.stable_id, l.country_code, l.subdivision_name, l.municipality; -- Required for DISTINCT ON, controls which row is picked per stable_id
