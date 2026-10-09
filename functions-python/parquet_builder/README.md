# Parquet Builder

Renders a GTFS dataset as Parquet: one file per GTFS table, plus a `manifest.json`
describing the set. The result is published publicly beside the dataset so a browser
can query the feed in place over HTTP range requests, without downloading or unpacking
it.

The Operations API decides *whether* a build is needed and reports progress; this
function does the work. See [Operations API endpoints](#operations-api-endpoints)
below.

## Usage

The function receives the following request:

```
{
  "feed_stable_id": str,       – stable_id of the GTFS feed
  "dataset_stable_id": str,    – stable_id of the dataset to convert
  "force": bool (optional)     – rebuild even if a finished build exists (default: false)
}
```

Example:

```json
{
  "feed_stable_id": "mdb-1210",
  "dataset_stable_id": "mdb-1210-202402121801"
}
```

The function verifies that the dataset stable id starts with the feed stable id.

### Output

```
gs://<DATASETS_BUCKET_NAME>/<feed_stable_id>/<dataset_stable_id>/parquet/
    agency.parquet
    routes.parquet
    stops.parquet
    ...
    manifest.json
```

Objects are made public. They have to be: the reader builds each file's URL from the
base URL's origin and path only, discarding any query string, so a signed URL cannot
survive the round trip.

**The publish order is part of the contract.** Tables go up first, `manifest.json`
last, and stale objects are pruned only afterwards. The manifest is what a reader
holding just the bucket URL uses to learn which tables exist, so publishing it earlier
advertises files that have not arrived - the reader asks for every table and finds only
the handful uploaded so far. Nothing is deleted before the new set is up either: a
rebuild that cleared the prefix first left an already-published dataset unreadable for
the length of the upload, and a reader that has been told the dataset is ready has
stopped polling by then and never finds out. Both orderings are pinned by
`TestPublishIsNotObservablyPartial` in `tests/test_main.py`.

One case is not covered by this and cannot be, short of publishing to a throwaway
prefix and copying: on a **first** build there is no manifest and no `ready` status yet,
so a client that goes straight to the bucket and probes for table names can still catch
a partial set. Clients driven by the Operations API or by the manifest never do.

`manifest.json` - the dataset's description of itself, and the only place a reader
learns what it holds:

```json
{
  "version": 2,
  "generated_at": "2026-09-17T22:41:03+00:00",
  "converter_version": "2",
  "source":  { "kind": "zip", "bytes": 4821334 },
  "totals":  { "uncompressed_bytes": 18422910, "stored_bytes": 903411 },
  "tables": [
    { "name": "stops", "file": "stops.parquet", "rows": 4821, "columns": 12,
      "bytes": 481223, "compressed_bytes": 92210, "parquet_bytes": 41880 }
  ]
}
```

**`bytes` is the source size, not the Parquet size.** In version 1 it meant the
opposite, which is why the version was bumped rather than the field added to: a reader
has to know which it is holding. `compressed_bytes` is what the file weighed inside the
archive and is null for a feed converted from a folder; `parquet_bytes` is the converted
size. The sizes are captured during conversion because they cannot be recovered
afterwards - the CSVs are deleted and the archive is gone.

The Operations API deliberately does **not** repeat this table list. The reader skips
`manifest.json` entirely when it is handed a list, and the manifest is where the sizes
and counts live, so serving one would suppress the load report it draws from them.

### Response

The function returns HTTP 200 even when a build fails, and records the reason in the
database instead. Cloud Tasks retries non-2xx, and nothing here fails transiently in a
way a retry would fix - a corrupt archive is still corrupt on the second delivery.

```json
{ "status": "success", "dataset": "mdb-1210-202402121801", "base_url": "...", "tables": ["agency", "stops"] }
{ "status": "skipped", "reason": "already in progress", "dataset": "mdb-1210-202402121801" }
{ "status": "error",   "error": "Failed to build Parquet for dataset ..." }
```

## What the conversion guarantees

Two properties are load-bearing for the reader and break *silently* rather than loudly
if they change, so they are asserted in `tests/test_converter.py`:

- **Every column is text.** The reader filters with `ILIKE` and `= ''`; a typed column
  still renders but stops matching. `ALL_VARCHAR` on the way in is what guarantees it
  on the way out.
- **An empty CSV field becomes NULL**, not an empty string, because the reader rewrites
  `= ''` into `IS NULL OR = ''` on that basis.

Table names are the GTFS file stem (`stops.txt` → `stops`), plus `locations` flattened
from `locations.geojson`. A file with no header row is skipped; a header with no data
rows is kept, since an empty `frequencies.txt` is a legitimate part of a feed.

`PARQUET_CONVERTER_VERSION` in `src/converter.py` is the run id of the tracking rows,
and must match the constant of the same name in the Operations API implementation.
Bump it when the output changes in a way that makes previously written files wrong: a
bump invalidates every dataset's artifacts rather than serving files a newer reader no
longer matches. It went to `"2"` with manifest v2, so datasets built before that report
as `absent` and rebuild on first request.

## Retention

Each build stamps every object it publishes with a `customTime` of
`now + retention_days` (default 30, 1..60 per request), and the datasets bucket carries
one lifecycle rule - `daysSinceCustomTime: 0`, Delete - that removes an object once its
own `customTime` has passed. One rule, a different date per file, no scheduled job.

The same timestamp goes into the tracking row as `expires_at`, and the Operations API
reports an expired row as `absent`. That is deliberate rather than redundant: lifecycle
deletion is asynchronous and GCS gives no promptness guarantee, so the row cannot be
relied on to vanish with the files. Reporting `absent` from the row is what makes the
dataset rebuild on the next request, and it happens on the date rather than whenever the
bucket gets round to the delete. The window in between - `absent` reported while the
files are still there - is harmless; a rebuild overwrites them.

**The builder must stay the only writer of `customTime` in this bucket.** The lifecycle
rule is bucket-wide and matched solely by the presence of that field (the condition is
never satisfied for an object without it, and `matchesPrefix` cannot express
`*/parquet/`). Anything else that starts setting `customTime` there becomes deletable by
this rule.

Nothing deletes the `task_execution_log` rows; they are small, and one row per converter
version per dataset already accumulates by design.

## Concurrency

A dataset is never converted twice at once. Cloud Tasks delivers at least once, so the
claim is taken by this function rather than by whatever enqueued it:
`TaskExecutionTracker.try_acquire` does a conditional upsert on `task_execution_log`,
and a refused claim makes the function return `skipped` without doing any work.

The claim carries a 30 minute lease, renewed by each progress write. It is deliberately
longer than the function's own 1680s timeout, so an instance GCP has not finished
killing cannot have its work started underneath it. A build killed by OOM or timeout
leaves its claim to expire; one that fails normally releases it immediately.

## Worker sizes

The builder is deployed three times from one source zip, as
`parquet-builder-{s,m,l}-<env>`, each with its own Cloud Tasks queue. The Operations API
picks one at enqueue time.

| Size | Memory | CPU | Volume | DuckDB | Largest uncompressed file | Share of feeds |
|---|---|---|---|---|---|---|
| `s` | 3Gi | 1 | 1Gi | 512MB | < 256 MB | ~98% |
| `m` | 7Gi | 2 | 3Gi | 1GB | < 1.5 GB | ~1.8% |
| `l` | 16Gi | 4 | 8Gi | 2GB | anything larger, or unknown | ~0.2% |

A feed pinned through config bypasses the table entirely; see below.

The bands are measured rather than guessed. Across 4277 feeds the median archive is
0.2 MB and only 31 exceed 100 MB, while about ten hold a single member over 1 GB and the
largest holds one of 4.8 GB. The catalogue is not a spectrum: it is a great many trivial
feeds, a thin band of medium ones, and roughly a dozen large ones.

Two rules set the numbers for each rung:

- **the volume** must hold the largest member plus its Parquet output, and is carved out
  of the total rather than added to it;
- **the process budget** left over must cover the process's *address space*, which is
  what `RLIMIT_AS` caps - not its resident size. Measured across ten feeds:

  | rung | budget | DuckDB cap | peak RSS | peak VMS | VMS of budget |
  |---|---|---|---|---|---|
  | `s` | 1848 MiB | 512MB | 443 MB | 816 MB | 44% |
  | `m` | 3896 MiB | 1GB | 1056 MB | 2297 MB | 59% |
  | `l` | 7992 MiB | 2GB | 2496 MB | 5571 MB | 70% |

  **VMS runs about 2.2-2.8x the DuckDB cap, and 2-3x peak RSS.** Baseline VMS is ~550 MB
  before any work. Size a rung from `vms`; sizing from `rss` under-provisions by about
  half, which is how `l` ended up at a 3896 MiB budget and killed mdb-2014 with
  `MemoryError`, and how `s` ended up at 824 MiB and died on a 41.7 MB feed with a
  DuckDB `OutOfMemoryException`. The `s` and `m` figures above are post-fix; both were
  raised a rung after those runs.

**The measure is the largest single file, not the archive or the feed total.** The volume
holds one source at a time, so that file is what decides whether a build fits. A total
would misjudge a feed of many medium files, and the compressed size misjudges almost
everything: mdb-2014 is a 1.08 GiB archive containing a 4.07 GiB `stop_times.txt`.

It comes from `max(gtfsfile.file_size_bytes)` for the dataset. Those rows are absent for
datasets processed before they existed, so the measure falls back to
`unzipped_size_bytes`, then to `zipped_size_bytes` times a conservative ratio, then to
nothing. **An unknown size routes to `l`**, never `m` - guessing small turns a missing row
into an OOM. The log line says which rung answered; if it says `unknown`, run the
`rebuild_missing_dataset_files` task to record them.

Separate queues are the point rather than a side effect. `max_concurrent_dispatches` caps
memory across concurrent instances, so a single queue has to be sized for the heaviest job
and a run of large builds leaves the short ones waiting behind them.

### Pinning a feed by hand

One key, `size`, under namespace `parquet_builder`, registered by
`liquibase/changes/feat_parquet_builder_size.sql` - no new table, just the `config_key`
row that `config_value_feed`'s foreign key needs.

One row per feed. **An override decides which worker runs the build**, in place of the
size the dataset would otherwise measure into. Two forms, differing only in what they
record about who wrote it:

| value | set by |
|---|---|
| `"l"` | a person |
| `{"size": "l", "source": "auto"}` | the builder, after a build ran out of resources |

Both decide outright. The source is carried for the record - it shows up as
`variant_basis` on each attempt - and changes nothing about the routing. The bare form is
the one to type by hand:

```sql
INSERT INTO config_value_feed (feed_id, feed_stable_id, namespace, key, value)
SELECT id, stable_id, 'parquet_builder', 'size', '"l"'::jsonb
  FROM feed WHERE stable_id = 'mdb-2014'
ON CONFLICT (feed_id, namespace, key) DO UPDATE SET value = EXCLUDED.value;
```

With no per-feed row, every feed is routed purely by measurement. The key carries no
`default_value` on purpose: setting one would move the whole catalogue at once, which
belongs in the routing table in `parquet_api_impl.py` instead.

**An override is absolute.** The measurement is not consulted at all - not even computed
- so an override can send a feed either way. The flip side is that setting one below what
a feed needs will fail it with `ENOSPC` or `MemoryError`, so check the build after
changing one.

Weighing the builder's own override against the measurement instead, so a grown feed
could overtake it, was considered and dropped: it changes the outcome only when the
measurement is larger, and that case already resolves itself - the build fails and the
escalation moves it up. One wasted build is not worth a second code path.

**The builder only writes a row where it disagrees with the measurement.** Escalating a
feed whose dataset already measures into the target size stores nothing, and clears an
earlier `auto` row that the measurement has since caught up with - the dataset is on its
way to that worker through the task either way. So the table holds the feeds that are
genuinely exceptions, and a feed leaves it as soon as its own data says the same thing.

A person's pin is never cleared automatically: it may agree with today's measurement and
still be there on purpose.

An unrecognised value is logged and ignored rather than failing the request.

There is no endpoint or UI for `config_value_feed`, so this is SQL for now.

### Coming back down

An `auto` override is reviewed on the success path, in `_downsize_after_success`, and
lowered a rung when the feed's recent builds say it can be. Nothing is re-queued: the
build in hand has already succeeded, so the new size applies to the feed's next one.

The two directions are deliberately asymmetric. Escalation acts on a single failure,
because being too small costs a build that cannot finish. Coming down is only ever an
economy, so it waits for `DOWNSIZE_STREAK` builds in a row that each left
`DOWNSIZE_HEADROOM` of the smaller worker unused - 3 and 60% today, both in
`helpers/parquet_policy.py`.

Each of those builds is checked on both axes, because either one can end a build:

| axis | evidence | compared against |
|---|---|---|
| memory | peak address space during the build | that rung's `RLIMIT_AS` budget |
| disk | largest uncompressed member actually opened | that rung's band ceiling |

Both numbers come from the build itself, recorded on the attempt row - `peak_vms_bytes`,
and `largest_member_bytes` in its `metadata`. The measurement in the database is
deliberately not consulted: an override exists precisely because that measurement was
wrong about this feed, so reading it again to justify undoing the override would be
circular.

Four things stop a review short, before any history is read: the feed has no override
(it already routes on its measurement, which is as low as it goes), the override is a
person's, the worker is already the smallest, or the override disagrees with the worker
that just ran. An attempt recorded before this evidence existed has no
`largest_member_bytes` and reads as unknown, which blocks the streak rather than
permitting it - leaving a feed too large costs money, the other way costs builds.

The case to watch is a feed whose datasets alternate between large and small: it could
move down, fail on the next large one, escalate, and repeat. The disk axis usually
catches it, because the large dataset's own build breaks the streak - but that is a
property of the evidence, not a guarantee. `task_execution_attempt` shows it if it
happens; the fix is a longer streak or a smaller fraction.

### Where the policy lives

The routing *mechanism* is `functions-python/helpers/sizing.py`, shared so other
functions can adopt it without copying: `choose_size` for the tier arithmetic,
`size_for_dataset` for the whole decision, `escalate` and `demote` for the ladder, and
`fits_within` for the two-axis comparison.

The Parquet builder's *policy* is `functions-python/helpers/parquet_policy.py` - its
bands and their budgets, its config namespace and key, its compression ratio, and the
two downsize thresholds. It is shared rather than per-function because two processes
decide the same thing and have to agree: the Operations API routes a build when it
enqueues one, and the builder re-routes it when one fails. A disagreement would bounce a
dataset between two workers.

One thing to look at before a second function adopts it: the measure. The largest single
uncompressed file is right here because the volume holds one at a time, but a function
bounded by something else wants `choose_size` with a measure of its own.

## Memory

The function's allocation is **split**, not shared: the in-memory volume is carved out of
the total rather than added to it.

Per variant, taking `l` as the example:

```
cgroup limit (the variant's "memory")          16384 MiB
  - in-memory volume at PARQUET_TMPDIR        -  8192 MiB
  - MEMORY_MARGIN_MB                          -   200 MiB
  = RLIMIT_AS set on the Python process          7992 MiB
```

The same arithmetic gives `m` 3896 MiB and `s` 1848 MiB. The small volumes are viable
only because the archive is streamed rather than written to them.

All three rungs live in `local.parquet_builder_sizes` in `infra/functions-python/main.tf`.
Memory and volume are set together there on purpose: the volume is subtracted from the
total, so splitting them across files invites a rung whose process budget is accidentally
negative.

`limit_gcp_memory` (`shared/common/gcp_memory_utils.py`) does that subtraction at import,
before anything allocates, and sets `RLIMIT_AS`. The point is that an overshoot raises a
catchable `MemoryError` with a traceback instead of the kernel killing the container
silently. It reads the volume's *declared* size, so it is subtracted whether or not a
byte is written to it. Both numbers are logged on every cold start:

```
Process memory limit: 16384.00 MiB, total tmpfs size: 8192.00 MiB, available: 8192.00 MiB
RLIMIT_AS set to 7992.00 MiB
```

If `total tmpfs size` reads `0.00 MiB`, the volume did not get mounted and the process is
running with the full cgroup limit as its budget. That is a broken deploy, not a safe one.

Three consumers, bounded differently:

| Consumer | Bound | Overshoot |
|---|---|---|
| The workdir under `PARQUET_TMPDIR` | 8Gi, by the volume's own `size-limit` | `ENOSPC` |
| DuckDB | `PARQUET_DUCKDB_MEMORY_LIMIT`, 2GB | spills, see below |
| The Python process | `RLIMIT_AS` | `MemoryError` |

**The tmpfs is the real limit, not the total.** DuckDB's spill directory is inside the
workdir, so spilling does not release memory from the container - it moves bytes out of
DuckDB's budget and into the tmpfs. A feed whose largest single CSV plus its Parquet plus
the spill exceeds the volume fails with `ENOSPC` no matter how much total memory the
function has. Raising the total without raising the volume does not help that case.

Size the volume from the **largest single uncompressed file** in the feed, not from the
archive or the feed total. The archive path needs more again, because the `.zip` stays
resident for the whole build:

```
both paths:  largest file + its Parquet + DuckDB spill
```

The worked example is mdb-2014, whose 1.08 GiB archive holds a 4.07 GiB `stop_times.txt`
and a 2.04 GiB `shapes.txt`. It once needed 1.08 + 4.07 = 5.15 GiB before conversion
started, and failed with `ENOSPC` on a 4Gi volume; now that the archive is streamed the
same feed needs 4.07 GiB plus its output. Read those numbers off any archive without
downloading it using
`zip_member_sizes_from_file` with `TailReader` over a ranged read of the last 1 MiB, which
is what the builder itself does to record compressed sizes.

What keeps usage low is that the conversion streams: one source file and one Parquet output
exist at a time, each deleted before the next begins, so peak tracks the largest single
table rather than the whole feed. This holds on both paths - the archive is read over the
network through `Blob.open("rb")`, a seekable reader that `zipfile` drives directly, so it
is never written to the volume. Members are converted in archive order rather than table
order, because a backward seek discards the reader's buffer and refetches; the manifest is
sorted by name afterwards so it does not depend on which path produced it.

Sizing from observed averages is a trap here: feed sizes span orders of magnitude, so a
sample that happens to exclude the largest feeds will suggest a volume that cannot build
them at all. The process budget is the part that measurement does settle - the largest
observed `process peak` is 2329 MB on `l`, but that is resident, not address space, and
`RLIMIT_AS` caps the latter - read `vms` for sizing. Note that the
`Function metrics` log
line reports `tracemalloc` for `memory:`, which sees Python allocations only - not DuckDB's
C++ heap and not tmpfs pages. Use the `rss` figure on that same line, or Cloud Monitoring's
`run.googleapis.com/container/memory/utilizations`, when sizing. There is no telemetry from
qa or prod yet, so the largest feeds in the catalogue may not have been converted.

# GCP environment variables

- `DATASETS_BUCKET_NAME`: bucket where datasets are stored, including the environment
  suffix (`-dev`, `-qa`, `-prod`). The function fails if this is not defined.
- `PUBLIC_HOSTED_DATASETS_URL`: public URL prefix the artifacts are served from; used
  to build the `base_url` reported back to callers.
- `FEEDS_DATABASE_URL` (secret): used for the claim and for progress reporting.
- `PARQUET_TMPDIR`: the in-memory volume everything large is written to
  (default `/tmp/in-memory`). `limit_gcp_memory` reads its size to compute the process
  budget, so this must point at the mounted volume.
- `PARQUET_DUCKDB_MEMORY_LIMIT`: DuckDB's own budget (default `2GB`). Set explicitly
  because DuckDB otherwise sizes itself from the host's RAM rather than the cgroup, and
  so would spill far too late to help.
- `MEMORY_MARGIN_MB`: margin subtracted before `RLIMIT_AS` is set (default `200`).

# Local testing

## Generating Parquet without GCP

`scripts/parquet-generate-local.sh` runs the same conversion this function runs -
importing `converter.convert_to_parquet` rather than reimplementing it - against a feed
on disk or a public URL. No bucket, database, task queue or credentials involved.

```bash
# A feed id: downloads its current archive over HTTPS
scripts/parquet-generate-local.sh mdb-1210

# A specific dataset, from a non-production environment
scripts/parquet-generate-local.sh mdb-1210-202402121801 --env dev

# A feed already on disk, as an archive or an unpacked folder
scripts/parquet-generate-local.sh ./gtfs.zip
scripts/parquet-generate-local.sh ./extracted/
```

Output goes to `.dist/parquet/<source>` unless `--out` says otherwise. The virtualenv
and `duckdb` are provisioned on first run; nothing else is needed.

## Serving it to a browser

```bash
scripts/parquet-generate-local.sh mdb-1210 --serve        # http://localhost:8090
```

`--serve` exists because the obvious alternative does not work: `python -m http.server`
ignores `Range` and returns whole files, so a reader asking for a Parquet footer gets
the entire table. The built-in server answers ranges (including the suffix ranges a
footer read uses) and sends the CORS headers a cross-origin worker needs.

## With the operations web app

The operations web app serves `public/datasets/<id>` as a static dataset, so generating
straight into it is enough to browse a real feed:

```bash
scripts/parquet-generate-local.sh mdb-1210 \
  --out <path-to-operations-web>/public/datasets/mdb-1210

cd <path-to-operations-web> && yarn dev
# then open /feeds/gtfs/mdb-1210/browse
```

## Exercising the whole path, including the Operations API

Only needed when the endpoints themselves are what is being tested. Cloud Tasks does
not dispatch locally - the `PARQUET_BUILDER_QUEUE_M`/`_L` vars are unset, so the enqueue
is a logged no-op - which means the builder is invoked by hand in place of the queue.

```bash
# 1. Database and Operations API (http://localhost:8081)
docker-compose --env-file ./config/.env.local up -d
scripts/api-operations-start.sh

# 2. The builder, against a real bucket
gcloud auth application-default login
scripts/function-python-setup.sh --function_name parquet_builder
DATASETS_BUCKET_NAME=mobilitydata-datasets-dev \
PUBLIC_HOSTED_DATASETS_URL=https://dev-files.mobilitydatabase.org \
  scripts/function-python-run.sh --function_name parquet_builder   # http://localhost:8080

# 3. Stand in for Cloud Tasks
curl -X POST localhost:8080 -H 'Content-Type: application/json' \
  -d '{"feed_stable_id":"mdb-1210","dataset_stable_id":"mdb-1210-202402121801"}'

# 4. Watch the API report absent -> preparing -> ready
curl localhost:8081/v1/operations/gtfs_datasets/mdb-1210-202402121801/parquet
```

To skip GCS entirely at step 2, run the builder against a local feed with
`scripts/parquet-generate-local.sh` and point the viewer at the output instead; only
the database-backed status reporting needs the function itself.

## Unit tests

```bash
scripts/api-tests.sh --folder functions-python/parquet_builder
```

The suite needs no network and no GCP: Cloud Storage is faked, and the archives the
tests convert are real zips built in-process.

# Operations API endpoints

The endpoints a client drives to request and follow a build, the states they report, and
what a client fetches once a set is ready, are documented in
[docs/parquet-feed-browsing.md](../../docs/parquet-feed-browsing.md) - including the
authentication the spec gets wrong and the CORS requirement the browser reader depends on.

Implemented in `functions-python/operations_api/src/feeds_operations/impl/parquet_api_impl.py`,
specified in `docs/OperationsAPI.yaml`.
