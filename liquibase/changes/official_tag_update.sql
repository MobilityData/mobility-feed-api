-- Query to update official tag for feeds with contact email in the feed table where the source is mdb

UPDATE public.feed f
SET 
  official = TRUE
  official_updated_at = NOW()
FROM public.externalid e
WHERE f.id = e.feed_id
  AND f.feed_contact_email LIKE '%@%'
  AND e.source = 'mdb';

-- Query to insert a record in officialstatushistory table for feeds with contact email in the feed table where the source is mdb
INSERT INTO public.officialstatushistory (is_official, feed_id, reviewer_email, timestamp, notes)
SELECT
    official,
    id,
    'api@mobilitydata.org',
    NOW(),
    'Official status tag changed'
FROM public.feed
WHERE feed_contact_email LIKE '%@%'
  AND official = TRUE;
