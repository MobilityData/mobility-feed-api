ALTER TYPE datatype ADD VALUE 'gbfs';

CREATE TABLE GBFS_Feed(
    id VARCHAR(255) PRIMARY KEY,
    operator VARCHAR(255),
    operator_url VARCHAR(255),
    FOREIGN KEY (id) REFERENCES Feed(id)
);

CREATE TABLE GBFS_Version(
    feed_id VARCHAR(255) NOT NULL,
    version VARCHAR(6),
    auto_discovery_url VARCHAR(255),
    PRIMARY KEY (feed_id, version),
    FOREIGN KEY (feed_id) REFERENCES GBFS_Feed(id)
);
