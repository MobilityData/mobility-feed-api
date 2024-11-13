CREATE TABLE OfficialStatusHistory(
    is_official BOOLEAN NOT NULL,
    feed_id VARCHAR(255) NOT NULL,
    reviewer_email VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    notes VARCHAR(255),
    FOREIGN KEY (feed_id) REFERENCES Feed(id),
    PRIMARY KEY (feed_id, timestamp)
);
