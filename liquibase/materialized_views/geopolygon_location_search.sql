CREATE MATERIALIZED VIEW GeopolygonLocationSearch AS
WITH RECURSIVE hierarchy AS (
    SELECT
        gp.osm_id,
        gp.osm_id AS ancestor_osm_id,
        0 AS depth,
        ARRAY[gp.osm_id] AS visited_osm_ids
    FROM Geopolygon gp

    UNION ALL

    SELECT
        hierarchy.osm_id,
        GeopolygonHierarchy.parent_osm_id AS ancestor_osm_id,
        hierarchy.depth + 1 AS depth,
        hierarchy.visited_osm_ids || GeopolygonHierarchy.parent_osm_id AS visited_osm_ids
    FROM hierarchy
    JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = hierarchy.ancestor_osm_id
    WHERE GeopolygonHierarchy.parent_osm_id IS NOT NULL
      AND NOT GeopolygonHierarchy.parent_osm_id = ANY(hierarchy.visited_osm_ids)
),
location_paths AS (
    SELECT
        hierarchy.osm_id,
        array_agg(ancestor.name ORDER BY hierarchy.depth DESC) AS path_names,
        string_agg(ancestor.name, ', ' ORDER BY hierarchy.depth DESC) AS display_name,
        (array_agg(ancestor.osm_id ORDER BY hierarchy.depth DESC)
            FILTER (WHERE ancestor.iso_3166_1_code IS NOT NULL))[1] AS country_osm_id,
        (array_agg(ancestor.osm_id ORDER BY hierarchy.depth DESC)
            FILTER (WHERE ancestor.iso_3166_2_code IS NOT NULL))[1] AS subdivision_osm_id
    FROM hierarchy
    JOIN Geopolygon ancestor ON ancestor.osm_id = hierarchy.ancestor_osm_id
    GROUP BY hierarchy.osm_id
)
SELECT
    gp.osm_id,
    GeopolygonHierarchy.parent_osm_id,
    gp.name,
    gp.alt_name,
    CASE
        WHEN gp.iso_3166_1_code IS NOT NULL THEN 'country'
        WHEN gp.iso_3166_1_code IS NULL AND gp.iso_3166_2_code IS NOT NULL THEN 'subdivision'
        ELSE 'municipality'
    END AS location_type,
    gp.admin_level,
    country.name AS country_name,
    COALESCE(gp.iso_3166_1_code, country.iso_3166_1_code) AS country_code,
    subdivision.name AS subdivision_name,
    subdivision.iso_3166_2_code AS subdivision_code,
    location_paths.path_names,
    location_paths.display_name,
    setweight(to_tsvector('english', coalesce(unaccent(location_paths.display_name), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent(gp.name), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent(gp.alt_name), '')), 'B') ||
    setweight(to_tsvector('english', coalesce(unaccent(gp.iso_3166_1_code), '')), 'B') ||
    setweight(to_tsvector('english', coalesce(unaccent(gp.iso_3166_2_code), '')), 'B')
        AS document
FROM Geopolygon gp
LEFT JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = gp.osm_id
LEFT JOIN location_paths ON location_paths.osm_id = gp.osm_id
LEFT JOIN Geopolygon country ON country.osm_id = COALESCE(GeopolygonHierarchy.country_osm_id, location_paths.country_osm_id)
LEFT JOIN Geopolygon subdivision ON subdivision.osm_id = COALESCE(
    GeopolygonHierarchy.subdivision_osm_id,
    location_paths.subdivision_osm_id
)
WHERE
    -- Countries are always kept.
    gp.iso_3166_1_code IS NOT NULL
    -- Subdivisions must resolve to a country.
    OR (
        gp.iso_3166_1_code IS NULL
        AND gp.iso_3166_2_code IS NOT NULL
        AND country.osm_id IS NOT NULL
    )
    -- Municipalities must resolve to both a country and a subdivision.
    OR (
        gp.iso_3166_1_code IS NULL
        AND gp.iso_3166_2_code IS NULL
        AND country.osm_id IS NOT NULL
        AND subdivision.osm_id IS NOT NULL
    );

CREATE UNIQUE INDEX idx_unique_geopolygon_location_search_osm_id ON GeopolygonLocationSearch(osm_id);
CREATE INDEX geopolygon_location_search_document_idx ON GeopolygonLocationSearch USING GIN(document);
CREATE INDEX geopolygon_location_search_country_code_idx ON GeopolygonLocationSearch(country_code);
CREATE INDEX geopolygon_location_search_location_type_idx ON GeopolygonLocationSearch(location_type);
CREATE INDEX geopolygon_location_search_parent_osm_id_idx ON GeopolygonLocationSearch(parent_osm_id);
