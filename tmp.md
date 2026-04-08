# GTFS diff changelog schema (v2.0.0)

## Design goals

1. **Single file output**: one JSON document contains summary + capped details
3. **Capped for performance**: max 50 row changes per file, full counts always preserved in summary
4. **Explicit scope**: files outside the supported scope are reported in `metadata.unsupported_files` rather than silently ignored
5. **Spec-aligned**: compatible with the existing [GTFS Diff specification](https://github.com/MobilityData/gtfs_diff/blob/main/specification.md)

## Supported scope (v2.0)

This version of the schema only supports files defined in the official [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/).
Any unsupported file in the GTFS archive (including non-`.txt` files like `readme.pdf`, `locations.geojson`, etc.) is **not diffed**. Instead, it's reported in `metadata.unsupported_files`.

## Key design decision: per-file cap

A GTFS diff can contain tens of thousands of row changes. Loading all of them into a UI upfront is wasteful — users rarely inspect every modified row. Instead:

- The **summary** always reports true counts
- **Each file caps its row changes at 50**, in first-encountered order
- When truncated, the file reports how many were omitted via `truncated` metadata

## Schema overview

```
GtfsDiffOutput
├── metadata
│   ├── schema_version
│   ├── generated_at
│   ├── row_changes_cap_per_file
│   ├── base_feed               # url, downloaded_at
│   ├── new_feed                # url, downloaded_at
│   └── unsupported_files[]     # files skipped by the diff engine
├── summary                     # true aggregate counts (drives file tree sidebar)
│   └── files[]                 # per-file: name + true counts by action
└── file_diffs[]                # one entry per changed supported file
    ├── file_name
    ├── file_action             # null | "added" | "deleted"
    ├── columns_added[]
    ├── columns_deleted[]
    ├── row_changes
    │   ├── primary_key[]
    │   ├── columns[]           # union of base + new
    │   ├── added[]             # capped
    │   ├── deleted[]           # capped
    │   └── modified[]          # capped
    └── truncated               # cap metadata (omitted counts)
```

## Capping behavior

The cap applies to the **combined** count of `added + deleted + modified` per file, in first-encountered order. A file with 30 added, 15 deleted, and 200 modified rows (245 total) hits the cap at 50 and reports `omitted_count: 195`.


File-level changes (`file_action`) and column-level changes (`columns_added`, `columns_deleted`) are **not capped**.

## Unsupported files behavior

When the diff engine encounters a file that is not in the supported scope:

1. It is **not** added to `file_diffs[]`
2. It is **not** counted in `summary.total_changes` or `summary.files_*`
3. It is listed in `metadata.unsupported_files[]` with:
   - `file_name`: the file as it appears in the archive
   - `present_in`: `base`, `new`, or `both`

This keeps the diff itself clean and focused on what was actually compared, while still surfacing skipped files so the UI can show a "files not diffed" section.

## Example output

```json
{
  "metadata": {
    "schema_version": "2.0.0",
    "generated_at": "2026-04-08T14:30:00Z",
    "row_changes_cap_per_file": 50,
    "base_feed": {
      "url": "https://example.com/gtfs-2026-03.zip",
      "downloaded_at": "2026-03-15T10:00:00Z"
    },
    "new_feed": {
      "url": "https://example.com/gtfs-2026-04.zip",
      "downloaded_at": "2026-04-01T10:00:00Z"
    },
    "unsupported_files": [
      {
        "file_name": "readme.pdf",
        "present_in": "base"
      },
      {
        "file_name": "custom_notes.txt",
        "present_in": "both"
      }
    ]
  },

  "summary": {
    "total_changes": 1213,
    "files_added": 1,
    "files_deleted": 0,
    "files_modified": 2,
    "files": [
      { "file_name": "shapes.txt", "status": "added", "rows_added": 30 },
      {
        "file_name": "stop_times.txt",
        "status": "modified",
        "rows_added": 120,
        "rows_deleted": 45,
        "rows_modified": 1048
      },
      {
        "file_name": "stops.txt",
        "status": "modified",
        "columns_deleted": 1,
        "rows_added": 2,
        "rows_deleted": 1,
        "rows_modified": 5
      }
    ]
  },

  "file_diffs": [
    {
      "file_name": "shapes.txt",
      "file_action": "added",
      "columns_added": [],
      "columns_deleted": []
    },
    {
      "file_name": "stop_times.txt",
      "file_action": null,
      "columns_added": [],
      "columns_deleted": [],
      "row_changes": {
        "primary_key": ["trip_id", "stop_sequence"],
        "columns": ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        "added": [
          {
            "identifier": { "trip_id": "T100", "stop_sequence": "1" },
            "values": {
              "trip_id": "T100",
              "arrival_time": "08:00:00",
              "departure_time": "08:00:30",
              "stop_id": "A",
              "stop_sequence": "1"
            }
          }
        ],
        "deleted": [],
        "modified": [
          {
            "identifier": { "trip_id": "T042", "stop_sequence": "3" },
            "field_changes": [
              { "field": "arrival_time", "old_value": "09:15:00", "new_value": "09:16:00" }
            ]
          }
        ]
      },
      "truncated": {
        "is_truncated": true,
        "omitted_count": 1163
      }
    },
    {
      "file_name": "stops.txt",
      "file_action": null,
      "columns_added": [],
      "columns_deleted": ["internal_id"],
      "row_changes": {
        "primary_key": ["stop_id"],
        "columns": ["stop_id", "stop_name", "stop_lat", "stop_lon", "zone_id"],
        "added": [
          {
            "identifier": { "stop_id": "C" },
            "values": {
              "stop_id": "C",
              "stop_name": "Central Park",
              "stop_lat": "45.5017",
              "stop_lon": "-73.5673",
              "zone_id": "1"
            }
          }
        ],
        "deleted": [
          {
            "identifier": { "stop_id": "A" },
            "values": {
              "stop_id": "A",
              "stop_name": "Town center",
              "stop_lat": "45.5000",
              "stop_lon": "-73.5500",
              "zone_id": "1"
            }
          }
        ],
        "modified": [
          {
            "identifier": { "stop_id": "B" },
            "field_changes": [
              { "field": "stop_name", "old_value": "", "new_value": "Train station" },
              { "field": "stop_lat", "old_value": "45.4900", "new_value": "45.4912" }
            ]
          }
        ]
      }
    }
  ]
}
```

Notice:
- `stop_times.txt` has 1213 row changes total (summary) but only 2 shown in `file_diffs` with `omitted_count: 1163`
- `stops.txt` has 8 row changes total, all fit under the cap, so no `truncated` field
- `shapes.txt` is a file-level action, no `row_changes` needed
- `readme.pdf`, `fare_products.txt`, and `custom_notes.txt` are reported in `unsupported_files` and do not appear in `file_diffs` or `summary`

## How this maps to a GitHub-style diff UI

### File tree sidebar (uses `summary`)
```
GTFS Diff: 1213 changes across 3 files

+ shapes.txt           (+30 rows)
~ stop_times.txt       (+120  -45  ~1048 rows)    [showing 50 of 1213]
~ stops.txt            (+2  -1  ~5 rows, -1 col)

Not diffed (3)
  readme.pdf
  fare_products.txt
  custom_notes.txt
```

The "Not diffed" section is rendered from `metadata.unsupported_files`.

### Expanded file view (uses `file_diffs[].row_changes`)

When the user expands `stop_times.txt`, the UI renders the 50 included rows and shows a banner:

> Showing 50 of 1213 row changes. 1163 more changes were omitted.

## Schema versioning

- Schema version tracked in `metadata.schema_version`
- Schema definition lives in `docs/schemas/`
- `CHANGELOG.md` tracks all schema changes
- Breaking changes bump major, additive changes bump minor, docs bump patch

### v2.0 scope

- Only GTFS Schedule `.txt` files from the official reference are diffed
- GTFS extensions (GTFS-Fares v2, GTFS-Flex, GTFS-Pathways extensions, etc.) are reported as unsupported
- Non-`.txt` files in the archive (e.g. `readme.pdf`) are reported as unsupported
- Support for additional files and extensions can be added in future minor versions (v2.1+) without breaking this schema