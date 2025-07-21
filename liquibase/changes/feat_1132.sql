-- Add 'unpublished' to the OperationalStatus enum if it doesn't exist
DO $$
BEGIN
    -- Check if the enum already has the 'unpublished' value
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum
        WHERE enumlabel = 'unpublished'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'operationalstatus')
    ) THEN
        -- Add 'unpublished' to the enum
        ALTER TYPE OperationalStatus ADD VALUE 'unpublished';
        RAISE NOTICE 'Added ''unpublished'' value to OperationalStatus enum';
    ELSE
        RAISE NOTICE 'The ''unpublished'' value already exists in OperationalStatus enum';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to add ''unpublished'' to OperationalStatus enum: %', SQLERRM;
END $$;
