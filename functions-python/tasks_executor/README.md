# Tasks Executor

This directory contains Google Cloud Functions used as a single point of access to multiple _tasks_.

## Usage

The function receive the following payload:

```
{
   "task": "string", # [required] Name of the task to execute
   "payload": { } [optional] Payload to pass to the task
}
```

Examples:

```json
{
  "task": "rebuild_missing_validation_reports",
  "payload": {
    "dry_run": true,
    "bypass_db_update": true,
    "filter_after_in_days": null,
    "force_update": false,
    "validator_endpoint": "https://stg-gtfs-validator-web-mbzoxaljzq-ue.a.run.app",
    "limit": 1,    
    "filter_statuses": ["active", "inactive", "future"]
  }
}
```

```json
{
  "task": "get_validation_run_status",
  "payload": {
    "task_name": "gtfs_validation",
    "run_id": "7.1.1-SNAPSHOT"
  }
}
```

```json
{
  "task": "rebuild_missing_bounding_boxes",
  "payload": {
    "dry_run": true,
    "after_date": "2025-06-01"
  }
}
```

```json
{
  "task": "refresh_materialized_view",
  "payload": {
    "dry_run": true
  }
}
```

To get the list of supported tasks use:

```json
{
  "name": "list_tasks",
  "payload": {}
}
```

To update the geolocation files precision:

```json
{
  "task": "update_geojson_files_precision",
  "payload": {
    "dry_run": true,
    "data_type": "gtfs",
    "precision": 5,
    "limit": 10
  }
}
```

To populate licenses:

```json
{
  "task": "populate_licenses",
  "payload": {
    "dry_run": true
  }
}
```

To backfill MD5 hashes for existing GTFS datasets (reads the MD5 from the GCS object metadata):

```json
{
  "task": "backfill_dataset_hash_md5",
  "payload": {
    "dry_run": true,
    "only_latest": true,
    "only_missing_hashes": true,
    "limit": 10
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Log changes without writing to the database |
| `only_latest` | bool | `true` | Process only datasets that are the current latest for their feed |
| `only_missing_hashes` | bool | `true` | Skip datasets that already have `hash_md5` set |
| `limit` | int \| null | `10` | Maximum number of datasets to process; omit or pass `null` for no limit |

To check the availability of non-deprecated published GTFS feeds via HTTP HEAD requests (with GET fallback):

```json
{
  "task": "check_gtfs_feed_availability",
  "payload": {
    "dry_run": true,
    "skip_db_update": false,
    "limit": null,
    "concurrency": 15,
    "timeout_seconds": 10,
    "batch_size": 50,
    "stable_feed_ids": null,
    "verbose": false,
    "fallback_to_get": true
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Count matching feeds only — no HTTP calls or DB writes |
| `skip_db_update` | bool | `false` | Run HTTP checks but skip writing results to the DB. Each check is logged individually for monitoring and debugging |
| `limit` | int \| null | `null` | Maximum number of feeds to process; omit or pass `null` for no limit |
| `concurrency` | int | `10` | Number of parallel HTTP workers |
| `timeout_seconds` | int | `20` | Per-request HTTP timeout in seconds |
| `batch_size` | int | `50` | Number of completed results committed to DB at a time |
| `stable_feed_ids` | list[str] \| null | `null` | If provided, only check feeds with these stable IDs (e.g. mdb-123) |
| `verbose` | bool | `false` | If `true`, the response includes a `failures` list with `stable_id`, `error_type`, `reason`, `content_type`, and `is_zip` for each failed check |
| `fallback_to_get` | bool | `true` | If `true`, feeds that fail HEAD are retried with a lightweight GET request (reads only 4 bytes to verify ZIP magic bytes). The stored `request_type` reflects the method that produced the final result (`http_head` or `http_get`) |

The response includes an `elapsed_seconds` field indicating how long the task took to complete. When `verbose=true`, a `failures` list is included:

```json
{
  "message": "Checked 3 feed(s): 2 succeeded, 1 failed.",
  "total_feeds": 3,
  "succeeded": 2,
  "failed": 1,
  "skip_db_update": false,
  "elapsed_seconds": 4.21,
  "failures": [
    {
      "stable_id": "mdb-123",
      "error_type": "ConnectionError",
      "reason": "Max retries exceeded",
      "content_type": null,
      "is_zip": null
    }
  ]
}
```

## Response Content Type

When the request includes the header `Accept: text/csv`, the server returns the response as a CSV file generated from the handler’s output.
If the header is not provided, the default response content type is `application/json`.

## Tasks

### `migrate_firebase_users`

Migrates Firebase Auth users into the `users.app_user` PostgreSQL table. This task is **insert-only** — existing rows are never modified. Brevo is the source of truth for `is_registered_to_receive_api_announcements`.

```json
{
  "task": "migrate_firebase_users",
  "payload": {
    "dry_run": true,
    "limit": null,
    "user_ids": null,
    "only_not_migrated": true
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Read and count without any DB writes. Brevo is still queried so counts are accurate |
| `limit` | int \| null | `null` | Maximum number of users to process per run; `null` means no limit |
| `user_ids` | list[str] \| null | `null` | If provided, only migrate these specific Firebase UIDs |
| `only_not_migrated` | bool | `true` | Skip users that already have a row in `app_user` with `migrated_at` set |

**Brevo subscription logic**: For each new user, `BREVO_API_ANNOUNCEMENTS_LIST_ID` is checked. If the contact is `SUBSCRIBED`, `is_registered_to_receive_api_announcements` is set to `true`; `UNSUBSCRIBED` sets it to `false`; `NOT_FOUND` leaves it at the DB default (`false`).

**Datastore entity lookup**: For each new user, the `web_api_users` kind is queried by the `uid` property to retrieve `fullName`, `organization`, and `registrationCompletionTime`.

**Required environment variables**:
- `BREVO_API_KEY` (secret) — Brevo API key
- `BREVO_API_ANNOUNCEMENTS_LIST_ID` — numeric Brevo list ID for API announcements
- `USERS_DATABASE_URL` (secret) — PostgreSQL connection string for the users DB

**Response fields**:

| Field | Description |
|---|---|
| `total` | Total Firebase users iterated |
| `inserted` | Users inserted into `app_user` |
| `skipped` | Users skipped because they already exist with `migrated_at` set |
| `no_email_skipped` | Users skipped because they have no email address |
| `brevo_subscribed` | Users found as subscribed in Brevo |
| `brevo_unsubscribed` | Users found as unsubscribed in Brevo |
| `brevo_not_found` | Users not found in Brevo |
| `brevo_failed` | Users where the Brevo check failed (non-fatal; user is still inserted) |
| `dry_run` | Whether the task ran in dry-run mode |

### `notifications_dispatch_plan` (+ `notifications_dispatch_subscription`, `notifications_dispatch_monitor`)

Notification dispatch is a **Cloud Tasks fan-out** of three tasks:

- **`notifications_dispatch_plan`** (producer) — resolves cadences, finds active
  `notification_subscription` rows, registers a run in `TaskExecutionTracker`,
  and enqueues one worker task per subscription plus a single monitor task.
  Triggered by the daily Cloud Scheduler job (disabled in dev/qa) or manually.
- **`notifications_dispatch_subscription`** (worker, one per subscription) —
  **claim-then-send** (lock-free `INSERT ... ON CONFLICT DO NOTHING` into
  `notification_log`, so concurrent workers never duplicate an email), sends via
  Brevo, records delivery, and reports completion to the tracker.
- **`notifications_dispatch_monitor`** (barrier, one per run) — returns 503
  (Cloud Tasks native retry) while workers are in flight, then emits exactly one
  `admin.event_summary` with aggregated stats.

Cloud Task names are **dynamic** (`run_id` carries a per-invocation timestamp),
so re-running the planner never collides with Cloud Tasks' name tombstones;
idempotency comes from the DB claim. See `docs/notifications.md` for the full
architecture, retry strategy, and operational runbook.

```json
{
  "task": "notifications_dispatch_plan",
  "payload": {
    "cadence": "scheduled",
    "weekly_weekday": 0,
    "dry_run": false,
    "status_filter": "new",
    "user_ids": [],
    "force": false,
    "since_dt": null,
    "until_dt": null,
    "max_retries": 5,
    "stale_claim_seconds": 1800,
    "monitor_delay_seconds": 60,
    "deadline_seconds": 21600
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `cadence` | str | `scheduled` | `daily` \| `weekly` \| `all` \| `scheduled`. `scheduled` (used by the daily Cloud Scheduler job) processes daily-cadence subscriptions every day and weekly-cadence subscriptions only on `weekly_weekday` |
| `weekly_weekday` | int | `0` | Day of week the weekly digest is sent under `cadence=scheduled` (0=Mon .. 6=Sun). Only used with `cadence=scheduled` |
| `dry_run` | bool | `false` | Resolve and log subscriptions without enqueuing workers |
| `status_filter` | str | `new` | `new` \| `failed` \| `all`. Selects which `notification_log` states workers (re)process |
| `user_ids` | list[str] | `[]` | If provided, only dispatch to these user IDs (manual trigger) |
| `force` | bool | `false` | When `user_ids` is set, bypass the cadence window/check |
| `since_dt` | str \| null | `null` | ISO8601 override for the event look-back window start |
| `until_dt` | str \| null | `null` | ISO8601 override for the event look-back window end |
| `max_retries` | int | `5` | Attempts before a log row is marked `permanently_failed` |
| `stale_claim_seconds` | int | `1800` | A `pending` claim older than this (crashed worker) is reclaimable |
| `monitor_delay_seconds` | int | `60` | Delay before the monitor's first poll |
| `deadline_seconds` | int | `21600` | Wall-clock cap before the monitor emits an incomplete summary and stops polling |

**Required environment variables**:
- `USERS_DATABASE_URL` (secret) — PostgreSQL connection string for the users DB
- `BREVO_API_KEY` (secret) — Brevo API key for sending email
- `PROJECT_ID`, `GCP_REGION`, `ENVIRONMENT`, `SERVICE_ACCOUNT_EMAIL` — used to enqueue worker/monitor tasks
- `NOTIFICATION_DISPATCH_QUEUE`, `NOTIFICATION_DISPATCH_MONITOR_QUEUE` — Cloud Tasks queue names

**Planner response** (`by_cadence` carries per-cadence `run_id` / `subscriptions` / `enqueued`):

| Field | Description |
|---|---|
| `cadences` | List of cadences processed in this run |
| `by_cadence.<cadence>.run_id` | The `TaskExecutionTracker` run id (`<cadence>-<YYYYMMDDThhmmss>`) |
| `by_cadence.<cadence>.subscriptions` | Active subscriptions resolved for the cadence |
| `by_cadence.<cadence>.enqueued` | Worker tasks enqueued |

Each **worker** returns its per-subscription stats (`emails_sent`,
`events_claimed`, `emails_failed`, ...); the **monitor** returns the aggregated
run summary that is also emitted as `admin.event_summary`.
| `by_cadence` | Per-cadence breakdown of the above counters |