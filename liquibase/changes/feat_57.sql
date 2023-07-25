ALTER TABLE Feed
DROP COLUMN provider;

CREATE TABLE Provider (
    id VARCHAR(255) PRIMARY KEY,
    short_name VARCHAR(255),
    long_name VARCHAR(255)
);

CREATE TABLE ProviderFeed (
    provider_id VARCHAR(255) REFERENCES Provider(id),
    feed_id VARCHAR(255) REFERENCES Feed(id),
    PRIMARY KEY (provider_id, feed_id)
);
