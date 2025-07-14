DROP TABLE IF EXISTS GtfsFile;
CREATE TABLE GtfsFile
(
    id VARCHAR(255) PRIMARY KEY,
    gtfs_dataset_id VARCHAR(255) NOT NULL REFERENCES GtfsDataset(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL
);

ALTER TABLE GtfsDataset DROP COLUMN IF EXISTS zipped_size;
ALTER TABLE GtfsDataset DROP COLUMN IF EXISTS unzipped_size;
ALTER TABLE GtfsDataset DROP COLUMN IF EXISTS zipped_size_bytes;
ALTER TABLE GtfsDataset DROP COLUMN IF EXISTS unzipped_size_bytes;
ALTER TABLE GtfsDataset
ADD COLUMN zipped_size_bytes BIGINT,
ADD COLUMN unzipped_size_bytes BIGINT;

