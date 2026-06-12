# Notification System — Architecture & Operations Guide

> **Issue**: [#1723](https://github.com/MobilityData/mobility-feed-api/issues/1723)

---

## Table of Contents

1. [Overview](#overview)
2. [Notification Types](#notification-types)
3. [Database Schema](#database-schema)
4. [Event Creation — Integration Points](#event-creation--integration-points)
5. [Dispatcher Task](#dispatcher-task)
6. [Cadence vs Digest](#cadence-vs-digest)
7. [Retry Strategy](#retry-strategy)
8. [Email Delivery — Brevo](#email-delivery--brevo)
9. [Admin Event Summary](#admin-event-summary)
10. [Manual Trigger](#manual-trigger)
11. [Environment Variables](#environment-variables)
12. [Deployment Notes](#deployment-notes)
13. [Future Work](#future-work)

---

## Overview

The notification system is **event-driven** and **application-level** (no database triggers).

```
Feed change happens
  │
  ├── feeds DB write          (existing, unchanged)
  └── users DB: notification_event  (new, best-effort)

           │
           ▼  Cloud Scheduler (daily / weekly)
   dispatch_notifications task
     • finds unprocessed / failed notification_events
     • matches active notification_subscriptions
     • sends emails via Brevo
     • records delivery in notification_log
```

**Two databases** are involved:
- **Feeds DB** (`FEEDS_DATABASE_URL`) — where feeds, redirects, and datasets live.
- **Users DB** (`USERS_DATABASE_URL`) — where users, subscriptions, events, and logs live.

Because these are separate PostgreSQL instances, event creation is **best-effort**: if the users DB write fails, the feed change is **not rolled back**. Failures are logged and can be monitored.

---

## Notification Types

| ID | Description |
|----|-------------|
| `feed.url_updated` | Fired when a feed URL changes in-place (`url_replaced`) or a feed is deprecated and redirected to another feed (`feed_redirected`). |
| `admin.event_summary` | Daily digest for admin subscribers summarising dispatcher run statistics. |

### `feed.url_updated` — `update_type` values

| `update_type` | Trigger |
|---------------|---------|
| `feed_redirected` | A new `Redirectingid` row is created; source feed is deprecated. |
| `url_replaced` | `Feed.producer_url` is updated in-place by automation or an operator. |

### `admin.event_summary` — `update_type` values

| `update_type` | Trigger |
|---------------|---------|
| `dispatch_summary` | Created after every non-dry-run dispatcher invocation. |

---

## Database Schema

All notification tables live in the **users DB**.

### `notification_type`

```sql
-- Seeded rows (idempotent, ON CONFLICT DO NOTHING):
INSERT INTO notification_type (id, description) VALUES
    ('feed.url_updated',   '...'),
    ('admin.event_summary', '...');
```

### `notification_event`

One row per real-world change event.  Created by the integration points below.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID v4 |
| `notification_type_id` | TEXT FK | `→ notification_type.id` |
| `update_type` | TEXT | `feed_redirected` \| `url_replaced` \| `dispatch_summary` |
| `feed_stable_id` | TEXT | Stable ID of the changed feed |
| `target_feed_stable_id` | TEXT | For `feed_redirected`: the new feed |
| `old_url` | TEXT | Previous `producer_url` |
| `new_url` | TEXT | New `producer_url` |
| `source` | TEXT | Which process emitted this (see source constants) |
| `extra_data` | JSONB | Free-form payload (redirect comment, dispatch stats, etc.) |
| `created_at` | TIMESTAMPTZ | Auto-set by DB |

### `notification_subscription`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `cadence` | TEXT | `'weekly'` | `'immediate'` \| `'daily'` \| `'weekly'` |
| `digest` | BOOLEAN | `true` | `true` = one batched email; `false` = one email per event |
| `filter_params` | JSONB | `null` | `null` = all feeds; `{"feed_ids": ["mdb-1"]}` = specific feeds |

### `notification_log`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `notification_event_id` | TEXT FK | `null` | `→ notification_event.id ON DELETE CASCADE` |
| `retry_count` | INTEGER | `0` | Incremented on each failed attempt |
| `status` | TEXT | — | `'sent'` \| `'failed'` \| `'permanently_failed'` |

**Unique constraint** on `(notification_event_id, subscription_id, channel)` prevents duplicate delivery regardless of how many times the dispatcher runs.

---

## Event Creation — Integration Points

`notification_event` rows are created by calling helpers from
`shared/notifications/notification_event_service.py`.

### `emit_feed_redirected(source_stable_id, target_stable_id, old_url, new_url, source)`
### `emit_url_replaced(feed_stable_id, old_url, new_url, source)`

Both functions are **fire-and-forget**: if `USERS_DATABASE_URL` is not set, or if the write fails, a warning is logged and the calling code continues normally.

### Wired integration points

| # | Type | File | Function | Source tag |
|---|------|------|----------|------------|
| 1 | `feed_redirected` | `api/src/scripts/populate_db_gtfs.py` | `process_redirects()` | `populate_db_gtfs` |
| 2 | `feed_redirected` | `tasks_executor/.../update_tdg_redirects.py` | `_update_feed_redirect()` | `tdg_redirects` |
| 3 | `feed_redirected` | `operations_api/.../feeds_operations_impl.py` | `_update_feed()` | `operations_api` |
| 4 | `feed_redirected` | `operations_api/.../feeds_operations_impl.py` | `_update_feed()` (GTFS-RT) | `operations_api` |
| 5 | `url_replaced` | `api/src/scripts/populate_db_gtfs.py` | `populate_db()` | `populate_db_gtfs` |
| 6 | `url_replaced` | `api/src/scripts/populate_db_gbfs.py` | main loop | `populate_db_gbfs` |
| 7 | `url_replaced` | `tasks_executor/.../import_tdg_feeds.py` | fingerprint diff block | `tdg_import` |
| 8 | `url_replaced` | `tasks_executor/.../import_jbda_feeds.py` | fingerprint diff block | `jbda_import` |
| 9 | `url_replaced` | `operations_api/.../feeds_operations_impl.py` | `_update_feed()` | `operations_api` |
| 10 | `url_replaced` | `operations_api/.../feeds_operations_impl.py` | `_update_feed()` (GTFS-RT) | `operations_api` |

> **Note — populate_db scripts and GitHub Actions CI**:
> The `populate_db_gtfs.py` and `populate_db_gbfs.py` scripts run as part of the
> `db-update-content.yml` GitHub Actions workflow.  This workflow currently only sets
> `FEEDS_DATABASE_URL`.  To enable notification events from these scripts,
> `USERS_DATABASE_URL` must be added to the workflow's environment.  Until then,
> the emit calls will log a warning and no-op, which does **not** break the populate run.

---

## Dispatcher Task

**Task name**: `dispatch_notifications`
**File**: `functions-python/tasks_executor/src/tasks/notifications/dispatch_notifications.py`

### Payload parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cadence` | str | `'weekly'` | Which subscriptions to process: `'daily'` \| `'weekly'` \| `'all'` |
| `dry_run` | bool | `true` | Discover and log without sending or writing |
| `status_filter` | str | `'new'` | `'new'` = unsent events; `'failed'` = retry mode; `'all'` = both |
| `user_ids` | list[str] | `[]` | Restrict to specific users (manual trigger) |
| `force` | bool | `false` | When `true` + `user_ids`: bypass cadence and window |
| `since_dt` | str | `null` | ISO 8601 window start override |
| `until_dt` | str | `null` | ISO 8601 window end override |
| `max_retries` | int | `5` | Stop retrying at this retry_count |

### Example invocations

```json
// Weekly scheduled run (dry_run=false in production)
{"cadence": "weekly", "dry_run": false}

// Daily scheduled run
{"cadence": "daily", "dry_run": false}

// Retry failed notifications from last 7 days
{"cadence": "all", "status_filter": "failed", "dry_run": false}

// Manual trigger for specific users
{"cadence": "all", "user_ids": ["uid-123", "uid-456"], "force": true, "dry_run": false}

// Admin-only test run (dry run, no emails sent)
{"cadence": "weekly", "dry_run": true}
```

### Response

```json
{
  "subscriptions_processed": 42,
  "events_found": 18,
  "emails_sent": 17,
  "emails_failed": 1,
  "permanently_failed": 0,
  "skipped_max_retries": 0,
  "dry_run": 0
}
```

---

## Cadence vs Digest

These are **two independent axes** on `notification_subscription`:

| `cadence` | `digest` | Result |
|-----------|----------|--------|
| `weekly` | `true` | 1 email/week batching all events — **default** |
| `weekly` | `false` | 1 email per event, sent in the weekly run |
| `daily` | `true` | 1 daily email batching all events from past 24 h |
| `daily` | `false` | 1 email per event, sent in the daily run |
| `immediate` | any | 1 email as soon as dispatcher runs (non-MVP; see below) |

**`cadence`** controls *when* the dispatcher processes subscriptions (which Cloud Scheduler job invokes it).

**`digest`** controls *how many emails*: batch all events in the window into one, or send individually.

---

## Retry Strategy

Three independent layers:

### Layer 1 — In-run retries (transient failures)
Each Brevo send attempt is retried **up to 3 times** within the same dispatcher run with short back-off (1 s, 2 s, 4 s). Handles transient Brevo API errors, rate limits, and timeouts.

### Layer 2 — Cross-run retries (via Cloud Scheduler)
A dedicated **daily retry Cloud Scheduler job** calls `dispatch_notifications` with `{"status_filter": "failed"}`. This ensures that even weekly-cadence subscribers whose email failed will be retried within ~24 hours, not next week.

```
Monday: weekly dispatch → email fails → notification_log status='failed'
Tuesday: daily retry job → status_filter='failed' → retry → status='sent'
```

### Layer 3 — Permanent failure (`retry_count >= max_retries`)
Once a log row reaches `retry_count >= max_retries` (default 5), it is marked `'permanently_failed'` and excluded from all future runs. Monitor for `permanently_failed` rows in dashboards or alerts.

### No GCP pub/sub per notification
A dedicated message queue per notification would add operational complexity without meaningful benefit at current scale. The `notification_log` table **is** the queue: `pending`/`failed` rows are the work items; the unique constraint prevents duplicates; `retry_count` tracks attempts.

---

## Email Delivery — Brevo

The dispatcher sends emails via **Brevo Transactional Email API** (`sib_api_v3_sdk.TransactionalEmailsApi`).

**File**: `api/src/shared/notifications/brevo_notification_sender.py`

### Template IDs

Template IDs are read from environment variables so they can be updated in the Brevo dashboard without code deployments:

| Env var | Template used for |
|---------|-------------------|
| `BREVO_TEMPLATE_FEED_URL_UPDATED` | Single `feed.url_updated` email |
| `BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST` | Digest `feed.url_updated` email |
| `BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY` | `admin.event_summary` email |

When a template ID env var is not set, a **plain HTML fallback** is generated inline. This allows the system to work in development without Brevo template setup.

### Template parameters (`params`)

The following params are passed to Brevo templates (accessible in templates as `{{ params.feed_stable_id }}`, etc.):

**Single event**:
```json
{
  "feed_stable_id": "mdb-1234",
  "target_feed_stable_id": "tdg-5678",
  "update_type": "feed_redirected",
  "old_url": "https://...",
  "new_url": "https://...",
  "source": "tdg_redirects",
  "event_created_at": "2026-06-09T12:00:00+00:00",
  "subscription_id": "sub-uuid"
}
```

**Digest**:
```json
{
  "event_count": 3,
  "subscription_id": "sub-uuid",
  "events": [{ "feed_stable_id": "...", ... }, ...]
}
```

---

## Admin Event Summary

After every **non-dry-run** dispatcher invocation, a `notification_event` of type `admin.event_summary` / `dispatch_summary` is created with dispatch statistics in `extra_data`:

```json
{
  "subscriptions_processed": 42,
  "events_found": 18,
  "emails_sent": 17,
  "emails_failed": 1,
  "permanently_failed": 0,
  "skipped_max_retries": 0,
  "cadence": "weekly"
}
```

Admin users subscribe to this with `notification_type_id='admin.event_summary'` and `cadence='daily'`. They receive a daily digest of dispatcher run statistics.

---

## Manual Trigger

To force-send notifications for specific users (e.g. for testing or re-sending after a known issue):

```bash
# Via tasks_executor Cloud Function
curl -X POST https://<region>-<project>.cloudfunctions.net/tasks_executor-<env> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
    "task": "dispatch_notifications",
    "payload": {
      "cadence": "all",
      "user_ids": ["firebase-uid-of-user"],
      "force": true,
      "dry_run": false
    }
  }'
```

The `force: true` flag bypasses cadence filtering, so the specified users receive all pending notifications regardless of their subscription cadence.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `USERS_DATABASE_URL` | Yes (in tasks_executor) | PostgreSQL connection string for the users DB |
| `BREVO_API_KEY` | Yes (in dispatcher) | Brevo API key for sending transactional emails |
| `BREVO_SENDER_EMAIL` | No | From-address (default: `noreply@mobilitydatabase.org`) |
| `BREVO_SENDER_NAME` | No | From-name (default: `Mobility Database`) |
| `BREVO_TEMPLATE_FEED_URL_UPDATED` | No | Brevo template ID (integer) for single events |
| `BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST` | No | Brevo template ID for digest emails |
| `BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY` | No | Brevo template ID for admin summary |

---

## Deployment Notes

### Cloud Scheduler jobs to create

| Job name | Schedule | Payload |
|----------|----------|---------|
| `dispatch-notifications-weekly` | `0 9 * * MON` (Mon 9 AM UTC) | `{"task":"dispatch_notifications","payload":{"cadence":"weekly","dry_run":false}}` |
| `dispatch-notifications-daily` | `0 8 * * *` (daily 8 AM UTC) | `{"task":"dispatch_notifications","payload":{"cadence":"daily","dry_run":false}}` |
| `dispatch-notifications-retry` | `0 10 * * *` (daily 10 AM UTC) | `{"task":"dispatch_notifications","payload":{"cadence":"all","status_filter":"failed","dry_run":false}}` |

### Adding `USERS_DATABASE_URL` to content update workflow

To enable notification events from the `populate_db` scripts, add to `.github/workflows/db-update-content.yml`:

```yaml
- name: Update .env file
  run: |
    # ... existing lines ...
    echo "USERS_DATABASE_URL=postgresql://${{ secrets.DB_USER_NAME }}:${{ secrets.DB_USER_PASSWORD }}@localhost:5432/MobilityDatabaseUsers${{ inputs.USER_DB_ENVIRONMENT }}" >> config/.env.local
```

Until this is added, `populate_db` scripts will log a warning and skip notification event creation — this does **not** break the populate run.

---

## Future Work

- **`immediate` cadence**: Architecture is fully implemented. To activate, deploy a Cloud Scheduler job calling `dispatch_notifications` with `cadence='immediate'` at the desired frequency (e.g. every 15 minutes). No code changes needed.
- **Additional notification types**: Add a new `notification_type` row + call `_emit()` in `notification_event_service.py`. The dispatcher, delivery, and retry infrastructure is reused automatically.
- **Operations API endpoint**: `GET /notifications/events` (paginated, filterable by type/date/source) for ops visibility into queued events. Belongs in the operations API, not the public API.
- **Unsubscribe link**: Pass `subscription_id` in Brevo template params; build a one-click unsubscribe endpoint that sets `notification_subscription.active = false`.
