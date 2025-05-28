-- Add the source of gbfs_version to the gbfsversion table
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gbfs_source') THEN
        CREATE TYPE gbfs_source AS ENUM ('autodiscovery', 'gbfs_versions');
    END IF;
END
$$;
ALTER TABLE gbfsversion DROP COLUMN IF EXISTS source;
ALTER TABLE gbfsversion ADD COLUMN source gbfs_source DEFAULT 'gbfs_versions' NOT NULL;

-- Remove latest tag in gbfsversion table
ALTER TABLE gbfsversion
    DROP COLUMN IF EXISTS latest;

