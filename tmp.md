# GTFS diff changelog schema (v2.0.0)

## Design goals

2. **Single file output**: one JSON document contains summary + capped details
3. **Capped for performance**: max 50 row changes per file, full counts always preserved in summary
4. **Spec-aligned**: compatible with the existing [GTFS Diff specification](https://github.com/MobilityData/gtfs_diff/blob/main/specification.md)

## Key design decision: per-file cap

A GTFS diff can contain tens of thousands of row changes. Loading all of them into a UI upfront is wasteful — users rarely inspect every modified row. Instead:

- The **summary** always reports true counts
- **Each file caps its row changes at 50**, in first-encountered order
- When truncated, the file reports how many were omitted via `truncated` metadata

## Schema overview

```
GtfsDiffOutput
├── metadata              # versioning, provenance, row cap config
├── summary               # true aggregate counts (drives file tree sidebar)
│   └── files[]           # per-file: name + true counts by action
└── file_diffs[]          # one entry per changed file
    ├── file_name
    ├── file_action        # null | "added" | "deleted"
    ├── columns_added[]
    ├── columns_deleted[]
    ├── row_changes
    │   ├── primary_key[]
    │   ├── columns[]
    │   ├── added[]        # capped
    │   ├── deleted[]      # capped
    │   └── modified[]     # capped
    └── truncated          # cap metadata (omitted counts)
```

## Full JSON schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "GtfsDiffOutput",
  "description": "Structured diff between two GTFS datasets, designed for UI consumption. Row changes are capped per file for efficient loading.",
  "type": "object",
  "required": ["metadata", "summary", "file_diffs"],
  "properties": {

    "metadata": {
      "type": "object",
      "required": ["schema_version", "generated_at", "row_changes_cap_per_file"],
      "properties": {
        "schema_version": {
          "type": "string",
          "description": "Semantic version of this schema (major.minor.patch).",
          "example": "1.0.0"
        },
        "generated_at": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 timestamp when this diff was generated."
        },
        "row_changes_cap_per_file": {
          "type": "integer",
          "description": "Maximum number of row changes included per file (added + deleted + modified combined). Defaults to 50. Full counts are always available in summary.",
          "default": 50,
          "minimum": 1
        },
        "base_feed": {
          "type": "object",
          "description": "Provenance of the 'before' dataset.",
          "properties": {
            "feed_id": { "type": "string" },
            "url": { "type": "string", "format": "uri" },
            "downloaded_at": { "type": "string", "format": "date-time" },
            "hash": { "type": "string", "description": "SHA-256 of the ZIP." }
          }
        },
        "new_feed": {
          "type": "object",
          "description": "Provenance of the 'after' dataset.",
          "properties": {
            "feed_id": { "type": "string" },
            "url": { "type": "string", "format": "uri" },
            "downloaded_at": { "type": "string", "format": "date-time" },
            "hash": { "type": "string", "description": "SHA-256 of the ZIP." }
          }
        }
      }
    },

    "summary": {
      "type": "object",
      "description": "True aggregate stats (not affected by the per-file cap). Powers the file tree sidebar.",
      "required": ["total_changes", "files"],
      "properties": {
        "total_changes": {
          "type": "integer",
          "description": "True total of atomic changes across all files (file + column + row level)."
        },
        "files_added": { "type": "integer" },
        "files_deleted": { "type": "integer" },
        "files_modified": { "type": "integer" },
        "files": {
          "type": "array",
          "description": "Per-file summary with TRUE counts, sorted by file name. These counts are authoritative.",
          "items": {
            "type": "object",
            "required": ["file_name", "status"],
            "properties": {
              "file_name": { "type": "string" },
              "status": {
                "type": "string",
                "enum": ["added", "deleted", "modified"]
              },
              "columns_added": { "type": "integer", "default": 0 },
              "columns_deleted": { "type": "integer", "default": 0 },
              "rows_added": { "type": "integer", "default": 0 },
              "rows_deleted": { "type": "integer", "default": 0 },
              "rows_modified": { "type": "integer", "default": 0 }
            }
          }
        }
      }
    },

    "file_diffs": {
      "type": "array",
      "description": "Detailed changes grouped by GTFS file. Row changes are capped per file.",
      "items": { "$ref": "#/$defs/FileDiff" }
    }
  },

  "$defs": {

    "FileDiff": {
      "type": "object",
      "required": ["file_name"],
      "properties": {
        "file_name": { "type": "string" },
        "file_action": {
          "type": ["string", "null"],
          "enum": ["added", "deleted", null],
          "description": "Non-null only when the entire file was added or deleted."
        },
        "columns_added": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Never capped."
        },
        "columns_deleted": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Never capped."
        },
        "row_changes": { "$ref": "#/$defs/RowChanges" },
        "truncated": { "$ref": "#/$defs/TruncationInfo" }
      }
    },

    "RowChanges": {
      "type": "object",
      "description": "Row-level changes within a file. The combined size of added + deleted + modified will not exceed metadata.row_changes_cap_per_file.",
      "properties": {
        "primary_key": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Column name(s) used to identify rows. Derived from the GTFS spec."
        },
        "columns": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Ordered list of all columns in this file (union of base + new)."
        },
        "added": {
          "type": "array",
          "description": "Added rows (capped). First-encountered order.",
          "items": { "$ref": "#/$defs/AddedRow" }
        },
        "deleted": {
          "type": "array",
          "description": "Deleted rows (capped). First-encountered order.",
          "items": { "$ref": "#/$defs/DeletedRow" }
        },
        "modified": {
          "type": "array",
          "description": "Modified rows (capped). First-encountered order.",
          "items": { "$ref": "#/$defs/ModifiedRow" }
        }
      }
    },

    "TruncationInfo": {
      "type": "object",
      "description": "Present only when row changes exceeded the cap.",
      "required": ["is_truncated", "omitted_count"],
      "properties": {
        "is_truncated": { "type": "boolean" },
        "omitted_count": {
          "type": "integer",
          "minimum": 0,
          "description": "Number of row changes omitted from this file_diff due to the cap."
        }
      }
    },

    "AddedRow": {
      "type": "object",
      "required": ["identifier", "values"],
      "properties": {
        "identifier": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "values": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      }
    },

    "DeletedRow": {
      "type": "object",
      "required": ["identifier", "values"],
      "properties": {
        "identifier": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "values": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      }
    },

    "ModifiedRow": {
      "type": "object",
      "required": ["identifier", "field_changes"],
      "properties": {
        "identifier": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "field_changes": {
          "type": "array",
          "items": { "$ref": "#/$defs/FieldChange" }
        }
      }
    },

    "FieldChange": {
      "type": "object",
      "required": ["field", "old_value", "new_value"],
      "properties": {
        "field": { "type": "string" },
        "old_value": { "type": ["string", "null"] },
        "new_value": { "type": ["string", "null"] }
      }
    }
  }
}
```

## Capping behavior

The cap applies to the **combined** count of `added + deleted + modified` per file, in first-encountered order. A file with 30 added, 15 deleted, and 200 modified rows (245 total) hits the cap at 50 and reports `omitted_count: 195`.

```python
CAP = metadata["row_changes_cap_per_file"]
included = 0
omitted_count = 0
for change in iterate_row_changes(file):
    if included >= CAP:
        omitted_count += 1
        continue
    include_in_output(change)
    included += 1

if omitted_count > 0:
    file_diff["truncated"] = {
        "is_truncated": True,
        "omitted_count": omitted_count,
    }
```

File-level changes (`file_action`) and column-level changes (`columns_added`, `columns_deleted`) are **never capped** — they're always small and always fully reported.

## Example output

```json
{
  "metadata": {
    "schema_version": "1.0.0",
    "generated_at": "2026-04-08T14:30:00Z",
    "row_changes_cap_per_file": 50,
    "base_feed": {
      "feed_id": "mdb-1934",
      "url": "https://example.com/gtfs-2026-03.zip",
      "downloaded_at": "2026-03-15T10:00:00Z",
      "hash": "sha256:abc123..."
    },
    "new_feed": {
      "feed_id": "mdb-1934",
      "url": "https://example.com/gtfs-2026-04.zip",
      "downloaded_at": "2026-04-01T10:00:00Z",
      "hash": "sha256:def456..."
    }
  },

  "summary": {
    "total_changes": 1247,
    "files_added": 1,
    "files_deleted": 1,
    "files_modified": 2,
    "files": [
      { "file_name": "shapes.txt", "status": "added", "rows_added": 30 },
      { "file_name": "readme.pdf", "status": "deleted" },
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
      "file_name": "readme.pdf",
      "file_action": "deleted",
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
- `shapes.txt` and `readme.pdf` are file-level actions, no `row_changes` needed

## How this maps to a GitHub-style diff UI

### File tree sidebar (uses `summary`)
```
GTFS Diff: 1247 changes across 4 files

+ shapes.txt           (+30 rows)
- readme.pdf           (deleted)
~ stop_times.txt       (+120  -45  ~1048 rows)    [showing 50 of 1213]
~ stops.txt            (+2  -1  ~5 rows, -1 col)
```

The sidebar uses `summary.files[]` counts (true totals). The "showing 50 of 1213" badge comes from comparing summary counts against `truncated.omitted_count`.

### Expanded file view (uses `file_diffs[].row_changes`)

When the user expands `stop_times.txt`, the UI renders the 50 included rows and shows a banner:

> Showing 50 of 1213 row changes. 1163 more changes were omitted.

## Schema versioning

- Schema version tracked in `metadata.schema_version`
- Schema definition lives in `docs/schemas/`
- `CHANGELOG.md` tracks all schema changes
- Breaking changes bump major, additive changes bump minor, docs bump patch