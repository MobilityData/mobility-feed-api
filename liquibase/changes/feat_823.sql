CREATE TABLE IF NOT EXISTS GeoPolygon (
    osm_id INTEGER PRIMARY KEY,
    admin_level INTEGER,
    name VARCHAR(255),
    iso_3166_1_code VARCHAR(3),
    iso_3166_2_code VARCHAR(8),
    geometry GEOMETRY(Geometry, 4326)
);

CREATE INDEX IF NOT EXISTS idx_geopolygon_geometry ON GeoPolygon USING GIST (geometry);
