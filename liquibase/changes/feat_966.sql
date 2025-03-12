-- Adding osm location groups to feed search view
DROP MATERIALIZED VIEW IF EXISTS FeedSearch;
CREATE MATERIALIZED VIEW FeedSearch AS
SELECT
    -- feed
    Feed.stable_id AS feed_stable_id,
    Feed.id AS feed_id,
    Feed.data_type,
    Feed.status,
    Feed.feed_name,
    Feed.note,
    Feed.feed_contact_email,
    -- source
    Feed.producer_url,
    Feed.authentication_info_url,
    Feed.authentication_type,
    Feed.api_key_parameter_name,
    Feed.license_url,
    Feed.provider,
    Feed.operational_status,
    -- official status
    Latest_official_status.is_official AS official,
    -- latest_dataset
    Latest_dataset.id AS latest_dataset_id,
    Latest_dataset.hosted_url AS latest_dataset_hosted_url,
    Latest_dataset.downloaded_at AS latest_dataset_downloaded_at,
    Latest_dataset.bounding_box AS latest_dataset_bounding_box,
    Latest_dataset.hash AS latest_dataset_hash,
    Latest_dataset.service_date_range_start AS latest_dataset_service_date_range_start,
    Latest_dataset.service_date_range_end AS latest_dataset_service_date_range_end,
    -- external_ids
    ExternalIdJoin.external_ids,
    -- redirect_ids
    RedirectingIdJoin.redirect_ids,
    -- feed gtfs_rt references
    FeedReferenceJoin.feed_reference_ids,
    -- feed gtfs_rt entities
    EntityTypeFeedJoin.entities,
    -- locations
    FeedLocationJoin.locations,
    -- osm locations grouped
    OsmLocationJoin.osm_locations,

    -- full-text searchable document
    setweight(to_tsvector('english', coalesce(unaccent(Feed.feed_name), '')), 'C') ||
    setweight(to_tsvector('english', coalesce(unaccent(Feed.provider), '')), 'C') ||
    setweight(to_tsvector('english', coalesce(unaccent((
        SELECT string_agg(
            coalesce(location->>'country_code', '') || ' ' ||
            coalesce(location->>'country', '') || ' ' ||
            coalesce(location->>'subdivision_name', '') || ' ' ||
            coalesce(location->>'municipality', ''),
            ' '
        )
        FROM json_array_elements(FeedLocationJoin.locations) AS location
    )), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent(OsmLocationNamesJoin.osm_location_names), '')), 'A')
        AS document
FROM Feed
LEFT JOIN (
    SELECT *
    FROM gtfsdataset
    WHERE latest = true
) AS Latest_dataset ON Latest_dataset.feed_id = Feed.id AND Feed.data_type = 'gtfs'
LEFT JOIN (
    SELECT
        feed_id,
        json_agg(json_build_object('external_id', associated_id, 'source', source)) AS external_ids
    FROM externalid
    GROUP BY feed_id
) AS ExternalIdJoin ON ExternalIdJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT
        gtfs_rt_feed_id,
        array_agg(FeedReferenceJoinInnerQuery.stable_id) AS feed_reference_ids
    FROM FeedReference
    LEFT JOIN Feed AS FeedReferenceJoinInnerQuery ON FeedReferenceJoinInnerQuery.id = FeedReference.gtfs_feed_id
    GROUP BY gtfs_rt_feed_id
) AS FeedReferenceJoin ON FeedReferenceJoin.gtfs_rt_feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'
LEFT JOIN (
    SELECT
        target_id,
        json_agg(json_build_object('target_id', target_id, 'comment', redirect_comment)) AS redirect_ids
    FROM RedirectingId
    GROUP BY target_id
) AS RedirectingIdJoin ON RedirectingIdJoin.target_id = Feed.id
LEFT JOIN (
    SELECT
        LocationFeed.feed_id,
        json_agg(json_build_object('country', country, 'country_code', country_code, 'subdivision_name',
                                   subdivision_name, 'municipality', municipality)) AS locations
    FROM Location
    LEFT JOIN LocationFeed ON LocationFeed.location_id = Location.id
    GROUP BY LocationFeed.feed_id
) AS FeedLocationJoin ON FeedLocationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT DISTINCT ON (feed_id) *
    FROM officialstatushistory
    ORDER BY feed_id, timestamp DESC
) AS Latest_official_status ON Latest_official_status.feed_id = Feed.id
LEFT JOIN (
    SELECT
        feed_id,
        array_agg(entity_name) AS entities
    FROM EntityTypeFeed
    GROUP BY feed_id
) AS EntityTypeFeedJoin ON EntityTypeFeedJoin.feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'
LEFT JOIN (
    WITH locations_per_group AS (
        SELECT
            fog.feed_id,
            olg.group_name,
            jsonb_agg(
                DISTINCT jsonb_build_object(
                    'admin_level', gp.admin_level,
                    'name', gp.name
                )
            ) AS locations
        FROM FeedOsmLocationGroup fog
        JOIN OsmLocationGroup olg ON olg.group_id = fog.group_id
        JOIN OsmLocationGroupGeopolygon olgg ON olgg.group_id = olg.group_id
        JOIN Geopolygon gp ON gp.osm_id = olgg.osm_id
        GROUP BY fog.feed_id, olg.group_name
    )
    SELECT
        feed_id,
        jsonb_agg(
            jsonb_build_object(
                'group_name', group_name,
                'locations', locations
            )
        )::json AS osm_locations
    FROM locations_per_group
    GROUP BY feed_id
) AS OsmLocationJoin ON OsmLocationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT
        fog.feed_id,
        string_agg(DISTINCT gp.name, ' ') AS osm_location_names
    FROM FeedOsmLocationGroup fog
    JOIN OsmLocationGroup olg ON olg.group_id = fog.group_id
    JOIN OsmLocationGroupGeopolygon olgg ON olgg.group_id = olg.group_id
    JOIN Geopolygon gp ON gp.osm_id = olgg.osm_id
    WHERE gp.name IS NOT NULL
    GROUP BY fog.feed_id
) AS OsmLocationNamesJoin ON OsmLocationNamesJoin.feed_id = Feed.id;


-- This index allows concurrent refresh on the materialized view avoiding table locks
CREATE UNIQUE INDEX idx_unique_feed_id ON FeedSearch(feed_id);

-- Indices for feedsearch view optimization
CREATE INDEX feedsearch_document_idx ON FeedSearch USING GIN(document);
CREATE INDEX feedsearch_feed_stable_id ON FeedSearch(feed_stable_id);
CREATE INDEX feedsearch_data_type ON FeedSearch(data_type);
CREATE INDEX feedsearch_status ON FeedSearch(status);

DROP VIEW IF EXISTS location_with_translations_en;
DROP TABLE IF EXISTS translation;
