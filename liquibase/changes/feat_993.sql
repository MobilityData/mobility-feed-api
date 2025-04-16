-- select * from databasechangelog

--
-- This SQL adds the validation features and totals of the latest dataset to the FeedSearch view.
--

-- Dropping the materialized view if it exists as we cannot update it
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
    Latest_dataset.agency_timezone AS latest_dataset_agency_timezone,
    Latest_dataset.service_date_range_start AS latest_dataset_service_date_range_start,
    Latest_dataset.service_date_range_end AS latest_dataset_service_date_range_end,
    -- Latest dataset features
    LatestDatasetFeatures AS latest_dataset_features,
    -- Latest dataset validation totals
    COALESCE(LatestDatasetValidationReportJoin.total_error, 0) as latest_total_error,
    COALESCE(LatestDatasetValidationReportJoin.total_warning, 0) as latest_total_warning,
    COALESCE(LatestDatasetValidationReportJoin.total_info, 0) as latest_total_info,
    COALESCE(LatestDatasetValidationReportJoin.unique_error_count, 0) as latest_unique_error_count,
    COALESCE(LatestDatasetValidationReportJoin.unique_warning_count, 0) as latest_unique_warning_count,
    COALESCE(LatestDatasetValidationReportJoin.unique_info_count, 0) as latest_unique_info_count,
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

-- Latest dataset
LEFT JOIN (
    SELECT *
    FROM gtfsdataset
    WHERE latest = true
) AS Latest_dataset ON Latest_dataset.feed_id = Feed.id AND Feed.data_type = 'gtfs'

-- Latest dataset features
LEFT JOIN (
    SELECT 
        GtfsDataset.id as FeatureGtfsDatasetId,
        array_agg(featurevalidationreport.feature) as LatestDatasetFeatures
    FROM FeatureValidationReport
    JOIN ValidationReportGtfsDataset on FeatureValidationReport.validation_id = ValidationReportGtfsDataset.validation_report_id
    JOIN GtfsDataset on GtfsDataset.id = ValidationReportGtfsDataset.dataset_id
    GROUP BY FeatureGtfsDatasetId
) AS LatestDatasetFeaturesJoin ON Latest_dataset.id = FeatureGtfsDatasetId

-- Latest dataset validation report
LEFT JOIN (
    SELECT 
        GtfsDataset.id as ValidationReportGtfsDatasetId,
        MAX(ValidationReport.total_error) AS total_error,
        MAX(ValidationReport.total_warning) AS total_warning,
        MAX(ValidationReport.total_info) AS total_info,
        MAX(ValidationReport.unique_error_count) AS unique_error_count,
        MAX(ValidationReport.unique_warning_count) AS unique_warning_count,
        MAX(ValidationReport.unique_info_count) AS unique_info_count
    FROM ValidationReport
    JOIN ValidationReportGtfsDataset ON ValidationReport.id = ValidationReportGtfsDataset.validation_report_id
    JOIN GtfsDataset ON GtfsDataset.id = ValidationReportGtfsDataset.dataset_id
    GROUP BY GtfsDataset.id
) AS LatestDatasetValidationReportJoin ON Latest_dataset.id = ValidationReportGtfsDatasetId


-- External ids
LEFT JOIN (
    SELECT
        feed_id,
        json_agg(json_build_object('external_id', associated_id, 'source', source)) AS external_ids
    FROM externalid
    GROUP BY feed_id
) AS ExternalIdJoin ON ExternalIdJoin.feed_id = Feed.id

-- feed reference ids
LEFT JOIN (
    SELECT
        gtfs_rt_feed_id,
        array_agg(FeedReferenceJoinInnerQuery.stable_id) AS feed_reference_ids
    FROM FeedReference
    LEFT JOIN Feed AS FeedReferenceJoinInnerQuery ON FeedReferenceJoinInnerQuery.id = FeedReference.gtfs_feed_id
    GROUP BY gtfs_rt_feed_id
) AS FeedReferenceJoin ON FeedReferenceJoin.gtfs_rt_feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'

-- Redirect ids
LEFT JOIN (
    SELECT
        target_id,
        json_agg(json_build_object('target_id', target_id, 'comment', redirect_comment)) AS redirect_ids
    FROM RedirectingId
    GROUP BY target_id
) AS RedirectingIdJoin ON RedirectingIdJoin.target_id = Feed.id

-- Feed locations
LEFT JOIN (
    SELECT
        LocationFeed.feed_id,
        json_agg(json_build_object('country', country, 'country_code', country_code, 'subdivision_name',
                                   subdivision_name, 'municipality', municipality)) AS locations
    FROM Location
    LEFT JOIN LocationFeed ON LocationFeed.location_id = Location.id
    GROUP BY LocationFeed.feed_id
) AS FeedLocationJoin ON FeedLocationJoin.feed_id = Feed.id

-- Latest dataset official status
LEFT JOIN (
    SELECT DISTINCT ON (feed_id) *
    FROM officialstatushistory
    ORDER BY feed_id, timestamp DESC
) AS Latest_official_status ON Latest_official_status.feed_id = Feed.id

-- Entity types
LEFT JOIN (
    SELECT
        feed_id,
        array_agg(entity_name) AS entities
    FROM EntityTypeFeed
    GROUP BY feed_id
) AS EntityTypeFeedJoin ON EntityTypeFeedJoin.feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'

-- OSM locations
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

-- OSM location names
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
