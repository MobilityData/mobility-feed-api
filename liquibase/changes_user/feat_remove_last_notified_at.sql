-- Remove the unused notification_subscription.last_notified_at column.
-- It was never written by any code path and is being dropped.
ALTER TABLE notification_subscription DROP COLUMN IF EXISTS last_notified_at;
