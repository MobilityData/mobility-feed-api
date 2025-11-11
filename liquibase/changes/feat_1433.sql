-- Add one-to-many feed relation with the licenses

-- Add the 'license_id' column to the 'feed' table if it doesn't exist
ALTER TABLE feed ADD COLUMN IF NOT EXISTS license_id TEXT;


-- Add a foreign key constraint to reference the 'licenses' table
ALTER TABLE feed
ADD CONSTRAINT fk_feed_license
FOREIGN KEY (license_id)
REFERENCES license (id)
ON DELETE SET NULL;