-- Make notification_log.subscription_id cascade-delete with its parent
-- notification_subscription.
--
-- The original FK (created in feat_1683.sql) had no ON DELETE rule and
-- subscription_id is NOT NULL, so deleting a subscription that had any
-- notification_log rows failed with a not-null / FK violation. Cascading the
-- delete lets a subscription (and any app_user that owns it) be removed cleanly.
ALTER TABLE notification_log
    DROP CONSTRAINT IF EXISTS notification_log_subscription_id_fkey;

ALTER TABLE notification_log
    ADD CONSTRAINT notification_log_subscription_id_fkey
        FOREIGN KEY (subscription_id)
        REFERENCES notification_subscription(id)
        ON DELETE CASCADE;
