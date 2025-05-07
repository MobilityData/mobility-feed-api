-- Insert a GbfsEndpoint row to GbfsVersions that miss the gbfs(autodiscovery) endpoint
INSERT INTO GbfsEndpoint (id, gbfs_version_id, url, name, is_feature)
SELECT 
    Feed.stable_id || '_' || GbfsVersion.version AS id,
    GbfsVersion.id AS gbfs_version_id,
    GbfsVersion.url AS url,
    'gbfs' AS name,
    false AS is_feature -- gbfs file is not a feature, see https://github.com/MobilityData/mobility-feed-api/issues/1125
FROM GbfsVersion
JOIN GbfsFeed ON GbfsVersion.feed_id = GbfsFeed.id
JOIN Feed ON GbfsFeed.id = Feed.id
WHERE NOT EXISTS (
    SELECT 1
    FROM GbfsEndpoint
    WHERE GbfsEndpoint.gbfs_version_id = GbfsVersion.id
      AND GbfsEndpoint.name = 'gbfs'
);
