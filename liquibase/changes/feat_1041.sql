-- Description: This script will update the database schema to include the new tables and columns required for the new
-- GBFS schema

-- 1. Drop the tables that will be recreated with the new schema
DROP TABLE IF EXISTS
    GBFSNotice,
    GBFSValidationReport,
    GBFSSnapshot,
    GBFSVersion,
    GBFSEndpoint,
    GBFSFeedLatestVersion,
    GBFSFeedHTTPAccessLog,
    GBFSEndpointHTTPAccessLog,
    HTTPAccessLog;

-- 2. Update the tables with the new schema
-- 2.1 Recreating the GBFSVersion table
CREATE TABLE GBFSVersion(
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    feed_id VARCHAR(255) NOT NULL REFERENCES GBFSFeed(id) MATCH SIMPLE ON DELETE CASCADE, -- Link to the feed that this version belongs to
    version VARCHAR(6) NOT NULL,
    url TEXT NOT NULL,
    latest BOOLEAN NOT NULL DEFAULT FALSE, -- Whether the version is the latest or not
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2.2 Creating the GBFSEndpoint table
CREATE TABLE GBFSEndpoint(
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    gbfs_version_id VARCHAR(255) NOT NULL REFERENCES GBFSVersion(id) MATCH SIMPLE ON DELETE CASCADE, -- Link to the version that this endpoint belongs to
    url TEXT NOT NULL, -- URL of the endpoint
    language VARCHAR(35), -- Language BCP 47 of the endpoint, if applicable
    name VARCHAR(255) NOT NULL, -- Name of the endpoint
    is_feature BOOLEAN NOT NULL DEFAULT FALSE -- Whether the endpoint represents a GBFS feature or not
);

-- 2.3 Recreating the GBFSValidationReport table
CREATE TABLE GBFSValidationReport(
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    gbfs_version_id VARCHAR(255) NOT NULL REFERENCES GBFSVersion(id) MATCH SIMPLE ON DELETE CASCADE, -- Link to the version that this report belongs to
    validated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report_summary_url VARCHAR(255) NOT NULL,
    total_errors_count INTEGER NOT NULL,
    validator_version VARCHAR(10) NOT NULL
);

-- 2.4 Recreating the GBFSNotice table
CREATE TABLE GBFSNotice(
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    schema_path VARCHAR(255) NOT NULL,
    gbfs_file VARCHAR(255) NOT NULL,
    validation_report_id VARCHAR(255) NOT NULL REFERENCES GBFSValidationReport(id) MATCH SIMPLE ON DELETE CASCADE,
    count INTEGER NOT NULL
);

-- 2.5 Create HTTPAccessLog Table
CREATE TABLE IF NOT EXISTS HTTPAccessLog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_method VARCHAR(10) NOT NULL,
    request_url TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms FLOAT,  -- Nullable if request failed early
    error_message TEXT,
    response_size_bytes INTEGER  -- Nullable if request failed early
);

-- 2.6 Link the GBFSFeed table to the HTTPAccessLog table
-- This will help us track the autodiscovery url that are not accessible
CREATE TABLE IF NOT EXISTS GBFSFeedHTTPAccessLog (
    http_access_log UUID NOT NULL REFERENCES HTTPAccessLog(id) MATCH SIMPLE ON DELETE CASCADE,
    gbfs_feed_id VARCHAR(255) NOT NULL REFERENCES GBFSFeed(id) MATCH SIMPLE ON DELETE CASCADE,
    PRIMARY KEY (http_access_log, gbfs_feed_id)
);

-- 2.7 Link the GBFSEndpoint table to the HTTPAccessLog table
-- This will help us compute latency for each endpoint
CREATE TABLE IF NOT EXISTS GBFSEndpointHTTPAccessLog (
    http_access_log UUID NOT NULL REFERENCES HTTPAccessLog(id) ON DELETE CASCADE,
    gbfs_endpoint_id VARCHAR(255) NOT NULL REFERENCES GBFSEndpoint(id) ON DELETE CASCADE,
    PRIMARY KEY (http_access_log, gbfs_endpoint_id)
);