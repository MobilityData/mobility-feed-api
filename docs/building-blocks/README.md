# Building blocks

Reusable mechanisms this repository already has. Check here before building new
infrastructure, and update the entry when you change a block.

Each entry is short. Blocks with more moving parts have a detail page; for everything
else the module docstring is the full reference.

| Block | One line | Detail |
|---|---|---|
| [Tasks executor](#tasks-executor) | One Cloud Function that runs named tasks | - |
| [Task execution tracking](#task-execution-tracking) | Durable state of a run and each entity in it | [page](task-execution-tracking.md) |
| [Fan-out with a monitor](#fan-out-with-a-monitor) | Split a run into Cloud Tasks batches, settle it once | [page](fanout.md) |
| [T-shirt sizing](#t-shirt-sizing) | Route a job to the smallest worker that fits | [page](tshirt-sizing.md) |
| [Cloud Tasks enqueue](#cloud-tasks-enqueue) | Shared helpers to create HTTP tasks | - |
| [Per-feed configuration](#per-feed-configuration) | Global config keys with per-feed overrides | - |
| [User feature flags](#user-feature-flags) | Gate behaviour per user | - |
| [CDN cache for latest.zip](#cdn-cache-for-latestzip) | Cache headers and invalidation | - |
| [Website revalidation](#website-revalidation) | Refresh feed pages on the website | - |
| [Runtime metrics](#runtime-metrics) | Measure time, memory and CPU of a job | - |
| [Work directory and memory limits](#work-directory-and-memory-limits) | Local files in memory: split the budget, clean up after crashed runs | [page](workdir-and-memory.md) |

Covered in [CLAUDE.md](../../CLAUDE.md) and not repeated here: spec-first code
generation, `with_db_session`, error handling, and shared code symlinked into functions.

---

## Tasks executor

- **What:** A single Cloud Function that receives `{"task": "<name>", "payload": {...}}` and
  runs the matching handler.
- **Use when:** You need a scheduled job, a backfill, or a Cloud Tasks worker that does not
  justify its own function.
- **Entry point:** [`functions-python/tasks_executor/src/main.py`](../../functions-python/tasks_executor/src/main.py)
  (the `tasks` dict).
- **Rules:**
  - Register the handler in `tasks` with a `description`; `list_tasks` returns them all.
  - Accept `dry_run` for anything that writes, and default it to safe.
  - Raise `TaskInProgressError` to answer 503, which makes Cloud Tasks retry (used by
    monitors to poll).
  - Cloud Scheduler jobs that call it set `attempt_deadline` in
    `infra/functions-python/main.tf`; keep it above the task's real duration.
- **Used by:** seal of reliability, [notification dispatch](../notifications.md), [validation reports](../../functions-python/tasks_executor/src/tasks/validation_reports/README.md), data imports, and the other tasks
  listed in its [README](../../functions-python/tasks_executor/README.md).

## Task execution tracking

- **What:** `TaskExecutionTracker` records a run (`task_run`), each entity in it
  (`task_execution_log`), and every attempt (`task_execution_attempt`).
- **Use when:** Work spans requests or retries and you must know what is done, prevent
  double processing, or count attempts.
- **Entry point:** [`functions-python/helpers/task_execution/task_execution_tracker.py`](../../functions-python/helpers/task_execution/task_execution_tracker.py)
- **Rules:**
  - Use `try_acquire` in the worker when the work must not run twice; `mark_triggered` is
    an upsert, not a lock.
  - `completed` is never reclaimed; call `release_for_retry` to redo finished work.
  - Heartbeat long work, or the 30 minute lease expires and another worker takes over.
- **Used by:** [Parquet builder](../../functions-python/parquet_builder/README.md), [parquet feed browsing](../parquet-feed-browsing.md), [validation reports](../../functions-python/tasks_executor/src/tasks/validation_reports/README.md), [notification dispatch](../notifications.md), seal of reliability.
  See the [detail page](task-execution-tracking.md).
- **Legacy, do not extend:** `DatasetTraceService` / `BatchExecutionService` in
  `functions-python/dataset_service` (Datastore), still used by `batch_datasets`,
  `batch_process_dataset` and `gbfs_validator`.

## Fan-out with a monitor

- **What:** A producer splits a run into batches, enqueues one worker task per batch and
  one delayed monitor that settles the run.
- **Use when:** A run over the catalogue is too long for one request.
- **Entry point:** `plan_fanout` in
  [`tasks_executor/src/tasks/seal_of_reliability/fanout.py`](../../functions-python/tasks_executor/src/tasks/seal_of_reliability/fanout.py)
- **Rules:**
  - Workers must be safe to run twice (Cloud Tasks delivers at least once).
  - The monitor polls with `TaskInProgressError` and must have a deadline.
- **Used by:** seal of reliability (nightly and backfill), [notification dispatch](../notifications.md). See the
  [detail page](fanout.md).

## T-shirt sizing

- **What:** Deploy one function at several sizes (S, M, L) and choose one per job at enqueue
  time; move a feed up after a resource failure and down after repeated successes.
- **Use when:** A function's worst case needs far more memory or disk than its typical job.
- **Entry point:** [`functions-python/helpers/sizing.py`](../../functions-python/helpers/sizing.py)
  (mechanism), [`functions-python/helpers/parquet_policy.py`](../../functions-python/helpers/parquet_policy.py) (example policy).
- **Rules:**
  - An unknown measure routes to the largest size.
  - A per-feed override decides on its own.
  - Tiers in code must match the size map in `infra/functions-python/main.tf`.
- **Used by:** [Parquet builder](../../functions-python/parquet_builder/README.md), [parquet feed browsing](../parquet-feed-browsing.md). See the [detail page](tshirt-sizing.md).

## Cloud Tasks enqueue

- **What:** Helpers that create authenticated HTTP Cloud Tasks.
- **Use when:** One service or task needs to call a function asynchronously.
- **Entry point:** `create_http_task_with_name` in
  [`api/src/shared/common/gcp_utils.py`](../../api/src/shared/common/gcp_utils.py);
  per-target wrappers (`create_http_*_task`) in
  [`functions-python/helpers/utils.py`](../../functions-python/helpers/utils.py).
- **Rules:**
  - A task name deduplicates: a second task with the same name is skipped. Names stay
    reserved for about an hour after completion, so do not name tasks that may need a
    quick retry; deduplicate with a tracker claim instead.
  - Pass `raise_on_error=True` when you record state based on the enqueue succeeding.
  - Queue retry behaviour lives in Terraform, not in code.
- **Used by:** most functions, for example [Parquet builder](../../functions-python/parquet_builder/README.md), [PMTiles builder](../../functions-python/pmtiles_builder/README.md), [reverse geolocation](../../functions-python/reverse_geolocation/README.md), [GTFS file data extractor](../../functions-python/gtfs_file_data_extractor/README.md), [`batch_process_dataset`](../../functions-python/batch_process_dataset/README.md),
  [notification dispatch](../notifications.md).

## Per-feed configuration

- **What:** `config_key` holds a namespaced key and its global default; `config_value_feed`
  holds per-feed overrides.
- **Use when:** One feed needs different behaviour (download headers, worker size).
- **Entry point:** `get_config_value` in
  [`api/src/shared/common/config_reader.py`](../../api/src/shared/common/config_reader.py)
- **Rules:**
  - Register the key with a Liquibase changeset (the override's foreign key needs it).
  - Validate values in `operations_api/.../config_value_schemas.py`.
  - Operators edit overrides through the Operations API
    (`/v1/operations/feeds/{id}/config/{namespace}/{key}`).
- **Used by:** `feed_download/http_headers` (feed downloads, `_get_http_headers_override` in
  `helpers/utils.py`),
  `parquet_builder/size` ([Parquet builder](../../functions-python/parquet_builder/README.md)).

## User feature flags

- **What:** `feature_flag` (flag and global default) and `user_feature_flag` (per-user
  override) in the users database.
- **Use when:** A feature is visible only to some users (betas, early access, admin tools).
- **Entry point:** `feature_flag_enabled` in
  [`api/src/shared/common/feature_flags.py`](../../api/src/shared/common/feature_flags.py)
- **Rules:**
  - Create flags and grant them through the Operations API (`/v1/operations/feature-flags`),
    not with a Liquibase changeset.
  - Website flags are separate: Firebase Remote Config, see [feature_flag.md](../feature-flag/feature_flag.md).
- **Used by:** User Service notifications and subscriptions, search, admin summary
  subscription; early access programs grant them in bulk.

## CDN cache for latest.zip

- **What:** Only `<feed>/latest.zip` is served through Cloud CDN, cached for a day and
  invalidated after each upload.
- **Use when:** You overwrite `latest.zip` or change how it is served.
- **Entry point:** [`functions-python/helpers/cdn_cache.py`](../../functions-python/helpers/cdn_cache.py)
- **Rules:**
  - Call `invalidate_cdn_cache` after overwriting the object.
  - Keep `max-age=0` so clients downstream of the CDN never hold a stale copy.
- **Used by:** [`batch_process_dataset`](../../functions-python/batch_process_dataset/README.md).

## Website revalidation

- **What:** Cloud Tasks that ask the website to refresh cached feed pages.
- **Use when:** A change in the database alters what a feed page shows.
- **Entry point:** `create_web_revalidation_task` / `create_web_revalidation_batch_tasks` in
  [`api/src/shared/common/gcp_utils.py`](../../api/src/shared/common/gcp_utils.py)
- **Rules:**
  - Task names are bucketed in 30 minute windows, so repeated calls for one feed collapse
    into one task.
- **Used by:** [`batch_process_dataset`](../../functions-python/batch_process_dataset/README.md), `process_validation_report`, [reverse geolocation](../../functions-python/reverse_geolocation/README.md), [PMTiles builder](../../functions-python/pmtiles_builder/README.md), data imports,
  seal of reliability, Operations API.

## Runtime metrics

- **What:** `track_metrics` logs the time, memory and CPU of a call; `MemorySampler`
  records peak RSS and VMS while a job runs.
- **Use when:** You need evidence to size a function or to compare runs.
- **Entry point:** [`functions-python/helpers/runtime_metrics.py`](../../functions-python/helpers/runtime_metrics.py)
- **Rules:**
  - For sizing, use `MemorySampler`'s peak VMS, not `track_metrics`' `tracemalloc`
    figure; see [why](workdir-and-memory.md#threads-and-address-space).
- **Used by:** [Parquet builder](../../functions-python/parquet_builder/README.md), [PMTiles builder](../../functions-python/pmtiles_builder/README.md), [reverse geolocation](../../functions-python/reverse_geolocation/README.md), export CSV, datasets comparer.

## Work directory and memory limits

- **What:** `EphemeralOrDebugWorkdir`, a per-job directory that also removes stale
  siblings left by crashed runs; `limit_gcp_memory`, which splits the instance memory
  between an in-memory volume for data and a capped process budget.
- **Use when:** A function writes large intermediate files locally, which on Cloud Run
  means into memory.
- **Entry point:** [`functions-python/helpers/ephemeral_workdir.py`](../../functions-python/helpers/ephemeral_workdir.py),
  [`api/src/shared/common/gcp_memory_utils.py`](../../api/src/shared/common/gcp_memory_utils.py)
- **Rules:**
  - Mount a sized in-memory volume so data has its own limit.
  - Use a unique `owner_prefix` and keep request concurrency at 1: the sweep deletes every
    sibling with that prefix.
- **Used by:** [Parquet builder](../../functions-python/parquet_builder/README.md), [PMTiles builder](../../functions-python/pmtiles_builder/README.md), datasets comparer
  (`limit_gcp_memory`), [`batch_process_dataset`](../../functions-python/batch_process_dataset/README.md) (`limit_gcp_memory`).
  See the [detail page](workdir-and-memory.md).
