-- Core user record
CREATE TABLE app_user (
    id                        TEXT PRIMARY KEY,          -- immutable Firebase/Google UID
    email                     TEXT NOT NULL UNIQUE,
    full_name                 TEXT,
    legacy_org_name           TEXT,                      -- preserved from Firestore; used by post-MVP org migration
    registration_completed_at TIMESTAMPTZ,               -- populated after registration is completed
    email_verified            BOOLEAN,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Predefined notification types
CREATE TABLE notification_type (
    id          TEXT PRIMARY KEY,            -- e.g. 'api.announcements', 'feed.published'
    description TEXT
);

-- User notification subscription
CREATE TABLE notification_subscription (
    id                   TEXT PRIMARY KEY,   -- UUID v4
    user_id              TEXT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    notification_type_id TEXT NOT NULL REFERENCES notification_type(id),
    filter_params        JSONB,              -- used to add filter logic within the notification, example feed_id(s). This can support custom notifications in the future.
    last_notified_at     TIMESTAMPTZ,
    active               BOOLEAN NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Delivery log
CREATE TABLE notification_log (
    id               TEXT PRIMARY KEY,       -- UUID v4
    subscription_id  TEXT NOT NULL REFERENCES notification_subscription(id),
    sent_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    channel          TEXT NOT NULL DEFAULT 'email',
    status           TEXT NOT NULL,          -- 'sent' | 'failed'
    error_message    TEXT
);

-- Indexes

-- notification_subscription
-- Lookups by user_id (list a user's subscriptions) and by notification_type_id (fan-out when a notification fires).
CREATE INDEX ON notification_subscription (user_id);
CREATE INDEX ON notification_subscription (notification_type_id);
-- Composite index to quickly find active subscriptions for a given notification type when dispatching notifications.
CREATE INDEX ON notification_subscription (notification_type_id, active) WHERE active;
-- GIN index on filter_params to support JSONB containment queries (e.g. filter by feed_id inside filter_params).
CREATE INDEX ON notification_subscription USING GIN (filter_params);

-- notification_log
-- Foreign key column: speeds up "delivery history for a subscription" lookups and cascade/joins.
CREATE INDEX ON notification_log (subscription_id);
-- Time-based queries (recent deliveries, retention cleanup); DESC matches typical "latest first" access patterns.
CREATE INDEX ON notification_log (sent_at DESC);
-- Partial index to efficiently find failed deliveries for retry/monitoring without scanning successful rows.
CREATE INDEX ON notification_log (sent_at DESC) WHERE status = 'failed';
