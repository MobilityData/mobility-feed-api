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

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import (
    GtfsDatasetChangelog,
    Gtfsdataset,
)
from shared.helpers.logger import get_logger, init_logger

init_logger()


@functions_framework.http
def gtfs_change_tracker(request: flask.Request) -> dict:
    """
    HTTP entrypoint for the GTFS change tracker function.

    Expects a JSON body with:
        feed_stable_id                – stable_id of the GTFS feed
        previous_dataset_stable_id    – stable_id of the previous Gtfsdataset
        current_dataset_stable_id     – stable_id of the current Gtfsdataset
    """
    payload = request.get_json(silent=True) or {}
    feed_stable_id = payload.get("feed_stable_id")
    previous_dataset_stable_id = payload.get("previous_dataset_stable_id")
    current_dataset_stable_id = payload.get("current_dataset_stable_id")

    if not (
        feed_stable_id and previous_dataset_stable_id and current_dataset_stable_id
    ):
        return {
            "status": "error",
            "error": "feed_stable_id, previous_dataset_stable_id, and current_dataset_stable_id are required.",
        }

    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return {
            "status": "error",
            "error": "DATASETS_BUCKET_NAME environment variable is not set.",
        }

    bucket_mount = os.getenv("DATASETS_BUCKET_MOUNT", "/mobilitydata-datasets")
    try:
        tracker = GtfsChangeTracker(
            feed_stable_id=feed_stable_id,
            previous_dataset_stable_id=previous_dataset_stable_id,
            current_dataset_stable_id=current_dataset_stable_id,
            bucket_name=bucket_name,
            bucket_mount=bucket_mount,
        )
        result = tracker.run()
        return {"status": "success", **result}
    except Exception as e:
        logging.exception(
            "Failed to generate changelog for %s -> %s",
            previous_dataset_stable_id,
            current_dataset_stable_id,
        )
        return {
            "status": "error",
            "error": f"Failed to generate changelog: {e}",
        }


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
        previous_dataset_stable_id: str,
        current_dataset_stable_id: str,
        bucket_name: str,
        bucket_mount: str,
    ):
        self.feed_stable_id = feed_stable_id
        self.previous_dataset_stable_id = previous_dataset_stable_id
        self.current_dataset_stable_id = current_dataset_stable_id
        self.bucket_name = bucket_name
        self.bucket_mount = bucket_mount
        self.logger = get_logger(GtfsChangeTracker.__name__, current_dataset_stable_id)

    def run(self) -> dict:
        """Execute the full change-tracking pipeline."""
        prev_dataset_uuid, curr_dataset_uuid, feed_uuid = self._resolve_datasets()

        self.logger.info(
            "Computing diff for feed %s: %s -> %s",
            self.feed_stable_id,
            self.previous_dataset_stable_id,
            self.current_dataset_stable_id,
        )

        prev_dir = self._extracted_dir(
            self.feed_stable_id, self.previous_dataset_stable_id
        )
        curr_dir = self._extracted_dir(
            self.feed_stable_id, self.current_dataset_stable_id
        )

        diff_result = diff_feeds(prev_dir, curr_dir)

        changelog_json = diff_result.model_dump_json(indent=2).encode("utf-8")
        changelog_url = self._upload_changelog(
            changelog_json,
            self.feed_stable_id,
            self.previous_dataset_stable_id,
            self.current_dataset_stable_id,
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
            .filter(Gtfsdataset.stable_id == self.previous_dataset_stable_id)
            .one_or_none()
        )
        if prev_dataset is None:
            raise ValueError(
                f"Previous dataset not found: {self.previous_dataset_stable_id}"
            )

        curr_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.stable_id == self.current_dataset_stable_id)
            .one_or_none()
        )
        if curr_dataset is None:
            raise ValueError(
                f"Current dataset not found: {self.current_dataset_stable_id}"
            )

        if curr_dataset.feed.stable_id != self.feed_stable_id:
            raise ValueError(
                f"Dataset {self.current_dataset_stable_id} does not belong to feed {self.feed_stable_id}."
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
        # TODO: remove this flag and always write to DB once testing is complete
        if os.getenv("CHANGELOG_DB_WRITE_ENABLED", "false").lower() == "true":
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
                        "generated_at": GtfsDatasetChangelog.generated_at.default,
                    },
                )
            )
            db_session.execute(stmt)
            db_session.commit()
            self.logger.info(
                "Saved changelog record for %s -> %s",
                self.previous_dataset_stable_id,
                self.current_dataset_stable_id,
            )
        else:
            self.logger.info(
                "[TEMP] Would upsert gtfs_dataset_changelog: feed_id=%s previous=%s current=%s url=%s summary=%s",
                feed_uuid,
                prev_dataset_uuid,
                curr_dataset_uuid,
                changelog_url,
                diff_summary,
            )
