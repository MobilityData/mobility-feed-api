# GTFS File Data Extractor

HTTP Cloud Function that extracts structured data from a single GTFS file and
persists it to the database. It is enqueued as a Cloud Task by
`batch_process_dataset` once a dataset has been processed (see
`batch_process_dataset/src/pipeline_tasks.py`).

## How it works

The task payload identifies one GTFS file:

```json
{
  "stable_id": "<feed stable id>",
  "dataset_id": "<dataset stable id>",
  "file_name": "feed_info.txt",
  "file_url": "<hosted_url of the GTFS file>"
}
```

Extracted data is stored **once per distinct file content** and shared: one
`feedinfo` row per `feed_info.txt` content hash, referenced by every dataset whose
`feed_info.txt` has that hash (`gtfsdataset.feed_info_id` -> `feedinfo.id`, so one
`feedinfo` to many datasets). A feed that republishes the same `feed_info.txt`
every day therefore has one row, not one per dataset.

`processor.py` looks up the matching extractor in `extractors/registry.py`, then
resolves the data for that dataset in the cheapest way available:

1. **The dataset is already linked** to extracted data -> nothing to do.
2. **The file content has already been extracted** (a row exists for its
   `gtfsfile.hash`) -> link the dataset to that row, without downloading
   anything. This is what gives a dataset whose file did not change its
   reference to the data.
3. **Otherwise** -> download the file, extract it into a new row keyed by the
   content hash, and link the dataset. This covers both a changed file and a
   file that never changed but was never extracted before (for example a dataset
   processed before this function existed).

Because every dataset needs its own reference, `batch_process_dataset` enqueues a
task for every extractable file present in a dataset, changed or not; step 2 is
what keeps the unchanged case cheap.

Extraction requires a known `gtfsfile.hash`: without it the data could not be
matched back to the file content, and a row per dataset is exactly what this
layout avoids. Such a task fails and is reported rather than silently writing an
unshareable row.

The function always responds with HTTP 200, reporting failures in the body, so
that Cloud Tasks does not retry errors that can never succeed (a malformed file,
a deleted dataset). Reruns are safe: every path above is idempotent.

## Adding a new file extractor

1. Implement a `FileDataExtractor` subclass under `src/extractors/`, including
   `has_data` and `link_existing_data` so the sharing path above works for it.
2. Register it in `src/extractors/registry.py`.
3. Add its `file_name` to `EXTRACTABLE_FILES` in
   `batch_process_dataset/src/pipeline_tasks.py` so the producer enqueues it.

Currently registered: `feed_info.txt` -> `FeedInfoExtractor` (writes the
`feedinfo` table).
