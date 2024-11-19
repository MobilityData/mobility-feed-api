DROP TABLE IF EXISTS AdminGeography;
CREATE TABLE IF NOT EXISTS AdminGeography (
    id VARCHAR(255) PRIMARY KEY,
    location_id VARCHAR(255),
    geonames_id VARCHAR(255) NOT NULL UNIQUE,
    coordinates GEOMETRY(GeometryCollection, 4326),
    FOREIGN KEY (location_id) REFERENCES Location(id)
);

CREATE INDEX IF NOT EXISTS idx_admin_geography_geom ON AdminGeography USING GIST (coordinates);

CREATE TABLE IF NOT EXISTS SupportedReverseGeocodingCountry (
    country_code VARCHAR(3) PRIMARY KEY
);