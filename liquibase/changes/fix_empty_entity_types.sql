-- Blank entity types make every API response carrying the feed fail the vp/tu/sa enum.
-- EntityTypeFeed.entity_name has no ON DELETE rule, so the join rows go first.

DELETE FROM EntityTypeFeed
WHERE btrim(entity_name) = '';

DELETE FROM EntityType
WHERE btrim(name) = '';

ALTER TABLE EntityType
    ADD CONSTRAINT entitytype_name_valid
    CHECK (name IN ('vp', 'tu', 'sa'));

REFRESH MATERIALIZED VIEW CONCURRENTLY feedsearch;
