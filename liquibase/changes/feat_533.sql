-- Adding created_at column to Feed table with default value of current timestamp for new records
ALTER TABLE Feed ADD COLUMN created_at TIMESTAMP NULL;