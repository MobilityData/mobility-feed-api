-- Latest dataset id should return the feed_id, not the UID of the dataset
DO
'
    DECLARE
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = ''translationtype'') THEN
            CREATE TYPE TranslationType AS ENUM (''country'', ''subdivision_name'', ''municipality'');
        END IF;
    END;
'  LANGUAGE PLPGSQL;

CREATE TABLE IF NOT EXISTS Translation (
    type TranslationType NOT NULL,
    language_code VARCHAR(3) NOT NULL, -- ISO 639-2
    key VARCHAR(255) NOT NULL,
    value VARCHAR(255) NOT NULL,
    PRIMARY KEY (type, language_code, key)
);

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
    -- latest_dataset
    Latest_dataset.stable_id AS latest_dataset_id,
    Latest_dataset.hosted_url AS latest_dataset_hosted_url,
    Latest_dataset.downloaded_at AS latest_dataset_downloaded_at,
    Latest_dataset.bounding_box AS latest_dataset_bounding_box,
    Latest_dataset.hash AS latest_dataset_hash,
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
    -- translations
    FeedCountryTranslationJoin.translations AS country_translations,
    FeedSubdivisionNameTranslationJoin.translations AS subdivision_name_translations,
    FeedMunicipalityTranslationJoin.translations AS municipality_translations,
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
    setweight(to_tsvector('english', coalesce(unaccent((
        SELECT string_agg(
            coalesce(translation->>'value', ''),
            ' '
        )
        FROM json_array_elements(FeedCountryTranslationJoin.translations) AS translation
    )), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent((
        SELECT string_agg(
            coalesce(translation->>'value', ''),
            ' '
        )
        FROM json_array_elements(FeedSubdivisionNameTranslationJoin.translations) AS translation
    )), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent((
        SELECT string_agg(
            coalesce(translation->>'value', ''),
            ' '
        )
        FROM json_array_elements(FeedMunicipalityTranslationJoin.translations) AS translation
    )), '')), 'A') AS document
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
    SELECT
        LocationFeed.feed_id,
        json_agg(json_build_object('value', Translation.value, 'key', Translation.key)) AS translations
    FROM Location
    LEFT JOIN Translation ON Location.country = Translation.key
    LEFT JOIN LocationFeed ON LocationFeed.location_id = Location.id
    WHERE Translation.language_code = 'en'
    AND Translation.type = 'country'
    AND Location.country IS NOT NULL
    GROUP BY LocationFeed.feed_id
) AS FeedCountryTranslationJoin ON FeedCountryTranslationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT
        LocationFeed.feed_id,
        json_agg(json_build_object('value', Translation.value, 'key', Translation.key)) AS translations
    FROM Location
    LEFT JOIN Translation ON Location.subdivision_name = Translation.key
    LEFT JOIN LocationFeed ON LocationFeed.location_id = Location.id
    WHERE Translation.language_code = 'en'
    AND Translation.type = 'subdivision_name'
    AND Location.subdivision_name IS NOT NULL
    GROUP BY LocationFeed.feed_id
) AS FeedSubdivisionNameTranslationJoin ON FeedSubdivisionNameTranslationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT
        LocationFeed.feed_id,
        json_agg(json_build_object('value', Translation.value, 'key', Translation.key)) AS translations
    FROM Location
    LEFT JOIN Translation ON Location.municipality = Translation.key
    LEFT JOIN LocationFeed ON LocationFeed.location_id = Location.id
    WHERE Translation.language_code = 'en'
    AND Translation.type = 'municipality'
    AND Location.municipality IS NOT NULL
    GROUP BY LocationFeed.feed_id
) AS FeedMunicipalityTranslationJoin ON FeedMunicipalityTranslationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT
        feed_id,
        array_agg(entity_name) AS entities
    FROM EntityTypeFeed
    GROUP BY feed_id
) AS EntityTypeFeedJoin ON EntityTypeFeedJoin.feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'
;


-- This index allows concurrent refresh on the materialized view avoiding table locks
CREATE UNIQUE INDEX idx_unique_feed_id ON FeedSearch(feed_id);

-- Indices for feedsearch view optimization
CREATE INDEX feedsearch_document_idx ON FeedSearch USING GIN(document);
CREATE INDEX feedsearch_feed_stable_id ON FeedSearch(feed_stable_id);
CREATE INDEX feedsearch_data_type ON FeedSearch(data_type);
CREATE INDEX feedsearch_status ON FeedSearch(status);
