CREATE TABLE IF NOT EXISTS GeoPolygon (
    osm_id INTEGER PRIMARY KEY,
    admin_level INTEGER,
    name VARCHAR(255),
    iso_3166_1_code VARCHAR(3),
    iso_3166_2_code VARCHAR(8),
    geometry GEOMETRY(Geometry, 4326)
);

CREATE INDEX IF NOT EXISTS idx_geopolygon_geometry ON GeoPolygon USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_name_geopolygon ON GeoPolygon (name);
CREATE INDEX IF NOT EXISTS idx_iso_3166_1_code_geopolygon ON GeoPolygon (iso_3166_1_code);
CREATE INDEX IF NOT EXISTS idx_iso_3166_2_code_geopolygon ON GeoPolygon (iso_3166_2_code);
CREATE INDEX IF NOT EXISTS idx_admin_level_geopolygon ON GeoPolygon (admin_level);

CREATE TABLE IF NOT EXISTS OsmLocationGroup (
    group_id VARCHAR(255) PRIMARY KEY,
    group_name VARCHAR(255) NOT NULL  -- e.g. "Canada, Quebec, Montreal"
);

CREATE TABLE IF NOT EXISTS OsmLocationGroupGeopolygon (
    group_id VARCHAR(255) NOT NULL REFERENCES OsmLocationGroup(group_id),
    osm_id INTEGER NOT NULL REFERENCES GeoPolygon(osm_id),
    PRIMARY KEY (group_id, osm_id)
);

CREATE TABLE IF NOT EXISTS FeedOsmLocation (
    feed_id VARCHAR(255) NOT NULL REFERENCES Feed(id),
    group_id VARCHAR(255) NOT NULL REFERENCES OsmLocationGroup(group_id),
    stops_count INTEGER NOT NULL,
    PRIMARY KEY (feed_id, group_id)
);

CREATE TABLE IF NOT EXISTS Stop (
    feed_id VARCHAR(255) NOT NULL REFERENCES feed(id),
    geometry GEOMETRY(Point, 4326) NOT NULL,
    group_id VARCHAR(255) NOT NULL REFERENCES OsmLocationGroup(group_id),
    PRIMARY KEY (feed_id, geometry)
);

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_class WHERE relname = 'feedosmlocation') THEN
        ALTER TABLE FeedOsmLocation RENAME TO FeedOsmLocationGroup;
    END IF;

    IF EXISTS (SELECT FROM pg_class WHERE relname = 'stop') THEN
        ALTER TABLE Stop RENAME TO FeedLocationGroupPoint;
    END IF;
END
$$;
