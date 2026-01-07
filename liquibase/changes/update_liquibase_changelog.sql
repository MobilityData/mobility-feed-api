-- This script updates the databasechangelog aligning all environments with the correct primary key

-- Drop the existing PK if it exists
ALTER TABLE databasechangelog
DROP CONSTRAINT IF EXISTS databasechangelog_pkey;

-- Add the correct composite primary key
ALTER TABLE databasechangelog
ADD CONSTRAINT databasechangelog_pkey
PRIMARY KEY (id, author, filename);
