-- Issue #1723: Implement feed.url_updated notification type.
--
-- Changes:
--   1. notification_event table       — records every feed-URL or redirect change
--   2. notification_subscription cols — cadence (when) + digest (how many emails)
--   3. notification_log cols          — event FK, retry_count, unique delivery guard
--   4. Seed notification_type rows    — feed.url_updated, admin.event_summary

-- ---------------------------------------------------------------------------
-- 1. notification_event
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_event (
    id                    TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    notification_type_id  TEXT        NOT NULL REFERENCES notification_type(id),
    -- Discriminator within a notification type.
    -- feed.url_updated:   'feed_redirected' | 'url_replaced'
    -- admin.event_summary: 'dispatch_summary'
    update_type           TEXT        NOT NULL,
    -- The feed that changed (stable_id).  Always set for feed.url_updated events.
    feed_stable_id        TEXT,
    -- For feed_redirected: the target feed's stable_id.
    target_feed_stable_id TEXT,
    old_url               TEXT,
    new_url               TEXT,
    -- Which process emitted this event.
    -- e.g. 'populate_db_gtfs' | 'populate_db_gbfs' | 'tdg_import' | 'jbda_import'
    --      | 'tdg_redirects'   | 'operations_api'   | 'dispatcher'
    source                TEXT,
    -- Arbitrary JSON payload for future extensibility (e.g. redirect comment,
    -- data_type, country, dispatch statistics for admin.event_summary).
    extra_data            JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dispatcher queries unprocessed events per type ordered by recency.
CREATE INDEX IF NOT EXISTS idx_notification_event_type_created
    ON notification_event (notification_type_id, created_at DESC);

-- Filter events for a specific feed's subscribers.
CREATE INDEX IF NOT EXISTS idx_notification_event_feed_stable_id
    ON notification_event (feed_stable_id);

-- ---------------------------------------------------------------------------
-- 2. notification_subscription — add cadence, active_since and digest columns
-- ---------------------------------------------------------------------------
ALTER TABLE notification_subscription
    ADD COLUMN IF NOT EXISTS cadence TEXT    NOT NULL DEFAULT 'weekly',
    ADD COLUMN IF NOT EXISTS digest  BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS active_since TIMESTAMPTZ NOT NULL DEFAULT now();

-- Index to let the dispatcher efficiently find subscriptions to process per run.
CREATE INDEX IF NOT EXISTS idx_notification_subscription_cadence_active
    ON notification_subscription (cadence, active) WHERE active;

-- ---------------------------------------------------------------------------
-- 3. notification_log — add event FK, unique delivery guard, retry tracking
-- ---------------------------------------------------------------------------
ALTER TABLE notification_log
    ADD COLUMN IF NOT EXISTS notification_event_id TEXT
        REFERENCES notification_event(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;

-- One row per (event × subscription × channel).  Prevents duplicate delivery
-- and provides the foundation for retry tracking.
ALTER TABLE notification_log
    DROP CONSTRAINT IF EXISTS uq_notification_log_event_sub_channel;
ALTER TABLE notification_log
    ADD CONSTRAINT uq_notification_log_event_sub_channel
        UNIQUE (notification_event_id, subscription_id, channel);

-- Dispatcher queries pending/failed rows for retry runs.
CREATE INDEX IF NOT EXISTS idx_notification_log_event_id
    ON notification_log (notification_event_id);

CREATE INDEX IF NOT EXISTS idx_notification_log_status
    ON notification_log (status) WHERE status IN ('pending', 'failed');

-- ---------------------------------------------------------------------------
-- 4. Seed notification types
-- ---------------------------------------------------------------------------
INSERT INTO notification_type (id, description) VALUES
    ('feed.url_updated',
     'Fired when a feed URL changes in-place (url_replaced) or a feed is deprecated '
     'and redirected to a new feed (feed_redirected).'),
    ('admin.event_summary',
     'Daily digest sent to admin subscribers summarising how many notification events '
     'were dispatched, failed, or skipped during the previous dispatcher run.')
ON CONFLICT (id) DO NOTHING;
