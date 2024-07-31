-- Install the unaccent extension to allow accent-insensitive search
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Droping the materialized view is not possible to edit it
DROP MATERIALIZED VIEW IF EXISTS FeedSearch;

CREATE MATERIALIZED VIEW FeedSearch AS
SELECT 
--feed
Feed.stable_id as feed_stable_id,
Feed.id as feed_id,
Feed.data_type,
Feed.status,
Feed.feed_name,
Feed.note,
Feed.feed_contact_email,
--source
Feed.producer_url,
Feed.authentication_info_url,
Feed.authentication_type,
Feed.api_key_parameter_name,
Feed.license_url,
Feed.provider,
--latest_dataset
Latest_dataset.id as latest_dataset_id,
Latest_dataset.hosted_url as latest_dataset_hosted_url,
Latest_dataset.downloaded_at as latest_dataset_downloaded_at,
Latest_dataset.bounding_box as latest_dataset_bounding_box,
Latest_dataset.hash as latest_dataset_hash,
--external_ids
ExternalIdJoin.external_ids,
--redirect_ids
RedirectingIdJoin.redirect_ids,
--feed gtfs_rt references
FeedReferenceJoin.feed_reference_ids,
-- feed gtfs_rt entities
EntityTypeFeedJoin.entities,
--locations
FeedLocationJoin.locations,
--full-text searchable document	
setweight(to_tsvector('english', coalesce(unaccent(Feed.feed_name), '')), 'C') ||
setweight(to_tsvector('english', coalesce(unaccent(Feed.provider), '')), 'C') ||
COALESCE(setweight(to_tsvector('english', coalesce((FeedLocationJoin.locations #>> '{0,country_code}'), '')), 'A'), '') ||
COALESCE(setweight(to_tsvector('english', coalesce((FeedLocationJoin.locations #>> '{0,subdivision_name}'), '')), 'A'), '') ||
COALESCE(setweight(to_tsvector('english', coalesce((FeedLocationJoin.locations #>> '{0,municipality}'), '')), 'A'), '')
AS DOCUMENT
FROM FEED
LEFT JOIN (
	SELECT *
	FROM gtfsdataset
	WHERE latest = true
) AS Latest_dataset on Latest_dataset.feed_id = Feed.id AND Feed.data_type = 'gtfs'
LEFT JOIN (
    SELECT 
        feed_id, 
		json_agg(json_build_object('external_id', associated_id, 'source', source)) AS external_ids	
    FROM externalid
    GROUP BY feed_id
) AS ExternalIdJoin ON ExternalIdJoin.feed_id = Feed.id
LEFT JOIN(
	SELECT 
		gtfs_rt_feed_id,
		array_agg(FeedReferenceJoinInnerQuery.stable_id) as feed_reference_ids
	FROM FeedReference
	LEFT JOIN Feed as FeedReferenceJoinInnerQuery on FeedReferenceJoinInnerQuery.id = FeedReference.gtfs_feed_id
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
		json_agg(json_build_object('country_code', country_code, 'subdivision_name',
								   subdivision_name, 'municipality', municipality)) AS locations		
    FROM Location
	LEFT JOIN LocationFeed on LocationFeed.location_id = Location.id
    GROUP BY LocationFeed.feed_id
) AS FeedLocationJoin ON FeedLocationJoin.feed_id = Feed.id
LEFT JOIN (
    SELECT 
        feed_id,
		array_agg(entity_name) as entities
    FROM EntityTypeFeed
    GROUP BY feed_id
) AS EntityTypeFeedJoin ON EntityTypeFeedJoin.feed_id = Feed.id AND Feed.data_type = 'gtfs_rt'
;

-- This index allows concurrent refresh on the materialized view avoiding table locks
CREATE UNIQUE INDEX idx_unique_feed_id ON FeedSearch(feed_id);

-- indices for feedsearch view optimization
CREATE INDEX feedsearch_document_idx ON FeedSearch USING GIN(document);
CREATE INDEX feedsearch_feed_stable_id ON FeedSearch(feed_stable_id);
CREATE INDEX feedsearch_data_type ON FeedSearch(data_type);
CREATE INDEX feedsearch_status ON FeedSearch(status);