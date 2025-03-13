import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from google.cloud import storage
from shared.database_gen.sqlacodegen_models import (
    Gbfssnapshot,
    Gbfsvalidationreport,
    Gbfsnotice,
)
from sqlalchemy.orm import Session
from shared.dataset_service.main import Status
from shared.helpers.database import with_db_session


class GBFSValidator:
    def __init__(self, stable_id: str):
        self.validation_timestamp = datetime.now().strftime("%Y%m%d%H%M")
        self.stable_id = stable_id
        self.snapshot_id = f"{self.stable_id}-{self.validation_timestamp}"
        self.VALIDATOR_URL = os.getenv(
            "VALIDATOR_URL",
            "https://gbfs-validator.mobilitydata.org/.netlify/functions/validator-summary",
        )
        self.hosted_url = None  # The hosted URL of the new gbfs.json

    def create_gbfs_json_with_bucket_paths(
        self, bucket: storage.Bucket, gbfs_data: Dict[str, Any]
    ) -> None:
        """
        Create a new gbfs.json with paths pointing to Cloud Storage and upload it.
        @param bucket: The Cloud Storage bucket.
        @param gbfs_data: The GBFS data.
        @return: The public URL of the new gbfs.json.
        """
        new_gbfs_data = gbfs_data.copy()

        for feed_key, feed in new_gbfs_data["data"].items():
            if isinstance(feed, list):
                for feed_info in feed:
                    old_url = feed_info["url"]
                    blob_name = (
                        f"{self.stable_id}/{self.snapshot_id}/{feed_info['name']}.json"
                    )
                    new_url = upload_gbfs_file_to_bucket(bucket, old_url, blob_name)
                    if new_url is not None:
                        feed_info["url"] = new_url
            elif isinstance(feed["feeds"], dict):
                for feed_language, feed_info in feed["feeds"].items():
                    old_url = feed_info["url"]
                    blob_name = f"{self.stable_id}/{self.snapshot_id}/{feed_info['name']}_{feed_language}.json"
                    new_url = upload_gbfs_file_to_bucket(bucket, old_url, blob_name)
                    if new_url is not None:
                        feed_info["url"] = new_url
            elif isinstance(feed["feeds"], list):
                for feed_info in feed["feeds"]:
                    old_url = feed_info["url"]
                    blob_name = (
                        f"{self.stable_id}/{self.snapshot_id}/{feed_info['name']}.json"
                    )
                    new_url = upload_gbfs_file_to_bucket(bucket, old_url, blob_name)
                    if new_url is not None:
                        feed_info["url"] = new_url
            else:
                logging.warning(f"Unexpected format in feed: {feed_key}")

        # Save the new gbfs.json in the bucket
        new_gbfs_blob = bucket.blob(f"{self.stable_id}/{self.snapshot_id}/gbfs.json")
        new_gbfs_blob.upload_from_string(
            json.dumps(new_gbfs_data), content_type="application/json"
        )
        new_gbfs_blob.make_public()
        self.hosted_url = new_gbfs_blob.public_url

    def create_snapshot(self, feed_id: str) -> Gbfssnapshot:
        """Create a new Gbfssnapshot object."""
        snapshot_id = str(uuid.uuid4())
        snapshot = Gbfssnapshot(
            id=snapshot_id,
            stable_id=self.snapshot_id,
            feed_id=feed_id,
            downloaded_at=datetime.now(),
            hosted_url=self.hosted_url,
        )
        return snapshot

    def validate_gbfs_feed(self, bucket: storage.Bucket) -> Dict[str, Any]:
        """Validate the GBFS feed and store the report in Cloud Storage."""
        json_payload = {"url": self.hosted_url}
        response = requests.post(self.VALIDATOR_URL, json=json_payload)
        response.raise_for_status()

        json_report_summary = response.json()
        report_summary_blob = bucket.blob(
            f"{self.stable_id}/{self.snapshot_id}/report_summary.json"
        )
        report_summary_blob.upload_from_string(
            json.dumps(json_report_summary), content_type="application/json"
        )
        report_summary_blob.make_public()

        return {
            "report_summary_url": report_summary_blob.public_url,
            "json_report_summary": json_report_summary,
        }


@with_db_session(echo=False)
def save_snapshot_and_report(
    snapshot: Gbfssnapshot, validation_result: Dict[str, Any], db_session: Session
):
    """Save the snapshot and validation report to the database."""
    validation_report = Gbfsvalidationreport(
        id=str(uuid.uuid4()),
        gbfs_snapshot_id=snapshot.id,
        validated_at=datetime.now(),
        report_summary_url=validation_result["report_summary_url"],
    )
    json_report_summary = validation_result["json_report_summary"]
    validation_report.gbfsnotices = [
        Gbfsnotice(
            keyword=error["keyword"],
            message=error["message"],
            schema_path=error["schemaPath"],
            gbfs_file=file_summary["file"],
            validation_report_id=validation_report.id,
            count=error["count"],
        )
        for file_summary in json_report_summary.get("filesSummary", [])
        if file_summary["hasErrors"]
        for error in file_summary["groupedErrors"]
    ]
    snapshot.gbfsvalidationreports = [validation_report]
    db_session.add(snapshot)
    db_session.commit()


def fetch_gbfs_files(url: str) -> Dict[str, Any]:
    """Fetch the GBFS files from the autodiscovery URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def save_trace_with_error(trace, error, trace_service):
    """Helper function to save trace with an error."""
    trace.error_message = error
    trace.status = Status.FAILED
    trace_service.save(trace)


def upload_gbfs_file_to_bucket(
    bucket: storage.Bucket, file_url: str, destination_blob_name: str
) -> Optional[str]:
    """Upload a GBFS file to a Cloud Storage bucket."""
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(response.content)
        blob.make_public()
        logging.info(f"Uploaded {destination_blob_name} to {bucket.name}.")
        return blob.public_url
    except requests.exceptions.RequestException as error:
        logging.error(
            f"Error uploading {destination_blob_name} with access url {file_url}: {error}"
        )
        return None
