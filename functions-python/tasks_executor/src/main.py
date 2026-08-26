#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import csv
import io
from typing import Any, Final

import flask
import functions_framework

from shared.helpers.logger import init_logger
from shared.helpers.task_execution.task_execution_tracker import TaskInProgressError
from tasks.data_import.transportdatagouv.import_tdg_feeds import import_tdg_handler
from tasks.data_import.transportdatagouv.update_tdg_redirects import (
    update_tdg_redirects_handler,
)
from tasks.dataset_files.rebuild_missing_dataset_files import (
    rebuild_missing_dataset_files_handler,
)
from tasks.dataset_files.backfill_dataset_hash_md5 import (
    backfill_dataset_hash_md5_handler,
)
from tasks.licenses.license_matcher import match_license_handler
from tasks.missing_bounding_boxes.rebuild_missing_bounding_boxes import (
    rebuild_missing_bounding_boxes_handler,
)
from tasks.refresh_feedsearch_view.refresh_materialized_view import (
    refresh_materialized_view_handler,
)
from tasks.validation_reports.rebuild_missing_validation_reports import (
    rebuild_missing_validation_reports_handler,
)
from tasks.sync_task_run_status import (
    sync_task_run_status_handler,
)
from tasks.get_task_run_status import (
    get_task_run_status_handler,
)
from tasks.visualization_files.rebuild_missing_visualization_files import (
    rebuild_missing_visualization_files_handler,
)
from tasks.geojson.update_geojson_files_precision import (
    update_geojson_files_precision_handler,
)
from tasks.data_import.jbda.import_jbda_feeds import import_jbda_handler
from tasks.data_import.odpt.import_odpt_feeds import import_odpt_handler

from tasks.licenses.populate_licenses import (
    populate_licenses_handler,
)
from tasks.web_revalidation.revalidate_feed import revalidate_feed_handler
from tasks.feed_availability.check_gtfs_feed_availability import (
    check_gtfs_feed_availability_handler,
)
from tasks.users.migrate_firebase_users import migrate_firebase_users_handler
from tasks.users.reconcile_announcements_from_brevo import (
    reconcile_announcements_from_brevo_handler,
)
from tasks.notifications.dispatch_batch import notifications_dispatch_batch_handler
from tasks.notifications.dispatch_worker import (
    notifications_dispatch_handler,
)
from tasks.notifications.dispatch_monitor import (
    notifications_dispatch_monitor_handler,
)
from tasks.changelog.backfill_changelog import backfill_changelog_handler
from tasks.seal_of_reliability.backfill.backfill_seal_of_reliability import (
    backfill_seal_of_reliability_handler,
)

from tasks.seal_of_reliability.update_seal_of_reliability import (
    update_seal_of_reliability_handler,
)
from tasks.sitemap.generate_sitemap import generate_mobilitydatabase_sitemap_handler
from tasks.seal_of_reliability.orchestrator.seal_orchestrator import (
    seal_orchestrator_handler,
)
from tasks.seal_of_reliability.orchestrator.seal_orchestrator_worker import (
    seal_orchestrator_worker_handler,
)
from tasks.seal_of_reliability.orchestrator.seal_orchestrator_monitor import (
    seal_orchestrator_monitor_handler,
)

init_logger()
LIST_COMMAND: Final[str] = "list"
tasks = {
    "list_tasks": {
        "description": "List all available tasks.",
        "handler": lambda payload: (
            {
                "tasks": [
                    {"name": task_name, "description": task_info["description"]}
                    for task_name, task_info in tasks.items()
                ]
            }
        ),
    },
    "rebuild_missing_validation_reports": {
        "description": "Rebuilds missing validation reports for GTFS datasets.",
        "handler": rebuild_missing_validation_reports_handler,
    },
    "get_task_run_status": {
        "description": (
            "Read-only snapshot of a task_run tracked by TaskExecutionTracker. "
            "Returns current DB state (triggered/completed/failed/pending counts) "
            "without triggering any GCP Workflows polling or status transitions. "
            "Required: task_name, run_id."
        ),
        "handler": get_task_run_status_handler,
    },
    "sync_task_run_status": {
        "description": (
            "Generic self-scheduling monitor for any task_run. "
            "Polls GCP Workflows for triggered entries, updates statuses, "
            "marks the task_run completed when all done, and re-schedules "
            "itself every 10 minutes until complete. "
            "Required: task_name, run_id."
        ),
        "handler": sync_task_run_status_handler,
    },
    "rebuild_missing_bounding_boxes": {
        "description": "Rebuilds missing bounding boxes for GTFS datasets that contain valid stops.txt files.",
        "handler": rebuild_missing_bounding_boxes_handler,
    },
    "refresh_materialized_view": {
        "description": "Refreshes the materialized view.",
        "handler": refresh_materialized_view_handler,
    },
    "rebuild_missing_dataset_files": {
        "description": "Rebuilds missing dataset files for GTFS datasets.",
        "handler": rebuild_missing_dataset_files_handler,
    },
    "backfill_dataset_hash_md5": {
        "description": (
            "Backfills the MD5 hash for existing GTFS datasets by reading it from GCS blob metadata. "
            "Parameters: dry_run (default true), only_latest (default true), "
            "only_missing_hashes (default true), limit (default 10)."
        ),
        "handler": backfill_dataset_hash_md5_handler,
    },
    "update_geojson_files": {
        "description": "Iterate over bucket looking for {feed_stable_id}/geolocation.geojson and update precision.",
        "handler": update_geojson_files_precision_handler,
    },
    "rebuild_missing_visualization_files": {
        "description": "Rebuilds missing visualization files for GTFS datasets.",
        "handler": rebuild_missing_visualization_files_handler,
    },
    "jbda_import": {
        "description": "Imports JBDA data into the system.",
        "handler": import_jbda_handler,
    },
    "odpt_import": {
        "description": "Imports ODPT data into the system.",
        "handler": import_odpt_handler,
    },
    "populate_licenses": {
        "description": "Populates licenses, license-rules and license-tags "
        "in the database from a predefined JSON source.",
        "handler": populate_licenses_handler,
    },
    "match_licenses": {
        "description": "Match licenses with feeds.",
        "handler": match_license_handler,
    },
    "tdg_import": {
        "description": "Imports TDG data into the system.",
        "handler": import_tdg_handler,
    },
    "mdb_to_tdg_redirect": {
        "description": "Redirect duplicate MDB feeds to TDG imported feeds.",
        "handler": update_tdg_redirects_handler,
    },
    "revalidate_feed": {
        "description": "Revalidate the website cache for a specific feed detail page.",
        "handler": revalidate_feed_handler,
    },
    "check_gtfs_feed_availability": {
        "description": (
            "Check availability of active/published GTFS feeds via HTTP HEAD requests "
            "and store results in gtfs_feed_availability_check. "
        ),
        "handler": check_gtfs_feed_availability_handler,
    },
    "migrate_firebase_users": {
        "description": (
            "Insert-only migration of Firebase Auth users into users.app_user "
            "(the only field updated on an existing row is brevo_synced_at). "
            "Reads profile fields (fullName, organization, registrationCompletionTime) "
            "from Datastore kind 'web_api_users' (queried by uid property). "
            "Uses Brevo as the source of truth for is_registered_to_receive_api_announcements. "
            "Ensures each user has an api.announcements notification_subscription and "
            "writes MDB_SUBSCRIPTION_ID back onto the Brevo contact, tracking that "
            "write via app_user.brevo_synced_at (idempotent: users already synced "
            "are skipped). "
            "Parameters: dry_run (default true), limit (default null), "
            "user_ids (default null), only_not_migrated (default true)."
        ),
        "handler": migrate_firebase_users_handler,
    },
    "reconcile_announcements_from_brevo": {
        "description": (
            "Reconcile Brevo-originated unsubscribes back into the users DB for "
            "api.announcements (reverse of the API/migration forward opt-in path). "
            "For every user with an ACTIVE api.announcements subscription, reads the "
            "Brevo contact status; when Brevo reports UNSUBSCRIBED (global "
            "email_blacklisted or list-level unsubscribe), sets "
            "app_user.is_registered_to_receive_api_announcements=false and "
            "deactivates the subscription (active=false). Turn-OFF only: never "
            "re-subscribes or adds anyone on SUBSCRIBED/NOT_FOUND. Idempotent. "
            "Parameters: dry_run (default true), limit (default null)."
        ),
        "handler": reconcile_announcements_from_brevo_handler,
    },
    "notifications_dispatch_batch": {
        "description": (
            "Cloud Tasks producer for notification dispatch. Triggered by Cloud "
            "Scheduler. Resolves cadences, finds active subscriptions (users DB), "
            "registers a run in TaskExecutionTracker (feeds DB), and enqueues one "
            "'notifications_dispatch' worker task per subscription plus "
            "a single 'notifications_dispatch_monitor' barrier task. "
            "Parameters: "
            "cadence ('daily'|'weekly'|'all'|'scheduled', default 'scheduled'), "
            "weekly_weekday (0=Mon..6=Sun, default 0, only used with cadence='scheduled'), "
            "dry_run (default false), "
            "status_filter ('new'|'failed'|'all', default 'new'), "
            "user_ids (list of user IDs for manual trigger, default []), "
            "force (bypass cadence when user_ids set, default false), "
            "max_retries (default 5), stale_claim_seconds (default 1800), "
            "monitor_delay_seconds (default 60), deadline_seconds (default 21600)."
        ),
        "handler": notifications_dispatch_batch_handler,
    },
    "notifications_dispatch": {
        "description": (
            "Cloud Tasks worker: process one subscription's pending notification "
            "events. Lock-free claim-then-send into notification_log (no duplicate "
            "emails under concurrency), sends via Brevo, and marks the run entry "
            "completed/failed in TaskExecutionTracker. "
            "Parameters: subscription_id (required), run_id (required), "
            "status_filter, max_retries, stale_claim_seconds."
        ),
        "handler": notifications_dispatch_handler,
    },
    "notifications_dispatch_monitor": {
        "description": (
            "Cloud Tasks barrier/monitor: polls TaskExecutionTracker until every "
            "worker for a run has reported (or the run deadline passes), then emits "
            "exactly one admin.event_summary with aggregated delivery stats. Returns "
            "503 (native Cloud Tasks retry) while workers are still in flight. "
            "Parameters: run_id (required)."
        ),
        "handler": notifications_dispatch_monitor_handler,
    },
    "generate_mobilitydatabase_sitemap": {
        "description": (
            "Generate the mobilitydatabase.org sitemap from published, "
            "non-deprecated feeds and upload it to GCS as sitemap.xml. "
            "One URL per feed at /feeds/{data_type}/{stable_id}, priority 0.8, "
            "no changefreq. lastmod: GTFS uses its latest dataset download; "
            "GTFS-RT the latest of its created_at and its related scheduled "
            "feeds' latest dataset; GBFS its newest GBFS version date — all "
            "floored at 2026-03-05. "
            "Parameters: dry_run (default true), "
            "bucket_name (default 'mobilitydatabase-sitemap-{ENVIRONMENT}'), "
            "object_name (default 'sitemap.xml'), "
            "base_url (default 'https://mobilitydatabase.org'), "
            "make_public (default true), include_xml (default false)."
        ),
        "handler": generate_mobilitydatabase_sitemap_handler,
    },
    "backfill_changelog": {
        "description": (
            "Backfills gtfs_dataset_changelog records from existing dataset history by "
            "dispatching Cloud Tasks to the gtfs-datasets-comparer function for each "
            "consecutive (base, new) dataset pair that has no changelog row yet. "
            "Parameters: dry_run (default true), limit (default 100), "
            "datasets_per_feed (default 3), stable_feed_ids (default null), "
            "feeds_not_updated_days (default null)."
        ),
        "handler": backfill_changelog_handler,
    },
    "update_seal_of_reliability": {
        "description": (
            "Evaluates the implemented Seal of Reliability criteria for the requested "
            "GTFS feeds and updates seal_criterion and feed_reliability_seal. "
            "Reads the source tables and never modifies them. "
            "Parameters: stable_feed_ids (required, non-empty; the feeds to evaluate), "
            "dry_run (default true), limit (default null), criteria (default null "
            "meaning every implemented criterion; a partial set skips the has_seal "
            "roll-up), batch_size (default 200), now (ISO timestamp, default current "
            "UTC time)."
        ),
        "handler": update_seal_of_reliability_handler,
    },
    "backfill_seal_of_reliability": {
        "description": (
            "Establishes a starting Seal of Reliability state for feeds that have none "
            "(issue #1763), by cold-starting each feed 12 months back and replaying the "
            "nightly evaluation forward one day at a time to end_date, writing only the "
            "final day. The intermediate days are held in memory and discarded unless "
            "snapshot_mode says otherwise. "
            "Parameters: stable_feed_ids (required, non-empty), start_date (ISO date, "
            "default end_date minus days_back; clamped up to each feed's created_at), "
            "end_date (ISO date, default yesterday UTC), days_back (default 365), "
            "dry_run (default true), limit (default null), criteria (default null "
            "meaning every implemented criterion), batch_size (default 200), "
            "only_missing (default true; skips feeds that already have seal state), "
            "snapshot_mode (final|all|none, default final), resume_from_snapshot "
            "(default false; the #1803 hook), max_reported_feeds (default 50)."
        ),
        "handler": backfill_seal_of_reliability_handler,
    },
    "seal_orchestrator": {
        "description": (
            "Cloud Tasks producer for the nightly Seal of Reliability run across the "
            "whole catalog. Resolves every seal-eligible GTFS feed, chunks it into "
            "batches, registers a run in TaskExecutionTracker (feeds DB), and enqueues "
            "one 'seal_orchestrator_worker' task per batch plus a single "
            "'seal_orchestrator_monitor' barrier task. "
            "Parameters: dry_run (default true), batch_size (default 250), criteria "
            "(default null meaning every implemented criterion), now (ISO timestamp, "
            "default current UTC time), limit (cap total eligible feeds, default "
            "null), stable_feed_ids (restrict eligibility to these ids, default "
            "null), deadline_seconds (default 3600), monitor_delay_seconds "
            "(default 60)."
        ),
        "handler": seal_orchestrator_handler,
    },
    "seal_orchestrator_worker": {
        "description": (
            "Cloud Tasks worker: evaluate one batch's worth of feeds for the seal "
            "orchestrator run and report completion/failure to TaskExecutionTracker. "
            "Parameters: run_id (required), batch_id (required), stable_feed_ids "
            "(required, non-empty), criteria (default null), now (default null)."
        ),
        "handler": seal_orchestrator_worker_handler,
    },
    "seal_orchestrator_monitor": {
        "description": (
            "Cloud Tasks barrier/monitor: polls TaskExecutionTracker until every "
            "batch of a seal orchestrator run has reported, or the run's "
            "deadline_seconds passes, then aggregates each batch's report and marks "
            "the run completed (every batch succeeded) or failed (any batch failed, "
            "or the deadline was reached with batches still unaccounted for). "
            "Parameters: run_id (required)."
        ),
        "handler": seal_orchestrator_monitor_handler,
    },
}


def get_task(request: flask.Request):
    """Verify if the task is valid and has a handler.
    Args:
        request (flask.Request): The incoming request.
    Returns:
        str: The task name.
    Raises:
        ValueError: If the task is invalid or has no handler.
    """
    request_json = request.get_json(silent=True)
    if not request_json:
        raise ValueError("Invalid JSON request")
    if not request_json.get("task"):
        raise ValueError("Task not provided")
    task = request_json.get("task")
    if task not in tasks:
        raise ValueError("Task not supported: %s", task)
    accept_content_type = request.headers.get("Accept", "application/json")
    payload = request_json.get("payload")
    if not payload:
        payload = {}
    return task, payload, accept_content_type


def _to_csv(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data.keys()))
        writer.writeheader()
        writer.writerow(data)
        return output.getvalue()
    if isinstance(data, list):
        if not data:
            return ""
        # Collect all keys to handle varying dict shapes
        keys = set()
        for row in data:
            if isinstance(row, dict):
                keys.update(row.keys())
        fieldnames = sorted(keys)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            if isinstance(row, dict):
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        return output.getvalue()
    # Fallback: stringify
    return str(data)


@functions_framework.http
def tasks_executor(request: flask.Request) -> flask.Response:
    task: Any
    payload: Any
    try:
        task, payload, accept_content_type = get_task(request)
    except ValueError as error:
        return flask.make_response(flask.jsonify({"error": str(error)}), 400)
    # Execute task
    handler = tasks[task]["handler"]
    try:
        result = handler(payload=payload)
        if accept_content_type == "text/csv":
            csv_body = _to_csv(result)
            response = flask.make_response(csv_body, 200)
            response.headers["Content-Type"] = "text/csv; charset=utf-8"
            response.headers["Content-Disposition"] = (
                "attachment; filename=task_result.csv"
            )
            return response

        # Default JSON response
        return flask.make_response(flask.jsonify(result), 200)
    except TaskInProgressError as error:
        # Signal Cloud Tasks to retry — the run is not yet complete
        return flask.make_response(
            flask.jsonify({"status": "in_progress", "detail": str(error)}), 503
        )
    except Exception as error:
        return flask.make_response(flask.jsonify({"error": str(error)}), 500)
