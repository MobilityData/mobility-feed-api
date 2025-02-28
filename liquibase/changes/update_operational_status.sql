-- Add 'published' to the OperationalStatus enum if it doesn't exist
DO $$
BEGIN
    -- Check if the enum already has the 'published' value
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumlabel = 'published'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'operationalstatus')
    ) THEN
        -- Add 'published' to the enum
        ALTER TYPE OperationalStatus ADD VALUE 'published';
        RAISE NOTICE 'Added ''published'' value to OperationalStatus enum';
    ELSE
        RAISE NOTICE 'The ''published'' value already exists in OperationalStatus enum';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to add ''published'' to OperationalStatus enum: %', SQLERRM;
END $$;

-- Update all feeds with NULL operational_status to 'published'
DO $$
DECLARE
    updated_count INTEGER;
BEGIN
    UPDATE Feed
    SET operational_status = 'published'
    WHERE operational_status IS NULL;

    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'Updated % feeds to have operational_status = published', updated_count;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to update feeds with NULL operational_status: %', SQLERRM;
END $$;

-- Refresh the materialized view to reflect the changes
DO $$
BEGIN
    REFRESH MATERIALIZED VIEW FeedSearch;
    RAISE NOTICE 'Refreshed FeedSearch materialized view';
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to refresh FeedSearch materialized view: %', SQLERRM;
END $$;

-- Final success message
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully';
END $$;
