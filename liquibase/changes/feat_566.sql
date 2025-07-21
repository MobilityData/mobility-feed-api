CREATE TABLE GBFSSnapshot(
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    feed_id VARCHAR(255) NOT NULL,
    hosted_url VARCHAR(255) NOT NULL,
    downloaded_at TIMESTAMPTZ NOT NULL,
    stable_id VARCHAR(255) NOT NULL UNIQUE,
    FOREIGN KEY (feed_id) REFERENCES GBFSFeed(id)
);

CREATE TABLE GBFSValidationReport(
    id VARCHAR(255) NOT NULL PRIMARY KEY,
    gbfs_snapshot_id VARCHAR(255) NOT NULL,
    validated_at TIMESTAMPTZ NOT NULL,
    report_summary_url VARCHAR(255) NOT NULL,
    FOREIGN KEY (gbfs_snapshot_id) REFERENCES GBFSSnapshot(id)
);

CREATE TABLE GBFSNotice(
    keyword VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    schema_path VARCHAR(255) NOT NULL,
    gbfs_file VARCHAR(255) NOT NULL,
    validation_report_id VARCHAR(255) NOT NULL,
    count INTEGER NOT NULL,
    FOREIGN KEY (validation_report_id) REFERENCES GBFSValidationReport(id),
    PRIMARY KEY (validation_report_id, keyword, gbfs_file, schema_path)
);
