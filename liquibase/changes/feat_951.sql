CREATE INDEX IF NOT EXISTS idx_feed_osm_location_group_feed_id_stops_count ON feedosmlocationgroup (feed_id, stops_count DESC);

CREATE INDEX IF NOT EXISTS idx_feed_osm_location_group_feed_id ON feedosmlocationgroup (feed_id);

CREATE INDEX IF NOT EXISTS idx_feed_osm_location_group_group_id ON feedosmlocationgroup (group_id);

CREATE INDEX IF NOT EXISTS idx_osm_location_group_group_id ON osmlocationgroup (group_id);

CREATE INDEX IF NOT EXISTS idx_osm_location_group_geopolygon_group_id ON osmlocationgroupgeopolygon (group_id);

CREATE INDEX IF NOT EXISTS idx_osm_location_group_geopolygon_osm_id ON osmlocationgroupgeopolygon (osm_id);
