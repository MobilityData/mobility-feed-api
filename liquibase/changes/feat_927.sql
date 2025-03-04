--  Add 'published' to the OperationalStatus enum if it doesn't exist
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
