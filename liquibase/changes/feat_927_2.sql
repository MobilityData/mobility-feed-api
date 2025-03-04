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