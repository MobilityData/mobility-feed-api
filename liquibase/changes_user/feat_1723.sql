-- Issue #1723: Implement feed.url_updated notification type.
--
-- This establishes a REUSABLE notification event + dispatch pattern for future
-- notification types (location.feed_added #1725, feed.url_availability #1726,
-- feed.coverage #1727, ...).  To stay generic across types:
--   * notification_event keeps only type-agnostic columns; everything
--     type-specific (urls, location, dataset, http status, coverage dates,
--     dispatch stats, ...) goes into the JSONB `payload` column.
--   * notification_event_feed relates an event to one-or-more feeds, so a
--     single event can reference multiple feeds (e.g. redirect source+target).
--
-- Changes:
--   1. notification_event table       — generic event record (type, subtype, payload)
--   2. notification_event_feed table  — N feeds per event (subject/target roles)
--   3. notification_subscription cols — cadence (when) + digest (how many emails)
--   4. notification_log cols          — event FK, retry_count, unique delivery guard
--   5. Seed notification_type rows    — feed.url_updated, admin.event_summary

-- ---------------------------------------------------------------------------
-- 1. notification_event — generic, type-agnostic event record
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_event (
    id                    TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    notification_type_id  TEXT        NOT NULL REFERENCES notification_type(id),
    -- Discriminator within a notification type.
    -- feed.url_updated:     'feed_redirected' | 'url_replaced'
    -- feed.url_availability:'became_unavailable' | 'became_available'
    -- feed.coverage:        'expiring_soon' | 'expired' | 'producer_follow_up_required'
    -- location.feed_added:  'feed_added'
    -- admin.event_summary:  'dispatch_summary'
    event_subtype         TEXT        NOT NULL,
    -- Which process emitted this event.
    -- e.g. 'populate_db_gtfs' | 'populate_db_gbfs' | 'tdg_import' | 'jbda_import'
    --      | 'tdg_redirects'   | 'operations_api'   | 'dispatcher'
    source                TEXT,
    -- All type-specific data lives here, keyed by convention per notification
    -- type (see docs/notifications.md).  Examples:
    --   feed.url_updated:      {old_url, new_url}
    --   location.feed_added:   {location_id, location_name, data_type, country, region}
    --   feed.url_availability: {feed_url, http_status, error_reason, outage_duration}
    --   feed.coverage:         {latest_dataset_id, coverage_end_date, days_remaining}
    --   admin.event_summary:   {emails_sent, emails_failed, ..., cadence}
    payload               JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dispatcher queries events per type ordered by recency.
CREATE INDEX IF NOT EXISTS idx_notification_event_type_created
    ON notification_event (notification_type_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- 2. notification_event_feed — relate one event to one-or-more feeds
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_event_feed (
    id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    notification_event_id TEXT NOT NULL
        REFERENCES notification_event(id) ON DELETE CASCADE,
    -- The feed this row references (stable_id).
    feed_stable_id        TEXT NOT NULL,
    -- Role of this feed within the event.
    --   'subject' : the feed the event is primarily about (default)
    --   'target'  : the destination feed (e.g. redirect target)
    role                  TEXT NOT NULL DEFAULT 'subject',
    -- A feed can appear once per role within an event.
    CONSTRAINT uq_notification_event_feed UNIQUE (notification_event_id, feed_stable_id, role)
);

-- Fetch all feeds for an event when rendering.
CREATE INDEX IF NOT EXISTS idx_notification_event_feed_event_id
    ON notification_event_feed (notification_event_id);

-- Match events to subscribers filtering by feed (filter_params.feed_ids).
CREATE INDEX IF NOT EXISTS idx_notification_event_feed_feed_stable_id
    ON notification_event_feed (feed_stable_id);

-- ---------------------------------------------------------------------------
-- 3. notification_subscription — add cadence, active_since and digest columns
-- ---------------------------------------------------------------------------
ALTER TABLE notification_subscription
    ADD COLUMN IF NOT EXISTS cadence TEXT    NOT NULL DEFAULT 'weekly',
    ADD COLUMN IF NOT EXISTS digest  BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS active_since TIMESTAMPTZ DEFAULT now();

-- Index to let the dispatcher efficiently find subscriptions to process per run.
CREATE INDEX IF NOT EXISTS idx_notification_subscription_cadence_active
    ON notification_subscription (cadence, active) WHERE active;

-- ---------------------------------------------------------------------------
-- 4. notification_log — add event FK, unique delivery guard, retry tracking
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
-- 5. Seed notification types
-- ---------------------------------------------------------------------------
INSERT INTO notification_type (id, description) VALUES
    ('feed.url_updated',
     'Fired when a feed URL changes in-place (url_replaced) or a feed is deprecated '
     'and redirected to a new feed (feed_redirected).'),
    ('admin.event_summary',
     'Daily digest sent to admin subscribers summarising how many notification events '
     'were dispatched, failed, or skipped during the previous dispatcher run.')
ON CONFLICT (id) DO NOTHING;
