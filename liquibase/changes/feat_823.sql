DROP TABLE IF EXISTS GeoPolygon;
CREATE TABLE IF NOT EXISTS GeoPolygon (
    osm_id INTEGER PRIMARY KEY,
    admin_level INTEGER,
    name VARCHAR(255),
    iso_3166_1_code VARCHAR(3),
    iso_3166_2_code VARCHAR(5),
    geometry GEOGRAPHY
);
CREATE INDEX IF NOT EXISTS idx_geo_polygon_geom ON GeoPolygon USING GIST (geometry);
drop index if exists idx_geo_polygon_geom;
ALTER TABLE geopolygon
ALTER COLUMN geometry TYPE geometry USING geometry::geometry;
ALTER TABLE geopolygon
ALTER COLUMN geometry TYPE geometry USING ST_SetSRID(geometry::geometry, 4326);
CREATE INDEX if not exists idx_geopolygon_geometry ON geopolygon USING GIST (geometry);
alter table geopolygon
alter column iso_3166_2_code type varchar(8);
