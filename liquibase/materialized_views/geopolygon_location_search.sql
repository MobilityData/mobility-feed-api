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
            FILTER (WHERE ancestor.iso_3166_2_code IS NOT NULL
                AND ancestor.iso_3166_1_code IS NULL))[1] AS subdivision_osm_id
    FROM hierarchy
    JOIN Geopolygon ancestor ON ancestor.osm_id = hierarchy.ancestor_osm_id
    GROUP BY hierarchy.osm_id
),
-- Some country codes have several boundaries (e.g. an overseas region mapped at several admin levels):
-- only the one with the lowest admin level, then the lowest osm_id, is kept as the country.
country_boundaries AS (
    SELECT
        gp.osm_id,
        row_number() OVER (
            PARTITION BY gp.iso_3166_1_code
            ORDER BY gp.admin_level ASC NULLS LAST, gp.osm_id ASC
        ) AS boundary_rank
    FROM Geopolygon gp
    WHERE gp.iso_3166_1_code IS NOT NULL
),
locations AS (
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
        gp.iso_3166_1_code,
        gp.iso_3166_2_code
    FROM Geopolygon gp
    LEFT JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = gp.osm_id
    LEFT JOIN location_paths ON location_paths.osm_id = gp.osm_id
    LEFT JOIN country_boundaries ON country_boundaries.osm_id = gp.osm_id
    LEFT JOIN Geopolygon country ON country.osm_id = COALESCE(GeopolygonHierarchy.country_osm_id, location_paths.country_osm_id)
    LEFT JOIN Geopolygon subdivision ON subdivision.osm_id = COALESCE(
        GeopolygonHierarchy.subdivision_osm_id,
        location_paths.subdivision_osm_id
    )
    WHERE
        -- Countries are kept once per country code.
        (gp.iso_3166_1_code IS NOT NULL AND country_boundaries.boundary_rank = 1)
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
        )
),
-- Slugs: the name lowercased, without accents, with every run of non-alphanumeric characters replaced by a single
-- hyphen. When two or more locations share the same parent (countries and other parentless locations form a single
-- group) and the same base slug, each of them gets '-<osm_id>' appended, so that siblings never share a slug.
-- Collisions are counted over every row of the view, not only the rows with feeds, so a slug does not change when
-- feeds are added or removed. A name without any ASCII letter or digit falls back to the osm_id.
location_base_slugs AS (
    SELECT
        locations.osm_id,
        locations.parent_osm_id,
        NULLIF(trim(BOTH '-' FROM lower(regexp_replace(unaccent(locations.name), '[^a-zA-Z0-9]+', '-', 'g'))), '')
            AS base_slug
    FROM locations
),
location_slugs AS (
    SELECT
        location_base_slugs.osm_id,
        CASE
            WHEN location_base_slugs.base_slug IS NULL THEN location_base_slugs.osm_id::text
            WHEN count(*) OVER (
                PARTITION BY location_base_slugs.parent_osm_id, location_base_slugs.base_slug
            ) > 1 THEN location_base_slugs.base_slug || '-' || location_base_slugs.osm_id
            ELSE location_base_slugs.base_slug
        END AS slug
    FROM location_base_slugs
),
-- Ancestors that are not rows of the view (e.g. an intermediate admin level, or a duplicate country boundary) still
-- need a slug in path_slugs. They get the same base slug, and the '-<osm_id>' suffix when another geopolygon with the
-- same parent, whether a row of the view or not, has the same base slug.
geopolygon_base_slugs AS (
    SELECT
        gp.osm_id,
        GeopolygonHierarchy.parent_osm_id,
        NULLIF(trim(BOTH '-' FROM lower(regexp_replace(unaccent(gp.name), '[^a-zA-Z0-9]+', '-', 'g'))), '')
            AS base_slug
    FROM Geopolygon gp
    LEFT JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = gp.osm_id
),
geopolygon_slugs AS (
    SELECT
        geopolygon_base_slugs.osm_id,
        CASE
            WHEN geopolygon_base_slugs.base_slug IS NULL THEN geopolygon_base_slugs.osm_id::text
            WHEN count(*) OVER (
                PARTITION BY geopolygon_base_slugs.parent_osm_id, geopolygon_base_slugs.base_slug
            ) > 1 THEN geopolygon_base_slugs.base_slug || '-' || geopolygon_base_slugs.osm_id
            ELSE geopolygon_base_slugs.base_slug
        END AS slug
    FROM geopolygon_base_slugs
),
-- path_slugs is aligned with path_names: same ancestors, same order.
location_path_slugs AS (
    SELECT
        hierarchy.osm_id,
        array_agg(COALESCE(location_slugs.slug, geopolygon_slugs.slug) ORDER BY hierarchy.depth DESC) AS path_slugs
    FROM hierarchy
    JOIN locations ON locations.osm_id = hierarchy.osm_id
    JOIN geopolygon_slugs ON geopolygon_slugs.osm_id = hierarchy.ancestor_osm_id
    LEFT JOIN location_slugs ON location_slugs.osm_id = hierarchy.ancestor_osm_id
    GROUP BY hierarchy.osm_id
)
SELECT
    locations.osm_id,
    locations.parent_osm_id,
    locations.name,
    locations.alt_name,
    locations.location_type,
    locations.admin_level,
    locations.country_name,
    locations.country_code,
    locations.subdivision_name,
    locations.subdivision_code,
    locations.path_names,
    locations.display_name,
    country_continent.continent_code,
    location_slugs.slug,
    location_path_slugs.path_slugs,
    -- The path parameter of /v1/locations. Slugs are lowercase, so a lowercased input matches it exactly.
    array_to_string(location_path_slugs.path_slugs, '/') AS path,
    setweight(to_tsvector('english', coalesce(unaccent(locations.display_name), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent(locations.name), '')), 'A') ||
    setweight(to_tsvector('english', coalesce(unaccent(locations.alt_name), '')), 'B') ||
    setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_1_code), '')), 'B') ||
    setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_2_code), '')), 'B')
        AS document
FROM locations
JOIN location_slugs ON location_slugs.osm_id = locations.osm_id
LEFT JOIN location_path_slugs ON location_path_slugs.osm_id = locations.osm_id
LEFT JOIN country_continent ON country_continent.country_code = locations.country_code;

CREATE UNIQUE INDEX idx_unique_geopolygon_location_search_osm_id ON GeopolygonLocationSearch(osm_id);
CREATE INDEX geopolygon_location_search_document_idx ON GeopolygonLocationSearch USING GIN(document);
CREATE INDEX geopolygon_location_search_country_code_idx ON GeopolygonLocationSearch(country_code);
CREATE INDEX geopolygon_location_search_location_type_idx ON GeopolygonLocationSearch(location_type);
CREATE INDEX geopolygon_location_search_parent_osm_id_idx ON GeopolygonLocationSearch(parent_osm_id);
CREATE INDEX geopolygon_location_search_continent_code_idx ON GeopolygonLocationSearch(continent_code);
CREATE INDEX geopolygon_location_search_path_idx ON GeopolygonLocationSearch(path);
