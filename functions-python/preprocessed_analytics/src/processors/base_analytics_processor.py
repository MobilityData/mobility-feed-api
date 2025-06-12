import logging
import os
from typing import List, Dict, Tuple

import json
import pandas as pd
from google.cloud import storage
from sqlalchemy.orm import Query
from sqlalchemy.orm.session import Session
from shared.database_gen.sqlacodegen_models import (
    Gbfsfeed,
    # Gbfssnapshot,
    Gtfsfeed,
    Gtfsdataset,
)
from shared.database.database import with_db_session


class NoFeedDataException(Exception):
    pass


class BaseAnalyticsProcessor:
    def __init__(self, run_date):
        self.run_date = run_date
        self.processed_feeds = set()
        self.data = []
        self.feed_metrics_data = []
        self.notices_metrics_data = []
        self.storage_client = storage.Client()
        self.analytics_bucket = self.storage_client.bucket(
            os.getenv("ANALYTICS_BUCKET")
        )

    def get_latest_data(self, db_session: Session) -> Query:
        raise NotImplementedError("Subclasses should implement this method.")

    def process_feed_data(
        self, feed: Gtfsfeed | Gbfsfeed, dataset_or_snapshot: Gtfsdataset | None
    ) -> None:
        raise NotImplementedError("Subclasses should implement this method.")

    def save(self) -> None:
        raise NotImplementedError("Subclasses should implement this method.")

    def save_summary(self) -> None:
        raise NotImplementedError("Subclasses should implement this method.")

    def _load_json(self, file_name: str) -> Tuple[List[Dict], storage.Blob]:
        # Read the JSON file from the specified GCS bucket
        blob = self.analytics_bucket.blob(file_name)

        if blob.exists():
            json_data = blob.download_as_text()
            try:
                return (
                    pd.read_json(json_data, convert_dates=["computed_on"]).to_dict(
                        orient="records"
                    ),
                    blob,
                )
            except Exception as e:
                logging.warning(
                    "Unable to convert data to DataFrame using Pandas: %s", e
                )
                return json.loads(json_data), blob
        return [], blob

    @staticmethod
    def _save_blob(blob: storage.Blob, data: List[Dict]) -> None:
        try:
            # Convert the data to JSON format
            json_data = pd.DataFrame(data).to_json(orient="records", date_format="iso")
        except Exception as e:
            logging.warning("Unable to convert data to JSON using Pandas: %s", e)
            json_data = json.dumps(data, default=str)

        # Save the JSON file to the specified GCS bucket
        blob.upload_from_string(json_data, content_type="application/json")
        blob.make_public()
        logging.info("%s saved to bucket", blob.name)

    def _save_json(self, file_name: str, data: List[Dict]) -> None:
        # Save the JSON file to the specified GCS bucket
        blob = self.analytics_bucket.blob(file_name)
        self._save_blob(blob, data)

    def aggregate_summary_files(
        self, metrics_file_data: Dict[str, List], merging_keys: Dict[str, List[str]]
    ) -> None:
        blobs = self.analytics_bucket.list_blobs(prefix="summary/summary_")
        for blob in blobs:
            logging.info("Aggregating data from %s", blob.name)
            summary_data, _ = self._load_json(blob.name)
            for key, new_data in summary_data.items():
                if key in metrics_file_data:
                    metrics_file_data[key] = self.append_new_data_if_not_exists(
                        metrics_file_data[key], new_data, merging_keys[key]
                    )
        # Save metrics to the bucket
        for file_name, data in metrics_file_data.items():
            self._save_json(f"{file_name}.json", data)

    @staticmethod
    def append_new_data_if_not_exists(
        old_data: List[Dict], new_data: List[Dict], keys: List[str]
    ) -> List[Dict]:
        for new_entry in new_data:
            exists = any(
                all(new_entry[key] == old_entry[key] for key in keys)
                for old_entry in old_data
            )
            if not exists:
                old_data.append(new_entry)
            else:
                matching_entries = [
                    old_entry
                    for old_entry in old_data
                    if all(new_entry[key] == old_entry[key] for key in keys)
                ]
                list_to_append = [key for key in new_entry if key not in keys]
                if len(list_to_append) > 0:
                    for entry in matching_entries:
                        for key in list_to_append:
                            entry[key].extend(new_entry[key])
        return old_data

    def save_analytics(self) -> None:
        file_name = f"analytics_{self.run_date.strftime('%Y-%m-%d')}.json"
        self._save_json(file_name, self.data)
        self.save()
        logging.info("Analytics saved to bucket as %s", file_name)

    @with_db_session
    def run(self, db_session: Session) -> None:
        for feed, dataset_or_snapshot in self._get_data(db_session):
            self.process_feed_data(feed, dataset_or_snapshot)

        self.save_summary()
        self.save_analytics()
        self.update_analytics_files()
        logging.info("Finished running analytics for date: %s", self.run_date)

    def _get_data(self, db_session: Session):
        query = self.get_latest_data(db_session)
        all_results = query.all()
        if len(all_results) == 0:
            raise NoFeedDataException("No feed data found")
        logging.info("Loaded %s feeds to process", len(all_results))
        unique_feeds = {result[0].stable_id: result for result in all_results}
        logging.info("Nb of unique feeds loaded: %s", len(unique_feeds))
        return [(result[0], result[1]) for result in unique_feeds.values()]

    def update_analytics_files(self) -> None:
        try:
            # List all blobs in the analytics bucket
            blobs = self.analytics_bucket.list_blobs()

            # Initialize a list to store information about each analytics file
            analytics_files_list = []

            for blob in blobs:
                # Only include blobs that match the pattern for monthly analytics files
                if (
                    blob.name.startswith("analytics_")
                    and blob.name.endswith(".json")
                    and blob.name != "analytics_files.json"
                ):
                    created_on = blob.time_created
                    analytics_files_list.append(
                        {
                            "file_name": blob.name,
                            "created_on": created_on,
                        }
                    )

            # Convert the list to a DataFrame
            analytics_files = pd.DataFrame(analytics_files_list)
            logging.info("Analytics files list created.")
            logging.info(analytics_files)

            # Save the DataFrame as analytics_files.json in the bucket
            self._save_json(
                "analytics_files.json", analytics_files.to_dict(orient="records")
            )

            logging.info(
                "analytics_files.json created and saved to bucket successfully."
            )

        except Exception as e:
            logging.error("Error updating analytics files: %s", e)
