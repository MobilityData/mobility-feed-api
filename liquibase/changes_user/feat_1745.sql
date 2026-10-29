-- Issue #1745: Drop app_user.is_registered_to_receive_api_announcements.
-- The opt-in is now the user's active api.announcements notification_subscription
-- (backfilled from this column by feat_1729), kept in sync with Brevo by the API.
ALTER TABLE app_user DROP COLUMN IF EXISTS is_registered_to_receive_api_announcements;
