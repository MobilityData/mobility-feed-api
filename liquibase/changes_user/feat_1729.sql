-- Seed 'api.announcements' notification type (idempotent).
INSERT INTO notification_type (id, description)
VALUES ('api.announcements', 'API announcements')
ON CONFLICT (id) DO NOTHING;
