CREATE TABLE GtfsFile
(
    id VARCHAR(255) PRIMARY KEY,
    gtfs_dataset_id VARCHAR(255) NOT NULL REFERENCES GtfsDataset(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL -- Size of the file in bytes
);

ALTER TABLE GtfsDataset
ADD COLUMN zipped_size BIGINT,
ADD COLUMN unzipped_size BIGINT;
