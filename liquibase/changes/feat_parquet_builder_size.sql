-- Register the per-feed Parquet worker size key in the existing config_key catalogue.
-- No new table: config_key and config_value_feed are generic. This row only satisfies
-- the FK config_value_feed(namespace, key) -> config_key, so an override can be set.
--
-- Values are 'm' or 'l'. A value set for a feed decides that feed's worker size on its
-- own, whichever way it differs from what the builder would have measured. No
-- default_value, so a feed with no row is routed by measurement.
INSERT INTO config_key (namespace, key, description)
VALUES (
    'parquet_builder',
    'size',
    'Parquet build worker size for this feed: "m" or "l". Overrides the size chosen by measurement.'
)
ON CONFLICT (namespace, key) DO NOTHING;
