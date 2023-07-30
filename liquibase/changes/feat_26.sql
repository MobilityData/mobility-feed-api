CREATE TYPE DataType AS ENUM ('gtfs', 'gtfs_rt');
CREATE TYPE Status AS ENUM ('active', 'inactive', 'development', 'deprecated');
CREATE TYPE AuthenticationType AS ENUM ('0', '1', '2');

CREATE TABLE Feed (
    id VARCHAR(255) PRIMARY KEY,
    data_type DataType,
    provider VARCHAR(255),
    feed_name VARCHAR(255),
    note VARCHAR(255),
    producer_url VARCHAR(255),
    authentication_type AuthenticationType DEFAULT '0',
    authentication_info_url VARCHAR(255),
    api_key_parameter_name VARCHAR(255),
    license_url VARCHAR(255),
    stable_id VARCHAR(255),
    status Status DEFAULT 'active'
);

CREATE TABLE FeedLog (
    id VARCHAR(255) REFERENCES Feed(id),
    historical_record_time DATE,
    data_type DataType,
    provider VARCHAR(255),
    feed_name VARCHAR(255),
    note VARCHAR(255),
    producer_url VARCHAR(255),
    authentication_type AuthenticationType,
    authentication_info_url VARCHAR(255),
    api_key_parameter_name VARCHAR(255),
    license_url VARCHAR(255),
    stable_id VARCHAR(255),
    status Status,
    PRIMARY KEY (id, historical_record_time)
);

CREATE TABLE GTFSRealtimeFeed (
    id VARCHAR(255) PRIMARY KEY REFERENCES Feed(id)
);

CREATE TABLE EntityType (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE EntityTypeFeed (
    entity_name VARCHAR(255) REFERENCES EntityType(name),
    feed_id VARCHAR(255) REFERENCES GTFSRealtimeFeed(id),
    PRIMARY KEY (entity_name, feed_id)
);

CREATE TABLE GTFSFeed (
    id VARCHAR(255) PRIMARY KEY REFERENCES Feed(id)
);

CREATE TABLE FeedReference (
    gtfs_rt_feed_id VARCHAR(255) REFERENCES GTFSRealtimeFeed(id),
    gtfs_feed_id VARCHAR(255) REFERENCES GTFSFeed(id),
    PRIMARY KEY (gtfs_rt_feed_id, gtfs_feed_id)
);

CREATE TABLE Location (
    id VARCHAR(255) PRIMARY KEY,
    country_code VARCHAR(3),
    subdivision_name VARCHAR(255),
    municipality VARCHAR(255)
);

CREATE TABLE LocationFeed (
    location_id VARCHAR(255) REFERENCES Location(id),
    feed_id VARCHAR(255) REFERENCES Feed(id),
    PRIMARY KEY (location_id, feed_id)
);

CREATE TABLE ExternalID (
    feed_id VARCHAR(255) REFERENCES Feed(id),
    associated_id VARCHAR(255),
    source VARCHAR(255),
    PRIMARY KEY (feed_id, associated_id)
);

CREATE TABLE GTFSDataset (
    id VARCHAR(255) PRIMARY KEY,
    feed_id VARCHAR(255) REFERENCES Feed(id),
    latest BOOLEAN,
    --  SRID 4326 is equivalent to WGS 84
    bounding_box geometry(Polygon, 4326),
    hosted_url VARCHAR(255),
    note VARCHAR(255),
    hash VARCHAR(255),
    download_date TIMESTAMP,
    creation_date TIMESTAMP,
    last_update_date TIMESTAMP,
    stable_id VARCHAR(255)
);

CREATE TABLE Component (
    name VARCHAR(255) PRIMARY KEY
);

CREATE TABLE ComponentGTFSDataset (
    component VARCHAR(255) REFERENCES Component(name),
    dataset_id VARCHAR(255) REFERENCES GTFSDataset(id),
    PRIMARY KEY (component, dataset_id)
);

CREATE TABLE RedirectingID (
    source_id VARCHAR(255) REFERENCES Feed(id),
    target_id VARCHAR(255) REFERENCES Feed(id),
    PRIMARY KEY (source_id, target_id)
);


CREATE INDEX idx_dataset_bounding_box ON GTFSDataset USING gist(bounding_box);
CREATE INDEX idx_dataset_hash ON GTFSDataset(hash);
CREATE INDEX idx_dataset_stable_id ON GTFSDataset(stable_id);
CREATE INDEX idx_feed_stable_id ON Feed(stable_id);
CREATE INDEX idx_location_country_code ON Location(country_code);
CREATE INDEX idx_location_subdivision_name ON Location(subdivision_name);
CREATE INDEX idx_location_municipality ON Location(municipality);