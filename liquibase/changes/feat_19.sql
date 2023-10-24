CREATE TABLE IF NOT EXISTS dataset_status (
    id SERIAL PRIMARY KEY,
    stable_id VARCHAR(255),
    update_time TIMESTAMP,
    status INTEGER,
    additional_data JSONB
);

CREATE INDEX idx_stable_id ON dataset_status(stable_id);
CREATE INDEX idx_update_time ON dataset_status(update_time);

-- create insert examples
INSERT INTO dataset_status (stable_id, update_time, status, additional_data) VALUES ('test', '2020-01-01 00:00:00', 1, '{"test": "test"}');

