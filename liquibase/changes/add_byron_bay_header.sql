-- Add a custom User-Agent/Referer header override for feeds mdb-3516
-- whose producer blocks the default download headers.
INSERT INTO config_value_feed (feed_id, feed_stable_id, namespace, key, value, updated_at)
SELECT
    f.id,
    f.stable_id,
    'feed_download',
    'http_headers',
    '{"Accept": "*/*", "User-Agent": "MobilityDatabaseAgent"}'::jsonb,
    now()
FROM feed f
WHERE f.stable_id='mdb-3516'
ON CONFLICT (feed_id, namespace, key) DO NOTHING;
