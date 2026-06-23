# Notification System — Architecture & Operations Guide

> **Issue**: [#1723](https://github.com/MobilityData/mobility-feed-api/issues/1723)

---

## Table of Contents

1. [Overview](#overview)
2. [Notification Types](#notification-types)
3. [Database Schema](#database-schema)
4. [Event Creation — Integration Points](#event-creation--integration-points)
5. [Dispatcher Tasks (Cloud Tasks fan-out)](#dispatcher-tasks-cloud-tasks-fan-out)
   - [Run tracking & dynamic task names](#run-tracking--dynamic-task-names)
   - [Planner Payload Parameters](#planner-payload-parameters)
   - [active_since — Eligibility Gate](#active_since--eligibility-gate)
   - [Claim-then-send (no duplicate emails)](#claim-then-send-no-duplicate-emails)
   - [Example Invocations](#example-invocations)
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
           ▼  Cloud Scheduler (daily)
   notifications_dispatch_plan       (producer / planner)
     • resolves cadences for today
     • finds active notification_subscriptions
     • registers a run in TaskExecutionTracker (feeds DB)
     • enqueues 1 Cloud Task per subscription + 1 monitor task
           │
           ├──▶ notifications_dispatch_subscription  (worker, 1 per subscription)
           │      • claim-then-send each pending event (lock-free, no duplicates)
           │      • sends emails via Brevo
           │      • records delivery in notification_log
           │      • reports completion to TaskExecutionTracker
           │
           └──▶ notifications_dispatch_monitor        (barrier, 1 per run)
                  • polls until every worker has reported (Cloud Tasks native retry)
                  • emits exactly ONE admin.event_summary with aggregated stats
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

### `feed.url_updated` — `event_subtype` values

| `event_subtype` | Trigger |
|---------------|---------|
| `feed_redirected` | A new `Redirectingid` row is created; source feed is deprecated. |
| `url_replaced` | `Feed.producer_url` is updated in-place by automation or an operator. |

### `admin.event_summary` — `event_subtype` values

| `event_subtype` | Trigger |
|---------------|---------|
| `dispatch_summary` | Created after every non-dry-run dispatcher invocation. |

---

## Database Schema

All notification tables live in the **users DB**.

The schema is deliberately **generic** so new notification types reuse it without DDL changes:
`notification_event` holds only type-agnostic columns, the feeds an event is about live in a
separate `notification_event_feed` link table (so one event can reference multiple feeds), and
**all type-specific data goes in the JSONB `payload`**.

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
| `event_subtype` | TEXT | Discriminator within the type (`feed_redirected` \| `url_replaced` \| `dispatch_summary` \| ...) |
| `source` | TEXT | Which process emitted this (see source constants) |
| `payload` | JSONB | **All type-specific data** (see payload conventions below) |
| `created_at` | TIMESTAMPTZ | Auto-set by DB |

### `notification_event_feed`

Relates one event to one-or-more feeds. Lets a single event reference multiple feeds (e.g. a
redirect has both a source and a target feed) and drives `feed_ids` subscription filtering.

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | UUID v4 |
| `notification_event_id` | TEXT FK | `→ notification_event.id ON DELETE CASCADE` |
| `feed_stable_id` | TEXT | The referenced feed |
| `role` | TEXT | `'subject'` (default) \| `'target'` |

**Unique constraint** on `(notification_event_id, feed_stable_id, role)`.

### `payload` conventions per type

Non-feed entities (location, dataset) also live in `payload` — they are type-specific and not used
for the cross-cutting `feed_ids` filter.

| Type / subtype | Feeds (`role`) | `payload` keys |
|----------------|----------------|----------------|
| `feed.url_updated` / `feed_redirected` | old (`subject`), new (`target`) | `old_url`, `new_url` |
| `feed.url_updated` / `url_replaced` | feed (`subject`) | `old_url`, `new_url` |
| `location.feed_added` (#1725) | feed (`subject`) | `location_id`, `location_name`, `data_type`, `country`, `region`, `provider` |
| `feed.url_availability` (#1726) | feed (`subject`) | `feed_url`, `http_status`, `error_reason`, `first_failure_at`, `latest_checked_at`, `recovery_at`, `outage_duration` |
| `feed.coverage` (#1727) | feed (`subject`) | `latest_dataset_id`, `coverage_end_date`, `days_remaining`, `days_expired`, `feed_url`, `guidance` |
| `admin.event_summary` / `dispatch_summary` | — | `emails_sent`, `emails_failed`, ..., `cadence` |

### `notification_subscription`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `cadence` | TEXT | `'weekly'` | `'immediate'` \| `'daily'` \| `'weekly'` |
| `digest` | BOOLEAN | `true` | `true` = one batched email; `false` = one email per event |
| `filter_params` | JSONB | `null` | `null` = all feeds; `{"feed_ids": ["mdb-1"]}` = events referencing any of those feeds |

### `notification_log`

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `notification_event_id` | TEXT FK | `null` | `→ notification_event.id ON DELETE CASCADE` |
| `retry_count` | INTEGER | `0` | Incremented on each failed attempt |
| `status` | TEXT | — | `'sent'` \| `'failed'` \| `'permanently_failed'` |

**Unique constraint** on `(notification_event_id, subscription_id, channel)` prevents duplicate delivery regardless of how many times the dispatcher runs.

---

## Event Creation — Integration Points

`notification_event` rows (and their `notification_event_feed` rows) are created by calling helpers
from `shared/notifications/notification_event_service.py`.

### `emit_feed_redirected(source_stable_id, target_stable_id, old_url, new_url, source, extra_data=None)`
### `emit_url_replaced(feed_stable_id, old_url, new_url, source, extra_data=None)`

These wrap the generic `_emit(notification_type_id, event_subtype, source, feeds, payload)`.
`old_url`/`new_url` are stored in `payload`; the feed(s) become `notification_event_feed` rows.
Any `extra_data` is merged into `payload`.

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

## Dispatcher Tasks (Cloud Tasks fan-out)

Dispatch is a **Cloud Tasks fan-out**, not a single monolithic task. Cloud
Scheduler triggers a **planner** that enqueues one **worker** per subscription
plus a single **monitor** that emits the run summary once the run drains. This
scales horizontally (workers run in parallel) and makes duplicate emails
structurally impossible under concurrency (lock-free claim-then-send).

**Files**: `functions-python/tasks_executor/src/tasks/notifications/`
— `dispatch_plan.py` (planner), `dispatch_subscription.py` (worker),
`dispatch_monitor.py` (monitor). Shared query/send/log/claim helpers live in
`dispatch_notifications.py`.

| Task name | Role | Triggered by |
|-----------|------|--------------|
| `notifications_dispatch_plan` | Producer: resolve cadences, find subscriptions, register the run, enqueue workers + monitor | Cloud Scheduler |
| `notifications_dispatch_subscription` | Worker: claim-then-send one subscription's pending events | `notifications_dispatch_plan` (one task per subscription) |
| `notifications_dispatch_monitor` | Barrier: poll until the run drains, then emit one `admin.event_summary` | `notifications_dispatch_plan` (one task per run) |

### Run tracking & dynamic task names

Each planner invocation picks a fresh `run_id` (`<cadence>-<YYYYMMDDThhmmss>`) and
registers it in **`TaskExecutionTracker`** (feeds DB) with one tracked entry per
subscription. Workers mark their entry `completed`/`failed`; the monitor settles
when every entry has reported (`triggered == 0`). Because `run_id` carries a
per-invocation timestamp, every Cloud Task name is **dynamic**
(`notifications-dispatch-<run_id>-<sub_id>`,
`notifications-dispatch-monitor-<run_id>`) — re-running the planner never
collides with Cloud Tasks' ~1h name tombstones. Idempotency comes from the DB
claim, **not** task-name dedup.

### Planner payload parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cadence` | str | `'scheduled'` | `'scheduled'` (daily every day + weekly on `weekly_weekday`) \| `'daily'` \| `'weekly'` \| `'all'` |
| `weekly_weekday` | int | `0` | Day-of-week (Mon=0..Sun=6) that weekly-cadence runs under `'scheduled'` |
| `dry_run` | bool | `false` | Resolve and log subscriptions without enqueuing workers |
| `status_filter` | str | `'new'` | `'new'` = unsent events; `'failed'` = retry mode; `'all'` = both (passed through to workers) |
| `user_ids` | list[str] | `[]` | Restrict to specific users (manual trigger) |
| `force` | bool | `false` | When `true` + `user_ids`: bypass cadence and window |
| `since_dt` | str | `null` | ISO 8601 lower-bound override. An *additional* floor on top of `active_since`: effective lower bound is `max(subscription.active_since, since_dt)`. |
| `until_dt` | str | `null` | ISO 8601 window end override. Defaults to `now()`. |
| `max_retries` | int | `5` | Stop retrying at this retry_count |
| `stale_claim_seconds` | int | `1800` | A `pending` claim older than this (crashed worker) is reclaimable |
| `monitor_delay_seconds` | int | `60` | Delay before the monitor's first poll |
| `deadline_seconds` | int | `21600` (6h) | Wall-clock cap: monitor stops polling and emits an "incomplete" summary past this |

### active_since — Eligibility Gate

Every `notification_subscription` row has an `active_since` timestamp. Event
discovery uses it as the **exclusive lower bound** — only events with
`created_at >= active_since` are candidates.

| Subscription state | `active_since` behaviour |
|--------------------|-------------------------|
| **Newly created** (`active=True` from birth) | Set to the creation timestamp. The subscription can never receive events that pre-date its own existence. |
| **Re-enabled** (`active` flipped `False → True`) | **Must be updated to `now()`** by the re-activation code. Events emitted while the subscription was inactive are permanently excluded. |
| **Active, no state change** | Never modified. Only `last_notified_at` is updated after a dispatch run. |

> **Key rule**: `since_dt` in the payload can narrow the window further, but it can never override the `active_since` floor.

### Claim-then-send (no duplicate emails)

The worker (`process_subscription`) guarantees at-most-one email per
`(event, subscription, channel)` even under concurrent workers, **lock-free**:

1. **Claim**: `INSERT INTO notification_log (... status='pending') ON CONFLICT DO NOTHING`.
   - `0` rows → another worker owns this event → skip.
   - `1` row → we own it → proceed.
2. **Send** via Brevo, then `UPDATE` the row to `sent`/`failed`.

A `pending` row younger than `stale_claim_seconds` is treated as in-flight and
skipped; an older one (crashed worker) is reclaimed. This bounds the rare
crash-after-send case to "at most one duplicate", never a lost email. The
unique constraint `uq_notification_log_event_sub_channel` enforces the claim.

### Example invocations

```json
// Daily scheduled run (production) — drives both cadences
{"cadence": "scheduled", "weekly_weekday": 0, "dry_run": false}

// Retry failed notifications
{"cadence": "all", "status_filter": "failed", "dry_run": false}

// Manual trigger for specific users
{"cadence": "all", "user_ids": ["uid-123", "uid-456"], "force": true, "dry_run": false}

// Dry run — resolve subscriptions, enqueue nothing
{"cadence": "weekly", "dry_run": true}
```

### Responses

The **planner** returns the per-cadence fan-out summary:

```json
{
  "cadences": ["daily"],
  "by_cadence": {
    "daily": {"run_id": "daily-20260622T080000", "subscriptions": 42, "enqueued": 42, "dry_run": false}
  }
}
```

Each **worker** returns its per-subscription stats (`emails_sent`,
`events_claimed`, `emails_failed`, ...). The **monitor** returns the aggregated
run summary (see [Admin Event Summary](#admin-event-summary)).

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

Durability plus three independent retry layers:

### Layer 0 — Commit after every send (crash durability)
The dispatcher commits the `notification_log` row **immediately after each email is sent** (after every single send, and after each digest). This guarantees that a crash, timeout (`attempt_deadline`), or DB error later in the run can never roll back the log of an email that was already delivered — bounding any duplicate to at most the one send in flight.

### Layer 1 — In-run retries (transient failures)
Each Brevo send attempt is retried **up to 3 times** within the same worker run with short back-off (1 s, 2 s, 4 s). Handles transient Brevo API errors, rate limits, and timeouts.

### Layer 2 — Cross-run retries (next scheduled run + Cloud Tasks)
Two mechanisms cooperate:
- **DB ledger**: a `failed` (non-permanent) `notification_log` row is re-claimed and retried by the next scheduled planner run (`status_filter` includes `failed` events whose `retry_count < max_retries`).
- **Cloud Tasks native retry**: if a *worker* task fails on an infrastructure error (HTTP 500), Cloud Tasks retries it per the queue's `retry_config`; the claim-then-send logic makes the redelivery a no-op for already-sent events.

### Layer 3 — Permanent failure (`retry_count >= max_retries`)
Once a log row reaches `retry_count >= max_retries` (default 5), it is marked `'permanently_failed'` and excluded from all future runs. Monitor for `permanently_failed` rows in dashboards or alerts.

### The ledger is the source of truth, not the queue
Cloud Tasks gives at-least-once *eventual* delivery, not a by-deadline guarantee, so completeness is anchored in the DB: a run is "done" when every pending event for an active subscription has a terminal `notification_log` row (`sent`/`permanently_failed`). The re-entrant planner re-publishes any stragglers on the next pass; the unique constraint + claim-then-send prevent duplicates; the monitor's `admin.event_summary` reports the outcome.


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

The following params are passed to Brevo templates (accessible in templates as `{{ params.events[0].feed_stable_id }}`, etc.). Both single and digest sends use the same `event_count` / `events[]` shape:

**Single event** (`events` has one entry):
```json
{
  "event_count": 1,
  "subscription_id": "sub-uuid",
  "events": [
    {
      "feed_stable_id": "mdb-1234",
      "target_feed_stable_id": "tdg-5678",
      "event_subtype": "feed_redirected",
      "old_url": "https://...",
      "new_url": "https://...",
      "source": "tdg_redirects",
      "created_at": "2026-06-09T12:00:00+00:00",
      "payload": { "old_url": "https://...", "new_url": "https://..." }
    }
  ]
}
```

**Digest**:
```json
{
  "event_count": 3,
  "subscription_id": "sub-uuid",
  "events": [{ "feed_stable_id": "...", "event_subtype": "...", ... }, ...]
}
```

---

## Admin Event Summary

The **monitor task** (`notifications_dispatch_monitor`) emits **exactly one**
`notification_event` of type `admin.event_summary` / `dispatch_summary` per
dispatch run, once every worker has reported (or the run deadline passes). It
aggregates delivery stats from `notification_log` over the run window into
`payload`:

```json
{
  "subscriptions_processed": 42,
  "workers_failed": 0,
  "events_found": 18,
  "emails_sent": 17,
  "emails_failed": 1,
  "permanently_failed": 0,
  "incomplete_workers": 0,
  "cadence": "daily"
}
```

`incomplete_workers > 0` means the run hit its `deadline_seconds` cap before all
workers reported — the summary is still emitted (marked incomplete) so the run
terminates. Because the summary is created by the single barrier task keyed off
the run's `TaskExecutionTracker` state (and the run is marked complete
afterward), the **multiple-summary bug class is structurally impossible** — a
monitor redelivery sees the run already `completed` and is a no-op.

Admin users subscribe with `notification_type_id='admin.event_summary'` and
`cadence='daily'` to receive these as a daily digest.


---

## Manual Trigger

To force-send notifications for specific users (e.g. for testing or re-sending after a known issue):

```bash
# Via tasks_executor Cloud Function
curl -X POST https://<region>-<project>.cloudfunctions.net/tasks_executor-<env> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
    "task": "notifications_dispatch_plan",
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
| `NOTIFICATION_DISPATCH_QUEUE` | Yes (in tasks_executor) | Cloud Tasks queue name for per-subscription dispatch workers |
| `NOTIFICATION_DISPATCH_MONITOR_QUEUE` | Yes (in tasks_executor) | Cloud Tasks queue name for the dispatch barrier/monitor task |
| `PROJECT_ID` / `GCP_REGION` / `ENVIRONMENT` / `SERVICE_ACCOUNT_EMAIL` | Yes (in tasks_executor) | Used to build the worker/monitor task URLs and OIDC token when enqueuing |

---

## Deployment Notes

### Cloud Tasks queues

Two queues back the fan-out (defined in `infra/functions-python/main.tf`, names
suffixed with `<env>-<deployment_timestamp>` so they can be recreated without
collisions):

| Queue | Purpose | Key `retry_config` |
|-------|---------|--------------------|
| `notifications-dispatch-queue-<env>-<ts>` | Per-subscription workers. `max_dispatches_per_second` is a guardrail below the Brevo cap (sends are also governed by the in-process token-bucket limiter). | `max_attempts=5`, backoff 30s→300s |
| `notifications-dispatch-monitor-queue-<env>-<ts>` | Single barrier/monitor task per run. Returns 503 while workers are in flight; native retry polls at a fixed interval until drained. | `max_attempts=-1` (unlimited), fixed `60s` backoff — the in-handler `deadline_seconds` guard stops runaway polling |

### Cloud Scheduler jobs

A **single daily** Cloud Scheduler job (`dispatch-notifications-daily-<env>`,
in `infra/functions-python/main.tf`) triggers the **planner**. It is **paused
outside `prod`** (`paused = var.environment == "prod" ? false : true`). The
`scheduled` cadence directive resolves in `notifications_dispatch_plan` to
`['daily']` every day plus `'weekly'` when `now.weekday() == weekly_weekday`.

| Job name | Schedule | Payload |
|----------|----------|---------|
| `dispatch-notifications-daily-<env>` | `0 8 * * *` (daily 8 AM UTC, `var.notification_dispatch_daily_schedule`) | `{"task":"notifications_dispatch_plan","payload":{"cadence":"scheduled","weekly_weekday":0,"dry_run":false}}` |

The weekday is configurable via `var.notification_dispatch_weekly_weekday`. A
dedicated retry job is unnecessary — `failed` (non-permanent) events are
re-claimed by the next daily run.


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

- **`immediate` cadence**: Architecture is fully implemented. To activate, deploy a Cloud Scheduler job calling `notifications_dispatch_plan` with `cadence='immediate'` at the desired frequency (e.g. every 15 minutes). No code changes needed.
- **Additional notification types**: Add a new `notification_type` row, then call `_emit(notification_type_id, event_subtype, source, feeds=[...], payload={...})` in `notification_event_service.py` — no schema changes needed (feeds go in `notification_event_feed`, everything else in `payload`). The dispatcher, delivery, and retry infrastructure is reused automatically. For non-`feed.url_updated` types, add a Brevo subject/template mapping and a `build_params_*` / HTML renderer in `brevo_notification_sender.py`.
- **Operations API endpoint**: `GET /notifications/events` (paginated, filterable by type/date/source) for ops visibility into queued events. Belongs in the operations API, not the public API.
- **Unsubscribe link**: Pass `subscription_id` in Brevo template params; build a one-click unsubscribe endpoint that sets `notification_subscription.active = false`.
