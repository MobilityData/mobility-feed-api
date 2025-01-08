-- The following script creates a PostgreSQL trigger function and trigger to track changes in the `official` field
-- of the `public.feed` table. When the `official` field is updated, the trigger logs details about the change
-- into the `public.officialstatushistory` table.

CREATE OR REPLACE FUNCTION log_official_tag_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.official IS DISTINCT FROM OLD.official THEN
        INSERT INTO public.officialstatushistory (is_official, feed_id, reviewer_email, timestamp, notes)
        VALUES (NEW.official, NEW.id, 'api@mobilitydata.org', NOW(),
                'Official tag changed');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to track changes in the official field of the feed table
CREATE TRIGGER track_official_tag_change
AFTER UPDATE OF official ON public.feed
FOR EACH ROW
EXECUTE FUNCTION log_official_tag_change();


-- Query to update official tag for feeds with contact email in the feed table where the source is mdb

UPDATE public.feed f
SET official = TRUE
FROM public.externalid e
WHERE f.id = e.feed_id
  AND f.feed_contact_email LIKE '%@%'
  AND e.source = 'mdb';
