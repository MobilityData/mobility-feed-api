-- Register the per-feed Parquet worker size key in the existing config_key catalogue.
-- No new table: config_key and config_value_feed are generic. This row only satisfies the
-- FK config_value_feed(namespace, key) -> config_key, without which no value can be
-- written for a feed at all.
--
-- The value is "s", "m" or "l". It may also be an object carrying the same size plus the
-- source that set it, which is how the builder records a size it chose itself.
--
-- No default_value on purpose: one would move the whole catalogue at once, which belongs
-- in the routing table in the code. With no per-feed row, a feed is routed by measurement.
INSERT INTO config_key (namespace, key, description)
VALUES (
    'parquet_builder',
    'size',
    'Parquet build worker size for this feed: "s", "m" or "l", or an object of the same size with the source that set it.'
)
ON CONFLICT (namespace, key) DO NOTHING;
