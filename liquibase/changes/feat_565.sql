ALTER TYPE datatype ADD VALUE IF NOT EXISTS 'gbfs';

-- Create the tables if they do not exist
CREATE TABLE IF NOT EXISTS GBFS_Feed(
    id VARCHAR(255) PRIMARY KEY,
    operator VARCHAR(255),
    operator_url VARCHAR(255),
    auto_discovery_url VARCHAR(255),
    FOREIGN KEY (id) REFERENCES Feed(id)
);

CREATE TABLE IF NOT EXISTS GBFS_Version(
    feed_id VARCHAR(255) NOT NULL,
    version VARCHAR(6),
    url VARCHAR(255),
    PRIMARY KEY (feed_id, version),
    FOREIGN KEY (feed_id) REFERENCES GBFS_Feed(id)
);

-- Rename tables to use convention like GBFSFeed and GBFSVersion
ALTER TABLE GBFS_Feed RENAME TO GBFSFeed;
ALTER TABLE GBFS_Version RENAME TO GBFSVersion;
