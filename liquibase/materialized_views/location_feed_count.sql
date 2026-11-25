-- Feed counts of the location directory, precomputed so that /v1/locations filters (`has_feeds`) and sorts
-- (`sort=feed_count`) on plain columns. Refreshed with feedsearch by the tasks_executor `refresh_materialized_view`
-- task, which runs after reverse geolocation and dataset processing.
--
-- A feed is counted in a location when it has reverse-geolocated stops there, sub-areas included: its
-- feedosmlocationgroup rows link it to location groups, and each group holds the full chain of areas covering some of
-- its stops. Feeds that were never reverse-geolocated have no group, so they are counted nowhere.
--
-- One row per location and visibility:
--   - places (osm_id set): every OSM area with a counted feed. A discarded duplicate boundary of a country counts in
--     the retained one (lowest admin level, then lowest osm_id), as in geopolygonlocationsearch.
--   - continents (continent_code set, osm_id NULL): the feeds of the continent's countries, each feed once even when it
--     has stops in several of them.
--   - published_only: FALSE counts every counted feed; TRUE only the published ones, for callers that cannot see
--     work-in-progress feeds.
-- Counted feeds have a status of active, inactive, development or future. A location without any counted feed has no
-- row; read a missing row as 0.
CREATE MATERIALIZED VIEW LocationFeedCount AS
WITH country_boundaries AS (
    SELECT
        gp.osm_id,
        gp.iso_3166_1_code,
        first_value(gp.osm_id) OVER (
            PARTITION BY gp.iso_3166_1_code
            ORDER BY gp.admin_level ASC NULLS LAST, gp.osm_id ASC
        ) AS retained_osm_id
    FROM Geopolygon gp
    WHERE gp.iso_3166_1_code IS NOT NULL
),
counted_feeds AS (
    SELECT
        feed.id,
        feed.data_type,
        feed.operational_status = 'published' AS is_published
    FROM Feed feed
    WHERE feed.status IN ('active', 'inactive', 'development', 'future')
),
place_feeds AS (
    SELECT DISTINCT
        COALESCE(country_boundaries.retained_osm_id, location_group.osm_id) AS osm_id,
        feed_group.feed_id
    FROM FeedOsmLocationGroup feed_group
    JOIN OsmLocationGroupGeopolygon location_group ON location_group.group_id = feed_group.group_id
    LEFT JOIN country_boundaries ON country_boundaries.osm_id = location_group.osm_id
),
continent_feeds AS (
    SELECT DISTINCT
        country_continent.continent_code,
        place_feeds.feed_id
    FROM place_feeds
    JOIN country_boundaries ON country_boundaries.osm_id = place_feeds.osm_id
    JOIN country_continent ON country_continent.country_code = country_boundaries.iso_3166_1_code
),
location_feeds AS (
    SELECT place_feeds.osm_id, NULL::varchar(2) AS continent_code, place_feeds.feed_id
    FROM place_feeds

    UNION ALL

    SELECT NULL::integer AS osm_id, continent_feeds.continent_code, continent_feeds.feed_id
    FROM continent_feeds
),
visibilities AS (
    SELECT unnest(ARRAY[FALSE, TRUE]) AS published_only
)
SELECT
    location_feeds.osm_id,
    location_feeds.continent_code,
    visibilities.published_only,
    -- A feed has one data type, so the total is the sum of the three counts.
    count(*) FILTER (WHERE counted_feeds.data_type = 'gtfs') AS gtfs,
    count(*) FILTER (WHERE counted_feeds.data_type = 'gtfs_rt') AS gtfs_rt,
    count(*) FILTER (WHERE counted_feeds.data_type = 'gbfs') AS gbfs,
    count(*) AS total
FROM location_feeds
JOIN counted_feeds ON counted_feeds.id = location_feeds.feed_id
CROSS JOIN visibilities
WHERE NOT visibilities.published_only OR counted_feeds.is_published
GROUP BY location_feeds.osm_id, location_feeds.continent_code, visibilities.published_only;

-- Required by REFRESH MATERIALIZED VIEW CONCURRENTLY. A place row has a NULL continent_code and a continent row a NULL
-- osm_id, so every row is unique on these three columns.
CREATE UNIQUE INDEX idx_unique_location_feed_count
    ON LocationFeedCount(osm_id, continent_code, published_only);
CREATE INDEX location_feed_count_continent_code_idx
    ON LocationFeedCount(continent_code, published_only) WHERE continent_code IS NOT NULL;
