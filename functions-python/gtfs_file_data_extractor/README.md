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

`processor.py` downloads the file, looks up the matching extractor in
`extractors/registry.py`, and lets it write to the database.

## Adding a new file extractor

1. Implement a `FileDataExtractor` subclass under `src/extractors/`.
2. Register it in `src/extractors/registry.py`.
3. Add its `file_name` to `EXTRACTABLE_FILES` in
   `batch_process_dataset/src/pipeline_tasks.py` so the producer enqueues it.

Currently registered: `feed_info.txt` -> `FeedInfoExtractor` (writes the
`feedinfo` table).
