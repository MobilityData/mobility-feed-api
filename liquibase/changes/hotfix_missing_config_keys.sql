-- Register the config key so the per-feed FK is satisfied.
INSERT INTO config_key (namespace, key, description)
VALUES ('feed_download', 'http_headers', 'HTTP headers to use when downloading a feed (per-feed override)')
ON CONFLICT (namespace, key) DO NOTHING; -- DEV and PROD already have this key, but QA does not. This is a hotfix to ensure that the key exists in all environments.