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
import tempfile

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
        feed_id             – DB id of the GTFS feed (FK to gtfsfeed.id)
        previous_dataset_id – DB id of the previous Gtfsdataset
        current_dataset_id  – DB id of the current Gtfsdataset
    """
    payload = request.get_json(silent=True) or {}
    feed_id = payload.get("feed_id")
    previous_dataset_id = payload.get("previous_dataset_id")
    current_dataset_id = payload.get("current_dataset_id")

    if not (feed_id and previous_dataset_id and current_dataset_id):
        return {
            "status": "error",
            "error": "feed_id, previous_dataset_id, and current_dataset_id are required.",
        }

    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    if not bucket_name:
        return {
            "status": "error",
            "error": "DATASETS_BUCKET_NAME environment variable is not set.",
        }

    try:
        tracker = GtfsChangeTracker(
            feed_id=feed_id,
            previous_dataset_id=previous_dataset_id,
            current_dataset_id=current_dataset_id,
            bucket_name=bucket_name,
        )
        result = tracker.run()
        return {"status": "success", **result}
    except Exception as e:
        logging.exception(
            "Failed to generate changelog for %s -> %s",
            previous_dataset_id,
            current_dataset_id,
        )
        return {
            "status": "error",
            "error": f"Failed to generate changelog: {e}",
        }


class GtfsChangeTracker:
    """
    Orchestrates GTFS change tracking between two consecutive datasets.

    Steps:
    1. Resolve both datasets and the feed stable_id from the database.
    2. Download the pre-extracted GTFS files from GCS for both datasets
       (<feed_stable_id>/<dataset_stable_id>/extracted/).
    3. Compute a structured diff using gtfs-diff-engine.
    4. Upload the changelog JSON to GCS at two paths (shared changelogs index
       and per-dataset location).
    5. Upsert a row in gtfs_dataset_changelog.
    """

    def __init__(
        self,
        feed_id: str,
        previous_dataset_id: str,
        current_dataset_id: str,
        bucket_name: str,
    ):
        self.feed_id = feed_id
        self.previous_dataset_id = previous_dataset_id
        self.current_dataset_id = current_dataset_id
        self.bucket_name = bucket_name
        self.logger = get_logger(GtfsChangeTracker.__name__, current_dataset_id)

    def run(self) -> dict:
        """Execute the full change-tracking pipeline."""
        prev_dataset, curr_dataset, feed_stable_id = self._resolve_datasets()

        self.logger.info(
            "Computing diff for feed %s: %s -> %s",
            feed_stable_id,
            prev_dataset.stable_id,
            curr_dataset.stable_id,
        )

        with tempfile.TemporaryDirectory(prefix="gtfs_change_tracker_") as tmpdir:
            prev_dir = os.path.join(tmpdir, "previous")
            curr_dir = os.path.join(tmpdir, "current")
            os.makedirs(prev_dir)
            os.makedirs(curr_dir)

            self._download_extracted_files(
                feed_stable_id, prev_dataset.stable_id, prev_dir
            )
            self._download_extracted_files(
                feed_stable_id, curr_dataset.stable_id, curr_dir
            )

            diff_result = diff_feeds(prev_dir, curr_dir)

        changelog_json = diff_result.model_dump_json(indent=2).encode("utf-8")
        changelog_url = self._upload_changelog(
            changelog_json,
            feed_stable_id,
            prev_dataset.stable_id,
            curr_dataset.stable_id,
        )

        diff_summary = diff_result.summary.model_dump()
        self._save_changelog_record(
            changelog_url=changelog_url, diff_summary=diff_summary
        )

        self.logger.info("Changelog stored at %s", changelog_url)
        return {
            "message": "Changelog generated successfully.",
            "changelog_url": changelog_url,
        }

    @with_db_session
    def _resolve_datasets(self, db_session: Session = None) -> tuple:
        """
        Load both Gtfsdataset rows and return (previous_dataset, current_dataset, feed_stable_id).
        """
        prev_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.id == self.previous_dataset_id)
            .one_or_none()
        )
        if prev_dataset is None:
            raise ValueError(f"Previous dataset not found: {self.previous_dataset_id}")

        curr_dataset = (
            db_session.query(Gtfsdataset)
            .filter(Gtfsdataset.id == self.current_dataset_id)
            .one_or_none()
        )
        if curr_dataset is None:
            raise ValueError(f"Current dataset not found: {self.current_dataset_id}")

        if not prev_dataset.stable_id:
            raise ValueError(
                f"Previous dataset {self.previous_dataset_id} has no stable_id."
            )
        if not curr_dataset.stable_id:
            raise ValueError(
                f"Current dataset {self.current_dataset_id} has no stable_id."
            )

        feed_stable_id = curr_dataset.feed.stable_id
        if not feed_stable_id:
            raise ValueError(f"Feed {self.feed_id} has no stable_id.")

        # Detach from session before returning so objects can be used outside the session
        db_session.expunge(prev_dataset)
        db_session.expunge(curr_dataset)

        return prev_dataset, curr_dataset, feed_stable_id

    def _download_extracted_files(
        self, feed_stable_id: str, dataset_stable_id: str, dest_dir: str
    ) -> None:
        """
        Download all pre-extracted GTFS files from GCS to a local directory.

        batch_process_dataset uploads each file from the dataset ZIP individually to:
            <feed_stable_id>/<dataset_stable_id>/extracted/<filename>

        This avoids re-downloading and re-unzipping the full archive.
        """
        prefix = f"{feed_stable_id}/{dataset_stable_id}/extracted/"
        bucket = storage.Client().bucket(self.bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        if not blobs:
            raise ValueError(
                f"No extracted files found in GCS at gs://{self.bucket_name}/{prefix}"
            )
        for blob in blobs:
            filename = os.path.basename(blob.name)
            if not filename:
                continue
            local_path = os.path.join(dest_dir, filename)
            blob.download_to_filename(local_path)
            self.logger.debug("Downloaded gs://%s/%s", self.bucket_name, blob.name)

    def _upload_changelog(
        self,
        json_bytes: bytes,
        feed_stable_id: str,
        prev_stable_id: str,
        curr_stable_id: str,
    ) -> str:
        """
        Upload the changelog JSON to GCS at two paths.

        Paths:
          - <feed_stable_id>/changelogs/<prev_stable_id>_<curr_stable_id>_changelog.json
          - <feed_stable_id>/<curr_stable_id>/<curr_stable_id>_<prev_stable_id>_changelog.json

        Returns the primary (changelogs/) URL.
        """
        primary_blob_path = f"{feed_stable_id}/changelogs/{prev_stable_id}_{curr_stable_id}_changelog.json"
        secondary_blob_path = f"{feed_stable_id}/{curr_stable_id}/{curr_stable_id}_{prev_stable_id}_changelog.json"

        bucket = storage.Client().bucket(self.bucket_name)
        primary_url = None

        for blob_path in (primary_blob_path, secondary_blob_path):
            blob = bucket.blob(blob_path)
            blob.upload_from_string(json_bytes, content_type="application/json")
            self.logger.info(
                "Uploaded changelog to gs://%s/%s", self.bucket_name, blob_path
            )
            if blob_path == primary_blob_path:
                primary_url = (
                    f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"
                )

        return primary_url

    @with_db_session
    def _save_changelog_record(
        self,
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
                feed_id=self.feed_id,
                previous_dataset_id=self.previous_dataset_id,
                current_dataset_id=self.current_dataset_id,
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
            self.previous_dataset_id,
            self.current_dataset_id,
        )
