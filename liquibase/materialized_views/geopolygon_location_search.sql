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
-- Some country codes have several boundaries (e.g. an overseas region mapped at several admin levels):
-- only the one with the lowest admin level, then the lowest osm_id, is kept as the country. The other boundaries
-- resolve to it (retained_osm_id) wherever they appear as a parent or an ancestor, so that their sub-areas are
-- children of the kept country and their paths go through it.
country_boundaries AS (
    SELECT
        gp.osm_id,
        row_number() OVER country_code_boundaries AS boundary_rank,
        first_value(gp.osm_id) OVER country_code_boundaries AS retained_osm_id
    FROM Geopolygon gp
    WHERE gp.iso_3166_1_code IS NOT NULL
    WINDOW country_code_boundaries AS (
        PARTITION BY gp.iso_3166_1_code
        ORDER BY gp.admin_level ASC NULLS LAST, gp.osm_id ASC
    )
),
-- The ancestors of every geopolygon (itself included), with duplicate country boundaries resolved to the retained
-- one and counted once, at their highest depth.
location_ancestors AS (
    SELECT
        hierarchy.osm_id,
        COALESCE(country_boundaries.retained_osm_id, hierarchy.ancestor_osm_id) AS ancestor_osm_id,
        max(hierarchy.depth) AS depth
    FROM hierarchy
    LEFT JOIN country_boundaries ON country_boundaries.osm_id = hierarchy.ancestor_osm_id
    GROUP BY hierarchy.osm_id, COALESCE(country_boundaries.retained_osm_id, hierarchy.ancestor_osm_id)
),
location_paths AS (
    SELECT
        location_ancestors.osm_id,
        array_agg(ancestor.name ORDER BY location_ancestors.depth DESC) AS path_names,
        string_agg(ancestor.name, ', ' ORDER BY location_ancestors.depth DESC) AS display_name,
        (array_agg(ancestor.osm_id ORDER BY location_ancestors.depth DESC)
            FILTER (WHERE ancestor.iso_3166_1_code IS NOT NULL))[1] AS country_osm_id,
        (array_agg(ancestor.osm_id ORDER BY location_ancestors.depth DESC)
            FILTER (WHERE ancestor.iso_3166_2_code IS NOT NULL
                AND ancestor.iso_3166_1_code IS NULL))[1] AS subdivision_osm_id
    FROM location_ancestors
    JOIN Geopolygon ancestor ON ancestor.osm_id = location_ancestors.ancestor_osm_id
    GROUP BY location_ancestors.osm_id
),
-- A location's continent comes from the country_continent classification of its country (NULL when the country has
-- none). Continents are not rows of this view: /v1/locations reads them from the continent table.
locations AS (
    SELECT
        gp.osm_id,
        -- A sub-area of a discarded duplicate country boundary is a child of the retained one.
        COALESCE(parent_boundary.retained_osm_id, GeopolygonHierarchy.parent_osm_id) AS parent_osm_id,
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
        gp.iso_3166_2_code,
        country_continent.continent_code
    FROM Geopolygon gp
    LEFT JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = gp.osm_id
    LEFT JOIN location_paths ON location_paths.osm_id = gp.osm_id
    LEFT JOIN country_boundaries ON country_boundaries.osm_id = gp.osm_id
    LEFT JOIN country_boundaries parent_boundary ON parent_boundary.osm_id = GeopolygonHierarchy.parent_osm_id
    LEFT JOIN country_boundaries hierarchy_country ON hierarchy_country.osm_id = GeopolygonHierarchy.country_osm_id
    LEFT JOIN Geopolygon country ON country.osm_id = COALESCE(
        hierarchy_country.retained_osm_id,
        GeopolygonHierarchy.country_osm_id,
        location_paths.country_osm_id
    )
    LEFT JOIN Geopolygon subdivision ON subdivision.osm_id = COALESCE(
        GeopolygonHierarchy.subdivision_osm_id,
        location_paths.subdivision_osm_id
    )
    LEFT JOIN country_continent ON country_continent.country_code = COALESCE(gp.iso_3166_1_code, country.iso_3166_1_code)
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
-- Slugs, the URL segments of the location directory. A country's slug is its ISO 3166-1 code, lowercased (`fr`).
-- Any other area's slug starts with its OSM id, which identifies it, followed by its name for readability: the name
-- lowercased, without accents, with every run of non-alphanumeric characters replaced by a hyphen (`71525-paris`).
-- A name without any ASCII letter or digit leaves the OSM id alone. The id makes every slug unique, so the name part
-- can change (an OSM rename) without making two places share a slug.
geopolygon_slugs AS (
    SELECT
        gp.osm_id,
        CASE
            WHEN gp.iso_3166_1_code IS NOT NULL THEN lower(gp.iso_3166_1_code)
            ELSE gp.osm_id::text || COALESCE(
                '-' || NULLIF(trim(BOTH '-' FROM lower(regexp_replace(unaccent(gp.name), '[^a-zA-Z0-9]+', '-', 'g'))), ''),
                ''
            )
        END AS slug
    FROM Geopolygon gp
),
-- path_slugs is aligned with path_names: same ancestors, same order, from the country down. Ancestors that are not rows
-- of this view (e.g. an intermediate admin level) get a slug by the same rules.
location_path_slugs AS (
    SELECT
        location_ancestors.osm_id,
        array_agg(geopolygon_slugs.slug ORDER BY location_ancestors.depth DESC) AS path_slugs
    FROM location_ancestors
    JOIN geopolygon_slugs ON geopolygon_slugs.osm_id = location_ancestors.ancestor_osm_id
    GROUP BY location_ancestors.osm_id
),
location_rows AS (
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
        locations.continent_code,
        geopolygon_slugs.slug,
        location_path_slugs.path_slugs,
        setweight(to_tsvector('english', coalesce(unaccent(locations.display_name), '')), 'A') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.name), '')), 'A') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.alt_name), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_1_code), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_2_code), '')), 'B')
            AS document
    FROM locations
    JOIN geopolygon_slugs ON geopolygon_slugs.osm_id = locations.osm_id
    LEFT JOIN location_path_slugs ON location_path_slugs.osm_id = locations.osm_id
)
SELECT
    location_rows.osm_id,
    location_rows.parent_osm_id,
    location_rows.name,
    location_rows.alt_name,
    location_rows.location_type,
    location_rows.admin_level,
    location_rows.country_name,
    location_rows.country_code,
    location_rows.subdivision_name,
    location_rows.subdivision_code,
    location_rows.path_names,
    location_rows.display_name,
    location_rows.continent_code,
    location_rows.slug,
    location_rows.path_slugs,
    location_rows.document
FROM location_rows;

CREATE UNIQUE INDEX idx_unique_geopolygon_location_search_osm_id ON GeopolygonLocationSearch(osm_id);
CREATE INDEX geopolygon_location_search_document_idx ON GeopolygonLocationSearch USING GIN(document);
CREATE INDEX geopolygon_location_search_country_code_idx ON GeopolygonLocationSearch(country_code);
CREATE INDEX geopolygon_location_search_location_type_idx ON GeopolygonLocationSearch(location_type);
CREATE INDEX geopolygon_location_search_parent_osm_id_idx ON GeopolygonLocationSearch(parent_osm_id);
CREATE INDEX geopolygon_location_search_continent_code_idx ON GeopolygonLocationSearch(continent_code);
