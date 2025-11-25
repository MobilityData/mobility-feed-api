-- Set operational_status to published for tfs feeds
UPDATE feed
SET operational_status = 'published'
WHERE stable_id like 'tfs-%';