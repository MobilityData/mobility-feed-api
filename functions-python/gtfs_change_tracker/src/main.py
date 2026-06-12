#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# This module provides the GtfsChangeTracker Cloud Function. It orchestrates change tracking
# between two consecutive GTFS datasets: reads the pre-extracted GTFS files from GCS (uploaded
# by batch_process_dataset at <feed_stable_id>/<dataset_stable_id>/extracted/), computes a
# structured diff using gtfs-diff-engine, uploads the changelog JSON to GCS, and persists the
# record in the gtfs_dataset_changelog database table.
import logging
import os

import flask
import functions_framework
from google.cloud import storage
from gtfs_diff.engine import diff_feeds
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from shared.common.gcp_memory_utils import limit_gcp_memory
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    GtfsDatasetChangelog,
    Gtfsdataset,
)
from shared.helpers.logger import get_logger, init_logger
from shared.helpers.runtime_metrics import track_metrics

init_logger()
limit_gcp_memory(os.getenv("GTFS_DIFF_DUCKDB_TMPDIR", "/tmp/in-memory"))


@functions_framework.http
def gtfs_change_tracker(request: flask.Request) -> dict:
    """
    HTTP entrypoint for the GTFS change tracker function.

    Expects a JSON body with:
        feed_stable_id            – stable_id of the GTFS feed
        base_dataset_stable_id    – stable_id of the base (previous) Gtfsdataset
        new_dataset_stable_id     – stable_id of the new (current) Gtfsdataset
        disallow_overwrite        – (optional, default false) skip if changelog already exists
        dry_run                   – (optional, default false) compute diff but skip GCS upload and DB write

    Always returns HTTP 200 — errors are reported in the response body.
    This prevents GCP from retrying failures: we cannot distinguish transient from
    permanent errors (e.g. a DB blip vs the DB being down), so retrying would only
    waste resources. The idempotency check in run() makes explicit reruns safe.
    """
    payload = request.get_json(silent=True) or {}
    feed_stable_id = payload.get("feed_stable_id")
    base_dataset_stable_id = payload.get("base_dataset_stable_id")
    new_dataset_stable_id = payload.get("new_dataset_stable_id")
    disallow_overwrite = bool(payload.get("disallow_overwrite", False))
    dry_run = bool(payload.get("dry_run", False))

    if not (feed_stable_id and base_dataset_stable_id and new_dataset_stable_id):
        return flask.make_response(
            {
                "status": "error",
                "error": "feed_stable_id, base_dataset_stable_id, and new_dataset_stable_id are required.",
            },
            200,
        )

    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return flask.make_response(
            {
                "status": "error",
                "error": "DATASETS_BUCKET_NAME environment variable is not set.",
            },
            200,
        )

    bucket_mount = os.getenv("DATASETS_BUCKET_MOUNT", "/tmp/mobilitydata-datasets")
    try:
        tracker = GtfsChangeTracker(
            feed_stable_id=feed_stable_id,
            base_dataset_stable_id=base_dataset_stable_id,
            new_dataset_stable_id=new_dataset_stable_id,
            bucket_name=bucket_name,
            bucket_mount=bucket_mount,
            disallow_overwrite=disallow_overwrite,
            dry_run=dry_run,
        )
        result = tracker.run()
        return flask.make_response({"status": "success", **result}, 200)
    except Exception as e:
        # We cannot reliably distinguish transient from permanent errors, so we always
        # return HTTP 200 to suppress GCP retries. If a specific exception type is
        # identified as safely retriable in the future, catch it here and return 500.
        logging.exception(
            "Failed to generate changelog for feed=%s base=%s new=%s",
            feed_stable_id,
            base_dataset_stable_id,
            new_dataset_stable_id,
        )
        return flask.make_response(
            {
                "status": "error",
                "error": f"Failed to generate changelog: {e}",
                "payload": payload,
            },
            200,
        )


class GtfsChangeTracker:
    """
    Orchestrates GTFS change tracking between two consecutive datasets.

    Steps:
    1. Resolve both datasets from the database using their stable_ids.
    2. Locate the pre-extracted GTFS files on the mounted GCS bucket filesystem
       (<bucket_mount>/<feed_stable_id>/<dataset_stable_id>/extracted/).
    3. Compute a structured diff using gtfs-diff-engine.
    4. Upload the changelog JSON to GCS.
    5. Upsert a row in gtfs_dataset_changelog.
    """

    def __init__(
        self,
        feed_stable_id: str,
        base_dataset_stable_id: str,
        new_dataset_stable_id: str,
        bucket_name: str,
        bucket_mount: str,
        disallow_overwrite: bool = False,
        dry_run: bool = False,
    ):
        self.feed_stable_id = feed_stable_id
        self.base_dataset_stable_id = base_dataset_stable_id
        self.new_dataset_stable_id = new_dataset_stable_id
        self.bucket_name = bucket_name
        self.bucket_mount = bucket_mount
        self.disallow_overwrite = disallow_overwrite
        self.dry_run = dry_run
        self.logger = get_logger(GtfsChangeTracker.__name__, new_dataset_stable_id)

    @track_metrics(metrics=("time", "memory", "cpu"))
    def run(self) -> dict:
        """Execute the full change-tracking pipeline."""
        changelog_blob_path = (
            f"{self.feed_stable_id}/{self.new_dataset_stable_id}/"
            f"{self.new_dataset_stable_id}_{self.base_dataset_stable_id}_changelog.json"
        )
        blob = storage.Client().bucket(self.bucket_name).blob(changelog_blob_path)

        # Idempotency: skip if changelog already exists and disallow_overwrite is set.
        if self.disallow_overwrite and blob.exists():
            changelog_url = f"https://storage.googleapis.com/{self.bucket_name}/{changelog_blob_path}"
            self.logger.info("Changelog already exists, skipping: %s", changelog_url)
            return {
                "message": "Changelog already exists.",
                "changelog_url": changelog_url,
            }

        prev_dataset_uuid, curr_dataset_uuid, feed_uuid = self._resolve_datasets()

        self.logger.info(
            "Computing diff for feed %s: %s -> %s",
            self.feed_stable_id,
            self.base_dataset_stable_id,
            self.new_dataset_stable_id,
        )

        prev_dir = self._extracted_dir(self.feed_stable_id, self.base_dataset_stable_id)
        curr_dir = self._extracted_dir(self.feed_stable_id, self.new_dataset_stable_id)

        diff_result = diff_feeds(prev_dir, curr_dir)

        if self.dry_run:
            self.logger.info("Dry run — skipping GCS upload and DB write.")
            return {
                "message": "Dry run completed. Diff computed but not persisted.",
                "summary": diff_result.summary.model_dump(),
            }

        changelog_json = diff_result.model_dump_json(indent=2).encode("utf-8")
        changelog_url = self._upload_changelog(
            changelog_json,
            self.feed_stable_id,
            self.base_dataset_stable_id,
            self.new_dataset_stable_id,
        )

        diff_summary = diff_result.summary.model_dump()
        self._save_changelog_record(
            feed_uuid=feed_uuid,
            prev_dataset_uuid=prev_dataset_uuid,
            curr_dataset_uuid=curr_dataset_uuid,
            changelog_url=changelog_url,
            diff_summary=diff_summary,
        )

        self.logger.info("Changelog stored at %s", changelog_url)
        return {
            "message": "Changelog generated successfully.",
            "changelog_url": changelog_url,
        }

    @with_db_session
    def _resolve_datasets(self, db_session: Session = None) -> tuple:
        """
        Validate both datasets exist and belong to the given feed.
        Returns (prev_dataset_uuid, curr_dataset_uuid, feed_uuid) as plain strings.
        """
        prev_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == self.base_dataset_stable_id)
            .one_or_none()
        )
        if prev_dataset is None:
            raise ValueError(
                f"Previous dataset not found: {self.base_dataset_stable_id}"
            )
        if prev_dataset.feed.stable_id != self.feed_stable_id:
            raise ValueError(
                f"Dataset {self.base_dataset_stable_id} does not belong to feed {self.feed_stable_id}."
            )

        curr_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == self.new_dataset_stable_id)
            .one_or_none()
        )
        if curr_dataset is None:
            raise ValueError(f"Current dataset not found: {self.new_dataset_stable_id}")

        if curr_dataset.feed.stable_id != self.feed_stable_id:
            raise ValueError(
                f"Dataset {self.new_dataset_stable_id} does not belong to feed {self.feed_stable_id}."
            )

        return prev_dataset.id, curr_dataset.id, curr_dataset.feed.id

    def _extracted_dir(self, feed_stable_id: str, dataset_stable_id: str) -> str:
        """
        Return the path to the pre-extracted GTFS files on the mounted bucket filesystem.

        batch_process_dataset uploads each file to:
            <feed_stable_id>/<dataset_stable_id>/extracted/<filename>
        which appears on the mount at:
            <bucket_mount>/<feed_stable_id>/<dataset_stable_id>/extracted/
        """
        path = os.path.join(
            self.bucket_mount, feed_stable_id, dataset_stable_id, "extracted"
        )
        if not os.path.isdir(path):
            raise ValueError(f"Extracted files not found on mounted bucket at {path}")
        self.logger.debug("Using extracted dir from mounted bucket: %s", path)
        return path

    def _upload_changelog(
        self,
        json_bytes: bytes,
        feed_stable_id: str,
        prev_dataset_id: str,
        curr_dataset_id: str,
    ) -> str:
        """
        Upload the changelog JSON to GCS at:
          <feed_stable_id>/<curr_dataset_id>/<curr_dataset_id>_<prev_dataset_id>_changelog.json

        Returns the GCS public URL.
        """
        blob_path = f"{feed_stable_id}/{curr_dataset_id}/{curr_dataset_id}_{prev_dataset_id}_changelog.json"
        bucket = storage.Client().bucket(self.bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json_bytes, content_type="application/json")
        blob.make_public()
        self.logger.info(
            "Uploaded changelog to gs://%s/%s", self.bucket_name, blob_path
        )
        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"

    @with_db_session
    def _save_changelog_record(
        self,
        feed_uuid: str,
        prev_dataset_uuid: str,
        curr_dataset_uuid: str,
        changelog_url: str,
        diff_summary: dict,
        db_session: Session = None,
    ) -> None:
        """
        Upsert a row into gtfs_dataset_changelog.
        The UNIQUE constraint on (previous_dataset_id, current_dataset_id) ensures idempotency.
        """
        stmt = (
            insert(GtfsDatasetChangelog)
            .values(
                feed_id=feed_uuid,
                previous_dataset_id=prev_dataset_uuid,
                current_dataset_id=curr_dataset_uuid,
                changelog_url=changelog_url,
                diff_summary=diff_summary,
            )
            .on_conflict_do_update(
                constraint="gtfs_dataset_changelog_previous_current_key",
                set_={
                    "changelog_url": changelog_url,
                    "diff_summary": diff_summary,
                    "generated_at": func.now(),
                },
            )
        )
        db_session.execute(stmt)
        db_session.commit()
        self.logger.info(
            "Saved changelog record for %s -> %s",
            self.base_dataset_stable_id,
            self.new_dataset_stable_id,
        )
