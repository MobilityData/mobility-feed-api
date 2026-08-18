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

Migrates Firebase Auth users into the `users.app_user` PostgreSQL table. `app_user` is **insert-only** with a single exception: the task sets `app_user.brevo_synced_at` on an existing row after it writes that user's `MDB_SUBSCRIPTION_ID` back onto the Brevo contact. It also ensures each user has an `api.announcements` `notification_subscription`. Brevo is the source of truth for `is_registered_to_receive_api_announcements`.

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
| `dry_run` | bool | `true` | Read and count without any DB writes or Brevo write-back. Brevo status is still queried so counts are accurate |
| `limit` | int \| null | `null` | Maximum number of users to process per run; `null` means no limit |
| `user_ids` | list[str] \| null | `null` | If provided, only migrate these specific Firebase UIDs |
| `only_not_migrated` | bool | `true` | Skip users that already have a row in `app_user` with `migrated_at` set |

**Brevo subscription logic**: For each new user, `BREVO_API_ANNOUNCEMENTS_LIST_ID` is checked. If the contact is `SUBSCRIBED`, `is_registered_to_receive_api_announcements` is set to `true`; `UNSUBSCRIBED` sets it to `false`; `NOT_FOUND` leaves it at the DB default (`false`).

**Announcements subscription association**: Every migrated user is associated with the `api.announcements` notification type via a row in `notification_subscription`. New users get the subscription created alongside their `app_user` row; existing users (including already-migrated ones) are **backfilled** a subscription if they don't already have one — without modifying their `app_user` row. The subscription is created enabled (`active=true`) for all users **except** those explicitly `UNSUBSCRIBED` on Brevo, who get a disabled (`active=false`) subscription. Users that are `NOT_FOUND` on Brevo (or whose Brevo check failed) are treated as "not unsubscribed" and therefore enabled. New-subscription counts are reported as `announcements_enabled` / `announcements_disabled`.

**Brevo contact write-back (`MDB_SUBSCRIPTION_ID`)**: For every user whose announcements subscription should be on the Brevo list, the contact is written via `add_contact_to_list` so its `MDB_SUBSCRIPTION_ID` attribute points at the subscription id. `app_user.brevo_synced_at` records that write — it lives on `app_user` (not `notification_subscription`) because `api.announcements` is the only Brevo-delivered notification type and a Brevo contact maps 1:1 to a user. The decision is evaluated identically on every run (no "first run" / "last run" logic):

- `brevo_synced_at IS NULL` → the contact is assumed to lack `MDB_SUBSCRIPTION_ID`, so it is (re)written and `brevo_synced_at` is stamped;
- `brevo_synced_at` set → already synced, skipped (no Brevo call).

The write-back is **skipped** for contacts Brevo reports as `UNSUBSCRIBED` (they are never re-added to the list) and whenever the Brevo check fails (retried on the next run). `brevo_synced_at` is stamped **only after a successful write** and **never in dry-run mode**. Setting `brevo_synced_at` is the only update the task makes to an existing `app_user` row. Counts are reported as `brevo_synced` / `brevo_sync_failed`. Requires `BREVO_API_ANNOUNCEMENTS_LIST_ID` to be set; without it the write-back is skipped.

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
| `brevo_synced` | Contacts written back to Brevo with `MDB_SUBSCRIPTION_ID` (in dry-run, contacts that would be written) |
| `brevo_sync_failed` | Contacts where the Brevo write-back failed (non-fatal; retried next run) |
| `dry_run` | Whether the task ran in dry-run mode |

### `reconcile_announcements_from_brevo`

Propagates Brevo-originated unsubscribes back into the users DB for the
`api.announcements` notification. This is the **reverse** direction of the forward
opt-in path: when a user toggles their subscription on our side (the `update_user`
/ subscription endpoints, via `set_announcements_optin`) or `migrate_firebase_users`
seeds it, flag + subscription + Brevo are kept consistent. But when a user clicks
**unsubscribe inside a Brevo email**, Brevo sets `email_blacklisted` (global) or adds
the list to `list_unsubscribed`, and nothing propagates that back — so
`app_user.is_registered_to_receive_api_announcements` and the
`notification_subscription.active` row stay stale-`true`. This task closes that gap.

It is deliberately **turn-OFF only**. For every user with an **active**
`api.announcements` subscription, it reads `get_contact_subscription_status(email,
BREVO_API_ANNOUNCEMENTS_LIST_ID)`. When Brevo reports `UNSUBSCRIBED` (either the
global `email_blacklisted` flag or the announcements list appearing in
`list_unsubscribed`), it sets `is_registered_to_receive_api_announcements = false`
and deactivates the subscription (`active = false`). `SUBSCRIBED` / `NOT_FOUND` are
left untouched — this task **never** re-subscribes or adds anyone to the list.

It only iterates **active** announcements subscriptions (a user already turned off
is already consistent), which also keeps Brevo API usage down. Once a subscription
is deactivated it drops out of the active set, so re-runs skip it: the task is
**idempotent** and restartable.

```json
{
  "task": "reconcile_announcements_from_brevo",
  "payload": {
    "dry_run": true,
    "limit": null
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Read and count without any DB writes. Brevo is still queried so counts are accurate |
| `limit` | int \| null | `null` | Maximum number of active announcements subscriptions to examine per run; omit or pass `null` for no limit |

**Required environment variables**:
- `BREVO_API_KEY` (secret) — Brevo API key
- `BREVO_API_ANNOUNCEMENTS_LIST_ID` — numeric Brevo list ID for API announcements. If unset/invalid the task still runs but honors only the global `email_blacklisted` flag (list-level unsubscribes are ignored)
- `USERS_DATABASE_URL` (secret) — PostgreSQL connection string for the users DB

**Response fields**:

| Field | Description |
|---|---|
| `checked` | Active announcements subscriptions whose Brevo status was read |
| `reconciled_unsubscribed` | Users turned OFF (flag cleared + subscription deactivated) because Brevo reports them unsubscribed |
| `still_subscribed` | Users Brevo reports as still subscribed (left untouched) |
| `not_found` | Users not found as a Brevo contact (left untouched; never added) |
| `brevo_failed` | Users whose Brevo check failed (non-fatal; retried next run) |
| `skipped_no_email` | Subscriptions whose user row had no email (cannot be looked up on Brevo) |
| `dry_run` | Whether the task ran in dry-run mode |

### `notifications_dispatch_batch` (+ `notifications_dispatch`, `notifications_dispatch_monitor`)

Notification dispatch is a **Cloud Tasks fan-out** of three tasks:

- **`notifications_dispatch_batch`** (producer) — resolves cadences, finds active
  `notification_subscription` rows, registers a run in `TaskExecutionTracker`,
  and enqueues one worker task per subscription plus a single monitor task.
  Triggered by the daily Cloud Scheduler job (disabled in dev/qa) or manually.
- **`notifications_dispatch`** (worker, one per subscription) —
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
  "task": "notifications_dispatch_batch",
  "payload": {
    "cadence": "scheduled",
    "weekly_weekday": 0,
    "dry_run": false,
    "status_filter": "new",
    "user_ids": [],
    "force": false,
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
| `force` | bool | `false` | When `user_ids` is set, bypass the cadence check |
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

### `backfill_changelog`

Backfills `gtfs_dataset_changelog` records from the **existing** dataset history. The live pipeline (`batch_process_dataset` → `gtfs-datasets-comparer`) only produces changelogs for new datasets going forward; this task walks the stored history and, for each consecutive `(base, new)` dataset pair that has no changelog row yet, dispatches a Cloud Task to the same `gtfs-datasets-comparer` function.

The task is **idempotent / restartable**: pairs that already have a changelog row are skipped (unless `force` is set), and each dispatched Cloud Task runs with `disallow_overwrite=true`. It is **rate-limited**: `limit` caps how many feeds are processed per invocation, and a dedicated Cloud Tasks queue (`GTFS_CHANGE_TRACKER_QUEUE`) throttles the actual comparer invocations. Call it repeatedly to walk the whole catalog.

Only **comparable** datasets are considered: a dataset must have a `downloaded_at` timestamp and extracted GTFS files registered in the db (`gtfsfile` rows), since the comparer reads those pre-extracted files. Datasets without extracted files are skipped, and a feed needs at least two comparable datasets to produce a pair.

```json
{
  "task": "backfill_changelog",
  "payload": {
    "dry_run": true,
    "limit": 100,
    "datasets_per_feed": 3,
    "stable_feed_ids": null,
    "feeds_not_updated_days": null,
    "force": false
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `dry_run` | bool | `true` | Enumerate the pairs that would be dispatched without creating any Cloud Task. The response includes a `dispatched` list of the pairs |
| `limit` | int \| null | `100` | Maximum number of feeds processed per invocation; omit or pass `null` for no limit |
| `datasets_per_feed` | int | `3` | Number of most recent datasets considered per feed. `N` datasets produce up to `N-1` consecutive pairs (must be `>= 2`) |
| `stable_feed_ids` | list[str] \| null | `null` | If provided, only process feeds with these stable IDs |
| `feeds_not_updated_days` | int \| null | `null` | If provided, only process feeds whose most recent dataset is older than this many days (e.g. `30` to target feeds not updated in the last month) |
| `force` | bool | `false` | If `true`, dispatch every pair even when a changelog row already exists, and run the comparer with `disallow_overwrite=false` so existing changelogs are regenerated (forces a full rerun) |

**Required environment variables**: `GTFS_CHANGE_TRACKER_QUEUE`, `PROJECT_ID`, `GCP_REGION`, `ENVIRONMENT` (used to dispatch Cloud Tasks to the `gtfs-datasets-comparer` function).

> Note: the comparer reads the pre-extracted GTFS files from the datasets bucket (`<feed>/<dataset>/extracted/`). Historical datasets whose extracted files are no longer present will surface as comparer-side errors (logged, HTTP 200); the backfill dispatch itself still succeeds.

**Response fields**:

| Field | Description |
|---|---|
| `feeds_processed` | Feeds that had at least one consecutive pair to consider |
| `feeds_skipped_recent` | Feeds skipped because of `feeds_not_updated_days` |
| `pairs_found` | Total consecutive pairs examined |
| `pairs_already_done` | Pairs skipped because a changelog row already exists |
| `pairs_dispatched` | Pairs dispatched (or, in `dry_run`, that would be dispatched) |
| `dispatched` | (dry-run only) list of `{feed_stable_id, base_dataset_stable_id, new_dataset_stable_id}` |


### update_seal_of_reliability

Evaluates the implemented Seal of Reliability criteria (issue #1761) for a given list of GTFS
feeds and updates the `sealcriterion` and `feedreliabilityseal` tables. Reads the source
tables and never modifies them.

The task always runs against an explicit `stable_feed_ids` list — there is no
run-the-whole-catalogue mode. Eligibility is applied on top of the list: a requested feed is
evaluated only if it is GTFS, `operational_status = published`, and `status NOT IN
(deprecated, development)`. `inactive` and `future` feeds are kept: skipping a feed freezes
its stored rows rather than making it neutral.

`seal_criterion_name` in the database declares all six criteria, so adding an evaluator
needs no schema change. The criteria still to be implemented are tracked by #1784 and #1782.

```json
{
  "task": "update_seal_of_reliability",
  "payload": {
    "dry_run": true,
    "stable_feed_ids": ["mdb-1210"]
  }
}
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `stable_feed_ids` | list[str] | **required** | The feeds to evaluate; must be non-empty. Ids that are unknown or not eligible are skipped with a logged warning naming them; it raises only when *none* of them can be evaluated. `feeds` in the response covers every requested feed |
| `dry_run` | bool | `true` | Evaluate the feeds and return the report without writing anything |
| `limit` | int \| null | `null` | Cap the number of feeds evaluated, from the list |
| `criteria` | list[str] \| null | `null` | Evaluate only these criteria. Naming a criterion that has no evaluator yet raises. A subset of the implemented criteria skips the `has_seal` roll-up, since the ones not evaluated cannot be judged |
| `batch_size` | int | `200` | Feeds loaded per query batch. Every eligible feed is still evaluated — this only sizes the queries |
| `max_reported_feeds` | int | `50` | Cap on the `feeds` list in the response. Everything is still evaluated and written; `feeds_omitted` says how many entries were left out |
| `now` | str \| null | `null` | ISO timestamp to evaluate against. Defaults to the current UTC time. Shifts the clock used for grace-period and probation arithmetic, but the source tables are still read at their current state, so this is not a full past-day replay — see #1761 for the retroactive-recalculation design |

**Response fields**:

| Field | Description |
|---|---|
| `total_feeds` | Feeds evaluated |
| `criteria` | The criteria evaluated in this run |
| `partial_run` | True when `criteria` was a subset, meaning `has_seal` was not recalculated |
| `criterion_rows_written` | `sealcriterion` rows inserted or updated (`0` on a dry run) |
| `unknown` | Criterion evaluations whose inputs were missing this run. The stored confirmed status is left standing, so the criterion stays in the roll-up — an outage freezes a criterion, it does not waive it |
| `not_applicable` | Criterion evaluations that do not apply to the feed (e.g. a seasonal feed for a coverage criterion). The criterion is withdrawn from the `has_seal` roll-up |
| `seals_before_run` | Feeds that held the seal before this run |
| `seals_after_run` | Feeds holding it afterwards — on a dry run, what *would* be stored |
| `seals_granted` / `seals_revoked` | Transitions in this run. `before + granted - revoked == after` |
| `granted_stable_ids` / `revoked_stable_ids` | The feeds behind `seals_granted` / `seals_revoked` — the two transitions written to `feedreliabilityseal` in this run |
| `first_evaluations` | Criteria that produced their first verdict this run (no prior `pass`/`fail`; a row of earlier `unknown` attempts still counts as a first verdict) |
| `feeds` | One entry per requested feed (every one is reported), capped at `max_reported_feeds`: `stable_id`, its `feedreliabilityseal` state (`had_seal`, `has_seal`), and a nested `criteria` list holding every criterion of that feed with `observed_status`, `confirmed_status`, `previously_confirmed_status`, `phase` (`steady`, `in_grace_period` or `on_probation`) and `reason` |
| `feeds_omitted` | Feeds left out of `feeds` by the cap. `sealcriterion` and `feedreliabilityseal` hold everything regardless |

#### Running it locally

Start Postgres and the function, then post to it:

```shell
docker compose --env-file ./config/.env.local up -d --force-recreate
scripts/function-python-run.sh --function_name tasks_executor --no_install_venv
```

```shell
curl -s -X POST http://localhost:8080 -H "Content-Type: application/json" \
  -d '{"task":"update_seal_of_reliability","payload":{"dry_run":true,"stable_feed_ids":["mdb-1210"]}}' \
  | python3 -m json.tool
```

`Accept: text/csv` returns a single summary row (the top-level report fields), not one row
per feed — the converter flattens the returned dict, and `feeds` lands in it as a single
stringified cell. Use the JSON response for per-feed and per-criterion detail.

Nothing about this task needs GCP credentials — only `FEEDS_DATABASE_URL`.
