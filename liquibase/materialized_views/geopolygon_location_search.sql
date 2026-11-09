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
-- Continents are not geopolygons: they come from the continent table, with their fixed negative location_id. A
-- country's parent is its continent (NULL when the country has no continent in the classification).
locations AS (
    SELECT
        gp.osm_id,
        CASE
            WHEN gp.iso_3166_1_code IS NOT NULL THEN continent.location_id
            ELSE COALESCE(parent_boundary.retained_osm_id, GeopolygonHierarchy.parent_osm_id)
        END AS parent_osm_id,
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
        continent.code AS continent_code,
        continent.slug AS continent_slug,
        continent.name AS continent_name
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
    LEFT JOIN continent ON continent.code = country_continent.continent_code
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
-- hyphen; a name without any ASCII letter or digit falls back to the osm_id. When two or more locations share the
-- same parent (the countries of a continent are siblings; continents, countries without continent and other
-- parentless locations form a single group) and the same slug, each of them gets '--<osm_id>' appended. A name never
-- produces '--' (runs of other characters collapse into one hyphen), so a suffixed slug can neither equal another
-- location's natural slug nor another suffixed slug: siblings never share a slug. A continent's slug is fixed: it
-- never gets the suffix, only its colliding siblings do. Collisions are counted over every row of the view, not only
-- the rows with feeds, so a slug does not change when feeds are added or removed.
location_base_slugs AS (
    SELECT
        locations.osm_id,
        locations.parent_osm_id,
        FALSE AS is_continent,
        COALESCE(
            NULLIF(trim(BOTH '-' FROM lower(regexp_replace(unaccent(locations.name), '[^a-zA-Z0-9]+', '-', 'g'))), ''),
            locations.osm_id::text
        ) AS base_slug
    FROM locations

    UNION ALL

    SELECT
        continent.location_id AS osm_id,
        NULL::integer AS parent_osm_id,
        TRUE AS is_continent,
        continent.slug::text AS base_slug
    FROM continent
),
location_slugs AS (
    SELECT
        location_base_slugs.osm_id,
        CASE
            WHEN location_base_slugs.is_continent THEN location_base_slugs.base_slug
            WHEN count(*) OVER (
                PARTITION BY location_base_slugs.parent_osm_id, location_base_slugs.base_slug
            ) > 1 THEN location_base_slugs.base_slug || '--' || location_base_slugs.osm_id
            ELSE location_base_slugs.base_slug
        END AS slug
    FROM location_base_slugs
),
-- Ancestors that are not rows of the view (e.g. an intermediate admin level, or a duplicate country boundary) still
-- need a slug in path_slugs. They follow the same rules (id fallback, '--<osm_id>' suffix) among the geopolygons with
-- the same parent, whether rows of the view or not. Duplicate country boundaries never appear as ancestors: they
-- resolve to the retained boundary.
geopolygon_base_slugs AS (
    SELECT
        gp.osm_id,
        GeopolygonHierarchy.parent_osm_id,
        COALESCE(
            NULLIF(trim(BOTH '-' FROM lower(regexp_replace(unaccent(gp.name), '[^a-zA-Z0-9]+', '-', 'g'))), ''),
            gp.osm_id::text
        ) AS base_slug
    FROM Geopolygon gp
    LEFT JOIN GeopolygonHierarchy ON GeopolygonHierarchy.osm_id = gp.osm_id
),
geopolygon_slugs AS (
    SELECT
        geopolygon_base_slugs.osm_id,
        CASE
            WHEN count(*) OVER (
                PARTITION BY geopolygon_base_slugs.parent_osm_id, geopolygon_base_slugs.base_slug
            ) > 1 THEN geopolygon_base_slugs.base_slug || '--' || geopolygon_base_slugs.osm_id
            ELSE geopolygon_base_slugs.base_slug
        END AS slug
    FROM geopolygon_base_slugs
),
-- path_slugs is aligned with path_names: same ancestors, same order.
location_path_slugs AS (
    SELECT
        location_ancestors.osm_id,
        array_agg(COALESCE(location_slugs.slug, geopolygon_slugs.slug) ORDER BY location_ancestors.depth DESC)
            AS path_slugs
    FROM location_ancestors
    JOIN locations ON locations.osm_id = location_ancestors.osm_id
    JOIN geopolygon_slugs ON geopolygon_slugs.osm_id = location_ancestors.ancestor_osm_id
    LEFT JOIN location_slugs ON location_slugs.osm_id = location_ancestors.ancestor_osm_id
    GROUP BY location_ancestors.osm_id
),
-- path_names and path_slugs start with the continent, when the location's country has one. display_name starts at
-- the country.
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
        CASE
            WHEN locations.continent_name IS NULL THEN locations.path_names
            ELSE ARRAY[locations.continent_name]::varchar[] || locations.path_names
        END AS path_names,
        locations.display_name,
        locations.continent_code,
        location_slugs.slug,
        CASE
            WHEN locations.continent_slug IS NULL THEN location_path_slugs.path_slugs
            ELSE ARRAY[locations.continent_slug::text] || location_path_slugs.path_slugs
        END AS path_slugs,
        setweight(to_tsvector('english', coalesce(unaccent(locations.display_name), '')), 'A') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.name), '')), 'A') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.alt_name), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_1_code), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(unaccent(locations.iso_3166_2_code), '')), 'B')
            AS document
    FROM locations
    JOIN location_slugs ON location_slugs.osm_id = locations.osm_id
    LEFT JOIN location_path_slugs ON location_path_slugs.osm_id = locations.osm_id

    UNION ALL

    -- The continents: admin level 0, so that they sort before the countries; no parent and no ISO code.
    SELECT
        continent.location_id AS osm_id,
        NULL::integer AS parent_osm_id,
        continent.name::varchar(255) AS name,
        NULL::varchar(255) AS alt_name,
        'continent'::text AS location_type,
        0 AS admin_level,
        NULL::varchar(255) AS country_name,
        NULL::varchar(3) AS country_code,
        NULL::varchar(255) AS subdivision_name,
        NULL::varchar(8) AS subdivision_code,
        ARRAY[continent.name]::varchar[] AS path_names,
        continent.name::text AS display_name,
        continent.code AS continent_code,
        location_slugs.slug,
        ARRAY[location_slugs.slug] AS path_slugs,
        setweight(to_tsvector('english', coalesce(unaccent(continent.name), '')), 'A') AS document
    FROM continent
    JOIN location_slugs ON location_slugs.osm_id = continent.location_id
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
    -- The path of /v1/locations/lookup and of the location_path parameter of /v1/search. Slugs are lowercase, so a
    -- lowercased input matches it exactly.
    array_to_string(location_rows.path_slugs, '/') AS path,
    location_rows.document
FROM location_rows;

CREATE UNIQUE INDEX idx_unique_geopolygon_location_search_osm_id ON GeopolygonLocationSearch(osm_id);
CREATE INDEX geopolygon_location_search_document_idx ON GeopolygonLocationSearch USING GIN(document);
CREATE INDEX geopolygon_location_search_country_code_idx ON GeopolygonLocationSearch(country_code);
CREATE INDEX geopolygon_location_search_location_type_idx ON GeopolygonLocationSearch(location_type);
CREATE INDEX geopolygon_location_search_parent_osm_id_idx ON GeopolygonLocationSearch(parent_osm_id);
CREATE INDEX geopolygon_location_search_continent_code_idx ON GeopolygonLocationSearch(continent_code);
CREATE INDEX geopolygon_location_search_path_idx ON GeopolygonLocationSearch(path);
