-- liquibase formatted sql

-- changeset MobilityData:feat_1778_subscription_feed
-- comment: Add notification_subscription_feed join table linking a subscription to the feeds it targets (feed.url_updated, feed.url_availability, feed.coverage). Issue #1778.

-- A notification_subscription can target one-or-more feeds for the feed-scoped
-- notification types. This mirrors the existing notification_event_feed table:
-- feeds are referenced by their public stable_id and there is deliberately NO
-- foreign key to the feeds table, because feeds live in a separate database
-- (see docs/notifications.md).
CREATE TABLE IF NOT EXISTS notification_subscription_feed (
    subscription_id  TEXT NOT NULL
        REFERENCES notification_subscription(id) ON DELETE CASCADE,
    -- Feed referenced by its public stable_id, e.g. 'mdb-1' (matches
    -- notification_event_feed.feed_stable_id). No FK: feeds are in another DB.
    feed_stable_id   TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One row per (subscription, feed); the PK also serves the
    -- "which feeds does this subscription target?" lookup.
    PRIMARY KEY (subscription_id, feed_stable_id)
);

-- Reverse fan-out: "which subscriptions target this feed?" when matching a
-- feed.* event to its subscribers.
CREATE INDEX IF NOT EXISTS idx_notification_subscription_feed_feed_stable_id
    ON notification_subscription_feed (feed_stable_id);
