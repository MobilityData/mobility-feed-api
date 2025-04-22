DO $$
BEGIN
    REFRESH MATERIALIZED VIEW FeedSearch;
    RAISE NOTICE 'Refreshed FeedSearch materialized view';
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to refresh FeedSearch materialized view: %', SQLERRM;
END $$;
