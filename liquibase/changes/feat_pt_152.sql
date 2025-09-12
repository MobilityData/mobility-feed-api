-- Add geolocation file feed level columns
ALTER TABLE feed ADD COLUMN IF NOT EXISTS geolocation_file_created_date TIMESTAMP;
ALTER TABLE feed ADD COLUMN IF NOT EXISTS geolocation_file_dataset_id VARCHAR(255);

ALTER TABLE feed
    ADD CONSTRAINT fk_feed_geolocation_file_dataset
    FOREIGN KEY (geolocation_file_dataset_id)
    REFERENCES gtfsdataset(id)
    ON DELETE SET NULL;
