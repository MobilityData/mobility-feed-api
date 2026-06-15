-- Dummy data for the users database, used by local development and tests.
-- Safe to re-run: every statement is idempotent via ON CONFLICT DO NOTHING.

-- Notification types ---------------------------------------------------------
INSERT INTO notification_type (id, description) VALUES
    ('api.announcements',  'General API announcements and platform updates'),
    ('feed.published',     'A new feed has been published'),
    ('feed.updated',       'An existing feed has new data available'),
    ('feed.deprecated',    'A feed has been marked deprecated'),
    ('validation.failed',  'Validation failed for a tracked feed')
ON CONFLICT (id) DO NOTHING;

-- App users ------------------------------------------------------------------
-- IDs intentionally look like Firebase UIDs (28 chars-ish, alphanumeric).
INSERT INTO app_user (id, email, full_name, legacy_org_name, registration_completed_at, email_verified) VALUES
    ('test_user_alice_000000000001', 'alice@example.com', 'Alice Tester', 'Acme Transit',     now() - interval '30 days', true),
    ('test_user_bob_00000000000002', 'bob@example.com',   'Bob Tester',   NULL,               now() - interval '10 days', true),
    ('test_user_carol_000000000003', 'carol@example.com', 'Carol Tester', 'City of Springfield', NULL,                    false),
    ('test_user_dan_00000000000004', 'dan@example.com',   'Dan Tester',   NULL,               now() - interval '2 days',  true)
ON CONFLICT (id) DO NOTHING;

-- Subscriptions --------------------------------------------------------------
INSERT INTO notification_subscription (id, user_id, notification_type_id, filter_params, last_notified_at, active) VALUES
    ('sub_0000000000000000000000000001', 'test_user_alice_000000000001', 'api.announcements', NULL,                                       now() - interval '5 days', true),
    ('sub_0000000000000000000000000002', 'test_user_alice_000000000001', 'feed.updated',      '{"feed_ids": ["mdb-1", "mdb-42"]}'::jsonb, now() - interval '1 day',  true),
    ('sub_0000000000000000000000000003', 'test_user_bob_00000000000002', 'feed.published',    '{"country": "CA"}'::jsonb,                 NULL,                      true),
    ('sub_0000000000000000000000000004', 'test_user_bob_00000000000002', 'validation.failed', '{"feed_ids": ["mdb-7"]}'::jsonb,           now() - interval '3 days', false),
    ('sub_0000000000000000000000000005', 'test_user_dan_00000000000004', 'feed.deprecated',   NULL,                                       NULL,                      true)
ON CONFLICT (id) DO NOTHING;

-- Notification log ----------------------------------------------------------
INSERT INTO notification_log (id, subscription_id, sent_at, channel, status, error_message) VALUES
    ('log_0000000000000000000000000001', 'sub_0000000000000000000000000001', now() - interval '5 days',  'email', 'sent',   NULL),
    ('log_0000000000000000000000000002', 'sub_0000000000000000000000000002', now() - interval '1 day',   'email', 'sent',   NULL),
    ('log_0000000000000000000000000003', 'sub_0000000000000000000000000004', now() - interval '3 days',  'email', 'failed', 'SMTP 550: mailbox unavailable'),
    ('log_0000000000000000000000000004', 'sub_0000000000000000000000000004', now() - interval '2 days',  'email', 'failed', 'SMTP timeout')
ON CONFLICT (id) DO NOTHING;

-- Feature flags ---------------------------------------------------------------
INSERT INTO feature_flag (id, name, description, value_type, default_value) VALUES
    ('beta_editor',    'Beta Editor',        'Enables the experimental feed editor UI',          'boolean', 'false'),
    ('max_results',    'Max Results',        'Maximum number of results returned per query',     'numeric', '100'),
    ('allowed_formats','Allowed Formats',    'Feed formats the user is allowed to submit',       'array',   '["gtfs","gtfs-rt"]'),
    ('ui_theme',       'UI Theme',           'Default UI theme for the user',                    'string',  '"light"'),
    ('extra_config',   'Extra Config',       'Arbitrary extra configuration blob for the user',  'json',    '{}')
ON CONFLICT (id) DO NOTHING;

-- User feature flag assignments (with optional per-user value overrides) ------
-- Alice: beta editor enabled (uses default false → overridden to true), max_results capped at 50
INSERT INTO user_feature_flag (user_id, feature_flag_id, value) VALUES
    ('test_user_alice_000000000001', 'beta_editor',     'true'),
    ('test_user_alice_000000000001', 'max_results',     '50')
ON CONFLICT (user_id, feature_flag_id) DO NOTHING;

-- Bob: beta editor with no value override (uses default false), custom allowed_formats
INSERT INTO user_feature_flag (user_id, feature_flag_id, value) VALUES
    ('test_user_bob_00000000000002', 'beta_editor',      NULL),
    ('test_user_bob_00000000000002', 'allowed_formats',  '["gtfs"]')
ON CONFLICT (user_id, feature_flag_id) DO NOTHING;

-- Dan: custom theme and extra_config blob
INSERT INTO user_feature_flag (user_id, feature_flag_id, value) VALUES
    ('test_user_dan_00000000000004', 'ui_theme',     '"dark"'),
    ('test_user_dan_00000000000004', 'extra_config', '{"debug": true, "beta_notes": "testing phase 2"}')
ON CONFLICT (user_id, feature_flag_id) DO NOTHING;

-- Carol: no feature flag assignments (uses all defaults)
