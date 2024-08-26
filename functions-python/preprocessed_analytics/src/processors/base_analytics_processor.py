import logging
import os
from typing import List, Dict, Tuple

import pandas as pd
from google.cloud import storage
from sqlalchemy.orm import Query

from database_gen.sqlacodegen_models import (
    Gbfsfeed,
    Gbfssnapshot,
    Gtfsfeed,
    Gtfsdataset,
)
from helpers.database import start_db_session


class BaseAnalyticsProcessor:
    def __init__(self, run_date):
        self.run_date = run_date
        self.session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
        self.processed_feeds = set()
        self.data = []
        self.feed_metrics_data = []
        self.notices_metrics_data = []
        self.storage_client = storage.Client()
        self.analytics_bucket = self.storage_client.bucket(
            os.getenv("ANALYTICS_BUCKET")
        )

    def get_latest_data(self) -> Query:
        raise NotImplementedError("Subclasses should implement this method.")

    def process_feed_data(
        self,
        feed: Gtfsfeed | Gbfsfeed,
        dataset_or_snapshot: Gtfsdataset | Gbfssnapshot,
        translations: Dict,
    ) -> None:
        raise NotImplementedError("Subclasses should implement this method.")

    def save(self) -> None:
        raise NotImplementedError("Subclasses should implement this method.")

    @staticmethod
    def append_new_data_if_not_exists(
        old_data: List[Dict], new_data: List[Dict], keys: List[str], list_to_append=None
    ) -> List[Dict]:
        if list_to_append is None:
            list_to_append = ["computed_on"]
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
                if list_to_append:
                    for entry in matching_entries:
                        for key in list_to_append:
                            entry[key].extend(new_entry[key])
        return old_data

    def _load_json(self, file_name: str) -> Tuple[List[Dict], storage.Blob]:
        # Read the JSON file from the specified GCS bucket
        blob = self.analytics_bucket.blob(file_name)

        if blob.exists():
            json_data = blob.download_as_text()
            return (
                pd.read_json(json_data, convert_dates=["computed_on"]).to_dict(
                    orient="records"
                ),
                blob,
            )

        return [], blob

    @staticmethod
    def _save_blob(blob: storage.Blob, data: List[Dict]) -> None:
        # Convert the data to JSON format
        json_data = pd.DataFrame(data).to_json(orient="records", date_format="iso")

        # Save the JSON file to the specified GCS bucket
        blob.upload_from_string(json_data, content_type="application/json")
        blob.make_public()
        logging.info(f"{blob.name} saved to bucket")

    def _save_json(self, file_name: str, data: List[Dict]) -> None:
        # Save the JSON file to the specified GCS bucket
        blob = self.analytics_bucket.blob(file_name)
        self._save_blob(blob, data)

    def save_metrics(self, metrics_file_data: Dict[str, Dict]) -> None:
        for file_name, data in metrics_file_data.items():
            old_data, blob = self._load_json(file_name)
            updated_data = self.append_new_data_if_not_exists(
                old_data, data["new_data"], data["keys"], data["list_to_append"]
            )
            self._save_blob(blob, updated_data)

    def save_analytics(self) -> None:
        file_name = f"analytics_{self.run_date.strftime('%Y_%m')}.json"
        self._save_json(file_name, self.data)
        self.save()
        logging.info(f"Analytics saved to bucket as {file_name}")

    def run(self) -> None:
        for (
            feed,
            dataset_or_snapshot,
            translation_fields,
        ) in self._get_data_with_translations():
            self.process_feed_data(feed, dataset_or_snapshot, translation_fields)

        self.session.close()
        self.save_analytics()
        self.update_analytics_files()
        logging.info(f"Finished running analytics for date: {self.run_date}")

    def _get_data_with_translations(self):
        query = self.get_latest_data()
        all_results = query.all()
        logging.info(f"Loaded {len(all_results)} feeds to process")
        try:
            location_translations = [
                self._extract_translation_fields(result[2:]) for result in all_results
            ]
            logging.info("Location translations loaded")
            location_translations_dict = {
                translation["location_id"]: translation
                for translation in location_translations
                if translation["location_id"] is not None
            }
        except IndexError:
            location_translations_dict = {}
        unique_feeds = {result[0].stable_id: result for result in all_results}
        logging.info(f"Nb of unique feeds loaded: {len(unique_feeds)}")
        return [(result[0], result[1], location_translations_dict) for result in unique_feeds.values()]

    @staticmethod
    def _extract_translation_fields(translation_data):
        keys = [
            "location_id",
            "country_code",
            "country",
            "subdivision_name",
            "municipality",
            "country_translation",
            "subdivision_name_translation",
            "municipality_translation",
        ]
        try:
            return dict(zip(keys, translation_data))
        except Exception as e:
            logging.error(f"Error extracting translation fields: {e}")
            return dict(zip(keys, [None] * len(keys)))

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
            logging.error(f"Error updating analytics files: {e}")
