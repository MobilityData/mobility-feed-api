-- GTFS-RT feeds carrying a blank entity type make the API return HTTP 500.
-- DatabaseCatalogAPI.yaml restricts entity_types to vp/tu/sa and the generated Pydantic models
-- validate it, so a single blank name fails serialization for the feed and for every unrelated
-- feed on the same /v1/search page.
--
-- EntityTypeFeed.entity_name references EntityType(name) with no ON DELETE rule (only feed_id
-- cascades), so the join rows have to go first.

DELETE FROM EntityTypeFeed
WHERE btrim(entity_name) = '';

DELETE FROM EntityType
WHERE btrim(name) = '';

-- Mirrors the entity_types enum in docs/DatabaseCatalogAPI.yaml and
-- api/src/shared/common/entity_type_enum.py, so no writer can reintroduce an unservable value.
ALTER TABLE EntityType
    ADD CONSTRAINT entitytype_name_valid
    CHECK (name IN ('vp', 'tu', 'sa'));

-- feedsearch aggregates entity_name into its `entities` column, which /v1/search returns verbatim.
REFRESH MATERIALIZED VIEW feedsearch;
