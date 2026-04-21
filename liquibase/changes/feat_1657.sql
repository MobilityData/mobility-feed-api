-- Add MD5 hash column to GTFSDataset table (issue #1657)
-- Many clients rely on MD5 as it is a common hash algorithm for cloud and storage services.
-- The SHA-256 hash is already stored in the `hash` column.
ALTER TABLE Gtfsdataset
    ADD COLUMN IF NOT EXISTS hash_md5 VARCHAR(255);
