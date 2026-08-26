/* Captured fixtures for the continuous coverage mock.
 *
 * COVERAGE is a real response of
 *   GET /v1/gtfs_feeds/mdb-9001/continuous_coverage?limit=100
 * against a seeded local database.
 *
 * The seed is built to exercise every clause of the probation rule:
 *
 *   a gap is introduced -> IF AND ONLY IF the next upload has no gap -> probation starts on that
 *   upload's download date -> it runs 180 days -> another gap inside that window restarts the clock.
 *
 * The producer publishes about every 30 days, each dataset covering 120 days of service starting
 * 20 days after we fetch it, so consecutive datasets share 91 days. A coverage gap happens when the
 * producer goes quiet: no new dataset arrives until the old one's service has run out, so the next
 * one starts later than the previous ended.
 *
 *   2024-01-30 .. 2024-10-26   ten healthy datasets, 91 days shared each time
 *   2025-03-14                 18 days uncovered -> seal withdrawn
 *   2025-08-07                 25 days uncovered -> seal withdrawn again. The next upload after
 *                              the first gap was NOT clean, so no probation started at this point.
 *                              This is the "if and only if" clause
 *   2025-09-06                 clean -> probation A starts, running to 2026-03-05
 *   2025-10-06                 clean, serving probation A
 *   2026-02-25                 21 days uncovered, INSIDE probation A -> the clock is broken
 *   2026-03-27                 clean -> probation B starts, running to 2026-09-23
 *   2026-04-26 .. 2026-07-25   clean, serving probation B, still open on the fixed today
 *
 * A gap is never repaired retroactively, which is why the gap rows are still in the chain after the
 * feed recovers. Pulling a later window back over the hole would leave a fresh hole on its far side,
 * and `overlap_days` - which compares only the older window's end to the newer one's start - would
 * report a large overlap for it.
 *
 * CRITERION is the `fresh_continuous` entry of GET /v1/gtfs_feeds/{id}/reliability. The mock does
 * not need it to place the probation bands - it derives those from the rule above - but it does
 * check its own answer against the `probation_ends_at` served here.
 */

const COVERAGE = {
  "feed_id": "mdb-9001",
  "total": 20,
  "offset": 0,
  "limit": 100,
  "items": [
    {
      "dataset_id": "mdb-9001-202607250029",
      "is_latest": true,
      "downloaded_at": "2026-07-25T00:29:00Z",
      "coverage_window": {
        "start": "2026-08-14",
        "end": "2026-12-12",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-08-14",
        "end": "2026-12-12",
        "days": 121
      },
      "feed_info_window": {
        "start": "2026-08-14",
        "end": "2026-12-12",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202606250029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202606250029",
      "is_latest": false,
      "downloaded_at": "2026-06-25T00:29:00Z",
      "coverage_window": {
        "start": "2026-07-15",
        "end": "2026-11-12",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-07-15",
        "end": "2026-11-12",
        "days": 121
      },
      "feed_info_window": {
        "start": "2026-07-15",
        "end": "2026-11-12",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202605260029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202605260029",
      "is_latest": false,
      "downloaded_at": "2026-05-26T00:29:00Z",
      "coverage_window": {
        "start": "2026-06-15",
        "end": "2026-10-13",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-06-15",
        "end": "2026-10-13",
        "days": 121
      },
      "feed_info_window": null,
      "feed_info_matches": null,
      "previous_dataset_id": "mdb-9001-202604260029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": false
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202604260029",
      "is_latest": false,
      "downloaded_at": "2026-04-26T00:29:00Z",
      "coverage_window": {
        "start": "2026-05-16",
        "end": "2026-09-13",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-05-16",
        "end": "2026-09-13",
        "days": 121
      },
      "feed_info_window": {
        "start": "2026-05-16",
        "end": "2026-09-13",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202603270029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202603270029",
      "is_latest": false,
      "downloaded_at": "2026-03-27T00:29:00Z",
      "coverage_window": {
        "start": "2026-04-16",
        "end": "2026-08-14",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-04-16",
        "end": "2026-08-14",
        "days": 121
      },
      "feed_info_window": {
        "start": "2026-04-16",
        "end": "2026-08-14",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202602250029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202602250029",
      "is_latest": false,
      "downloaded_at": "2026-02-25T00:29:00Z",
      "coverage_window": {
        "start": "2026-03-17",
        "end": "2026-07-15",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2026-03-17",
        "end": "2026-07-15",
        "days": 121
      },
      "feed_info_window": {
        "start": "2026-03-17",
        "end": "2026-07-15",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202510060029",
      "overlap_days": null,
      "gap_days": 21,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202510060029",
      "is_latest": false,
      "downloaded_at": "2025-10-06T00:29:00Z",
      "coverage_window": {
        "start": "2025-10-26",
        "end": "2026-02-23",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2025-10-26",
        "end": "2026-02-23",
        "days": 121
      },
      "feed_info_window": {
        "start": "2025-10-26",
        "end": "2026-02-23",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202509060029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202509060029",
      "is_latest": false,
      "downloaded_at": "2025-09-06T00:29:00Z",
      "coverage_window": {
        "start": "2025-09-26",
        "end": "2026-01-24",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2025-09-26",
        "end": "2026-01-24",
        "days": 121
      },
      "feed_info_window": {
        "start": "2025-09-26",
        "end": "2026-01-24",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202508070029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202508070029",
      "is_latest": false,
      "downloaded_at": "2025-08-07T00:29:00Z",
      "coverage_window": {
        "start": "2025-08-27",
        "end": "2025-12-25",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2025-08-27",
        "end": "2025-12-25",
        "days": 121
      },
      "feed_info_window": {
        "start": "2025-08-27",
        "end": "2025-12-25",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202503140029",
      "overlap_days": null,
      "gap_days": 25,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202503140029",
      "is_latest": false,
      "downloaded_at": "2025-03-14T00:29:00Z",
      "coverage_window": {
        "start": "2025-04-03",
        "end": "2025-08-01",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2025-04-03",
        "end": "2025-08-01",
        "days": 121
      },
      "feed_info_window": {
        "start": "2025-04-03",
        "end": "2025-08-01",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202410260029",
      "overlap_days": null,
      "gap_days": 18,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202410260029",
      "is_latest": false,
      "downloaded_at": "2024-10-26T00:29:00Z",
      "coverage_window": {
        "start": "2024-11-15",
        "end": "2025-03-15",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-11-15",
        "end": "2025-03-15",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-11-15",
        "end": "2025-03-15",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202409260029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202409260029",
      "is_latest": false,
      "downloaded_at": "2024-09-26T00:29:00Z",
      "coverage_window": {
        "start": "2024-10-16",
        "end": "2025-02-13",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-10-16",
        "end": "2025-02-13",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-10-16",
        "end": "2025-02-13",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202408270029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202408270029",
      "is_latest": false,
      "downloaded_at": "2024-08-27T00:29:00Z",
      "coverage_window": {
        "start": "2024-09-16",
        "end": "2025-01-14",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-09-16",
        "end": "2025-01-14",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-09-22",
        "end": "2025-01-20",
        "days": 121
      },
      "feed_info_matches": false,
      "previous_dataset_id": "mdb-9001-202407280029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202407280029",
      "is_latest": false,
      "downloaded_at": "2024-07-28T00:29:00Z",
      "coverage_window": {
        "start": "2024-08-17",
        "end": "2024-12-15",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-08-17",
        "end": "2024-12-15",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-08-17",
        "end": "2024-12-15",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202406280029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202406280029",
      "is_latest": false,
      "downloaded_at": "2024-06-28T00:29:00Z",
      "coverage_window": {
        "start": "2024-07-18",
        "end": "2024-11-15",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-07-18",
        "end": "2024-11-15",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-07-18",
        "end": "2024-11-15",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202405290029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202405290029",
      "is_latest": false,
      "downloaded_at": "2024-05-29T00:29:00Z",
      "coverage_window": {
        "start": "2024-06-18",
        "end": "2024-10-16",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-06-18",
        "end": "2024-10-16",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-06-18",
        "end": "2024-10-16",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202404290029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202404290029",
      "is_latest": false,
      "downloaded_at": "2024-04-29T00:29:00Z",
      "coverage_window": {
        "start": "2024-05-19",
        "end": "2024-09-16",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-05-19",
        "end": "2024-09-16",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-05-19",
        "end": "2024-09-16",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202403300029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202403300029",
      "is_latest": false,
      "downloaded_at": "2024-03-30T00:29:00Z",
      "coverage_window": {
        "start": "2024-04-19",
        "end": "2024-08-17",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-04-19",
        "end": "2024-08-17",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-04-19",
        "end": "2024-08-17",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202402290029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202402290029",
      "is_latest": false,
      "downloaded_at": "2024-02-29T00:29:00Z",
      "coverage_window": {
        "start": "2024-03-20",
        "end": "2024-07-18",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-03-20",
        "end": "2024-07-18",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-03-20",
        "end": "2024-07-18",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": "mdb-9001-202401300029",
      "overlap_days": 91,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    },
    {
      "dataset_id": "mdb-9001-202401300029",
      "is_latest": false,
      "downloaded_at": "2024-01-30T00:29:00Z",
      "coverage_window": {
        "start": "2024-02-19",
        "end": "2024-06-18",
        "days": 121
      },
      "coverage_window_source": "service_dates",
      "within_max_coverage_window": true,
      "service_window": {
        "start": "2024-02-19",
        "end": "2024-06-18",
        "days": 121
      },
      "feed_info_window": {
        "start": "2024-02-19",
        "end": "2024-06-18",
        "days": 121
      },
      "feed_info_matches": true,
      "previous_dataset_id": null,
      "overlap_days": null,
      "gap_days": null,
      "files": [
        {
          "name": "feed_info.txt",
          "present": true
        },
        {
          "name": "calendar.txt",
          "present": true
        },
        {
          "name": "calendar_dates.txt",
          "present": true
        }
      ]
    }
  ]
};

const CRITERION = {
  "criterion": "fresh_continuous",
  "status": "pass",
  "in_grace_period": false,
  "grace_period_ends_at": null,
  "on_probation": true,
  "probation_ends_at": "2026-09-23T00:00:00Z",
  "evaluated_at": "2026-08-24T03:00:00Z",
  "first_failure_at": "2025-03-14T03:00:00Z",
  "last_failure_at": "2026-02-25T03:00:00Z"
};

// shared.common.seal_criteria.PROBATION_PERIOD
const PROBATION_DAYS = 180;

// A fixed "today" so the mock renders the same way on any day it is opened.
const MOCK_TODAY = "2026-08-24";
