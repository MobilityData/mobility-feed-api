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

`manifest.json`:

```json
{
  "version": 1,
  "converter_version": "1",
  "tables": [
    { "name": "stops", "file": "stops.parquet", "rows": 4821, "bytes": 148213 }
  ]
}
```

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

`PARQUET_CONVERTER_VERSION` in `src/converter.py` is the run id of the tracking rows.
Bump it when the output changes in a way that makes previously written files wrong: a
bump invalidates every dataset's artifacts rather than serving files a newer reader no
longer matches.

## Concurrency

A dataset is never converted twice at once. Cloud Tasks delivers at least once, so the
claim is taken by this function rather than by whatever enqueued it:
`TaskExecutionTracker.try_acquire` does a conditional upsert on `task_execution_log`,
and a refused claim makes the function return `skipped` without doing any work.

The claim carries a 30 minute lease, renewed by each progress write. It is deliberately
longer than the function's own 1680s timeout, so an instance GCP has not finished
killing cannot have its work started underneath it. A build killed by OOM or timeout
leaves its claim to expire; one that fails normally releases it immediately.

# GCP environment variables

- `DATASETS_BUCKET_NAME`: bucket where datasets are stored, including the environment
  suffix (`-dev`, `-qa`, `-prod`). The function fails if this is not defined.
- `PUBLIC_HOSTED_DATASETS_URL`: public URL prefix the artifacts are served from; used
  to build the `base_url` reported back to callers.
- `FEEDS_DATABASE_URL` (secret): used for the claim and for progress reporting.

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
not dispatch locally - `PARQUET_BUILDER_QUEUE` is unset, so the enqueue is a logged
no-op - which means the builder is invoked by hand in place of the queue.

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

Implemented in `functions-python/operations_api/src/feeds_operations/impl/parquet_api_impl.py`,
specified in `docs/OperationsAPI.yaml`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/operations/gtfs_feeds/{id}/parquet` | State of the feed's latest dataset |
| POST | `/v1/operations/gtfs_feeds/{id}/parquet` | Start a build for it |
| GET | `/v1/operations/gtfs_datasets/{id}/parquet` | State of one dataset |
| POST | `/v1/operations/gtfs_datasets/{id}/parquet` | Start a build for it |

`GET` returns **200 for every state**, including `absent`:

```json
{ "status": "absent",    "feed_stable_id": "mdb-1210", "dataset_stable_id": "mdb-1210-202402121801" }
{ "status": "preparing", "phase": "convert", "done": 12, "total": 32, "detail": "stop_times" }
{ "status": "ready",     "base_url": "https://.../parquet", "tables": [{"name": "stops"}] }
{ "status": "failed",    "message": "Conversion ran out of memory" }
```

`absent` means no conversion has been requested yet, which is an ordinary starting
state rather than an error - a **404 means the feed or dataset does not exist**, and a
client has to be able to tell the two apart. `GET` never starts work; `POST` does.

`done` and `total` are **bytes** during the `download` phase and counts otherwise;
`total` is `0` when it is not knowable in advance.
