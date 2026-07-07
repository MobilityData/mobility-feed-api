-- Add a custom User-Agent/Referer header override for feeds mdb-3237 through mdb-3293, and mdb-2939,
-- whose producer blocks the default download headers.
INSERT INTO config_value_feed (feed_id, feed_stable_id, namespace, key, value, updated_at)
SELECT
    f.id,
    f.stable_id,
    'feed_download',
    'http_headers',
    '{"Accept": "*/*", "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36", "Accept-Encoding": "gzip"}'::jsonb,
    now()
FROM feed f
WHERE f.stable_id IN (
    SELECT 'mdb-' || generate_series(3237, 3293)
    UNION ALL
    SELECT 'mdb-2939'
)
ON CONFLICT (feed_id, namespace, key) DO NOTHING;
