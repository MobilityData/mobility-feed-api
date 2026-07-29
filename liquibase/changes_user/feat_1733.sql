-- Issue #1733: Add brevo_synced_at to app_user.
-- Tracks when the user's Brevo contact was last written with its
-- MDB_SUBSCRIPTION_ID (the id of the user's api.announcements
-- notification_subscription) by the migrate_firebase_users task.
-- NULL means the Brevo contact has not been synced yet (MDB_SUBSCRIPTION_ID is
-- assumed unset), so the next task run will (re)write it. api.announcements is
-- the only Brevo-delivered notification type and a Brevo contact maps 1:1 to a
-- user, so this lives on app_user rather than on notification_subscription.
-- Idempotent and reusable to detect/repair contacts with a missing Brevo id.
ALTER TABLE app_user
    ADD COLUMN IF NOT EXISTS brevo_synced_at TIMESTAMPTZ;
