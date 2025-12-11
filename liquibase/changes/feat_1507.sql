-- Change hosted_url column type to text to accommodate longer URLs
ALTER TABLE gtfsdataset ALTER COLUMN hosted_url TYPE text;