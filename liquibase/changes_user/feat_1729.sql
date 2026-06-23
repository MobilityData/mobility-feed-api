-- Seed 'api.announcements' notification type (idempotent).
INSERT INTO notification_type (id, description)
VALUES ('api.announcements', 'API announcements')
ON CONFLICT (id) DO NOTHING;

-- Backfill subscriptions for users already opted in (idempotent).
INSERT INTO notification_subscription (id, user_id, notification_type_id)
SELECT gen_random_uuid()::text, u.id, 'api.announcements'
FROM app_user u
WHERE u.is_registered_to_receive_api_announcements
  AND NOT EXISTS (
      SELECT 1 FROM notification_subscription s
      WHERE s.user_id = u.id
        AND s.notification_type_id = 'api.announcements'
  );
