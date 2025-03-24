import json
import logging
import os
from typing import Optional

import requests
from google.cloud import storage

from shared.helpers.bq_schema.schema import (
    json_schema_map,
    load_json_schema,
    filter_json_by_schema,
)
from locations import get_feed_location

# Environment variables
project_id = os.getenv("PROJECT_ID")
bucket_name = os.getenv("BUCKET_NAME")
data_type = os.getenv("DATA_TYPE")


class ValidationReportConverter:
    """Converts a validation report to NDJSON format."""

    def __init__(
        self,
        stable_id: str,
        dataset_id: str,
        report_id: str,
        validation_report_url: str,
    ):
        try:
            self.validation_report = requests.get(validation_report_url).json()
        except Exception as e:
            logging.error(f"Failed to download the validation report: {e}")
            self.validation_report = None
        self.stable_id = stable_id
        self.dataset_id = dataset_id
        self.report_id = report_id
        self.nd_json_path_prefix = "ndjson"
        self.locations = get_feed_location(stable_id)
        self.json_schema_path = os.path.join(
            os.path.dirname(__file__),
            "shared/helpers/bq_schema",
            json_schema_map.get(data_type, "gtfs"),
        )
        self.json_schema = load_json_schema(self.json_schema_path)

    @staticmethod
    def get_converter(data_type_value: Optional[str] = None) -> type:
        """Returns the appropriate converter based on the data type."""
        data_type_value = data_type_value if data_type_value else data_type
        if data_type_value == "gtfs":
            return GTFSValidationReportConverter
        elif data_type_value == "gbfs":
            return GBFSValidationReportConverter
        raise ValueError(f"Invalid data type: {data_type}")

    def _process(self) -> None:
        """Class-specific processing logic for augmenting the validation report."""
        pass  # The logic needs to be implemented in the child class

    def process(self) -> None:
        """Processes the validation report and uploads it to Cloud Storage."""
        ndjson_blob_name = (
            f"{self.nd_json_path_prefix}/"
            f"{self.stable_id}/"
            f"{self.dataset_id}/"
            f"{self.report_id}.ndjson"
        )
        if self.validation_report is None:
            logging.error(f"Validation report is empty for {self.report_id}.")
            return

        # Add feedId to the JSON data
        self.validation_report["feedId"] = self.stable_id
        self.validation_report["locations"] = [
            {
                "country": location.country,
                "countryCode": location.country_code,
                "subdivisionName": location.subdivision_name,
                "municipality": location.municipality,
            }
            for location in self.locations
        ]

        self._process()
        json_data = filter_json_by_schema(self.json_schema, self.validation_report)

        # Convert the JSON data to a single NDJSON record (one line)
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.get_bucket(bucket_name)
        ndjson_content = json.dumps(json_data, separators=(",", ":"))
        ndjson_blob = bucket.blob(ndjson_blob_name)
        ndjson_blob.upload_from_string(ndjson_content + "\n")
        logging.info(f"Processed and uploaded {ndjson_blob_name}")


class GTFSValidationReportConverter(ValidationReportConverter):
    """Converts a GTFS validation report to NDJSON format."""

    def __init__(
        self,
        stable_id: str,
        dataset_id: str,
        report_id: str,
        validation_report_url: str,
    ):
        super().__init__(stable_id, dataset_id, report_id, validation_report_url)

    def _process(self):
        self.validation_report["datasetId"] = self.dataset_id
        # Extract validatedAt and add it to the same level
        validated_at = self.validation_report.get("summary", {}).get(
            "validatedAt", None
        )
        self.validation_report["validatedAt"] = validated_at
        # Convert sampleNotices to JSON strings
        for notice in self.validation_report.get("notices", []):
            if "sampleNotices" in notice:
                notice["sampleNotices"] = json.dumps(
                    notice["sampleNotices"], separators=(",", ":")
                )


class GBFSValidationReportConverter(ValidationReportConverter):
    """Converts a GBFS validation report to NDJSON format."""

    def __init__(self, stable_id, dataset_id, report_id, validation_report_url):
        super().__init__(stable_id, dataset_id, report_id, validation_report_url)

    def _process(self):
        self.validation_report["snapshotId"] = self.dataset_id
