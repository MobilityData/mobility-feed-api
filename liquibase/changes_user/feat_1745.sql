-- Issue #1745: Drop app_user.is_registered_to_receive_api_announcements.
-- The opt-in is now the user's active api.announcements notification_subscription,
-- kept in sync with Brevo by the API.

-- Give every user without one an api.announcements subscription carrying their current opt-in.
INSERT INTO notification_subscription (id, user_id, notification_type_id, active)
SELECT gen_random_uuid()::text, u.id, 'api.announcements',
       COALESCE(u.is_registered_to_receive_api_announcements, false)
FROM app_user u
WHERE NOT EXISTS (
    SELECT 1 FROM notification_subscription s
    WHERE s.user_id = u.id
      AND s.notification_type_id = 'api.announcements'
);

ALTER TABLE app_user DROP COLUMN IF EXISTS is_registered_to_receive_api_announcements;
