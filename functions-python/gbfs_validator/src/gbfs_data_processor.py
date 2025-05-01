import json
import language_tags
import logging
from datetime import datetime
from http import HTTPMethod
from typing import Dict, Any, Optional, List, Tuple
from jsonpath_ng import parse
from google.cloud import tasks_v2
import requests
from requests.exceptions import RequestException
from google.cloud import storage
from sqlalchemy.orm import joinedload
from gbfs_utils import (
    GBFSVersion,
    GBFSEndpoint,
    fetch_gbfs_data,
    BUCKET_NAME,
    VALIDATOR_URL,
)
import os
from shared.database_gen.sqlacodegen_models import (
    Gbfsnotice,
    Gbfsversion,
    Gbfsfeed,
    Gbfsendpoint,
    Gbfsvalidationreport,
    Httpaccesslog,
)
from sqlalchemy.orm import Session
from shared.database.database import with_db_session
from shared.helpers.utils import create_http_task


class GBFSDataProcessor:
    def __init__(self, stable_id: str, feed_id: str):
        self.stable_id = stable_id
        self.feed_id = feed_id
        self.gbfs_versions: List[GBFSVersion] = []
        self.gbfs_endpoints: Dict[str, List[GBFSEndpoint]] = {}
        self.validation_reports: Dict[str, Dict[str, Any]] = {}

    def process_gbfs_data(self, autodiscovery_url: str) -> None:
        """Process the GBFS data from the autodiscovery URL."""
        # Record the request to the autodiscovery URL
        self.record_autodiscovery_request(autodiscovery_url)

        # Extract GBFS versions and endpoints
        self.gbfs_versions = self.extract_gbfs_versions(autodiscovery_url)
        if not self.gbfs_versions:
            raise ValueError("No GBFS versions found.")
        self.extract_endpoints_for_all_versions()

        # Validate GBFS versions
        self.validate_gbfs_feed_versions()

        # Update database entities
        self.update_database_entities()

        self.trigger_location_extraction()

    @with_db_session()
    def record_autodiscovery_request(
        self, autodiscovery_url: str, db_session: Session
    ) -> None:
        """Record the request to the autodiscovery URL."""
        logging.info(f"Accessing auto-discovery URL: {autodiscovery_url}")
        request_metadata = GBFSEndpoint.get_request_metadata(autodiscovery_url)
        gbfs_feed = (
            db_session.query(Gbfsfeed).filter(Gbfsfeed.id == self.feed_id).one_or_none()
        )
        if not gbfs_feed:
            raise ValueError(f"GBFS feed with ID {self.feed_id} not found.")
        gbfs_feed.httpaccesslogs.append(
            Httpaccesslog(
                request_url=autodiscovery_url,
                request_method=HTTPMethod.GET.value,
                status_code=request_metadata.get("status_code"),
                latency_ms=request_metadata.get("latency"),
                response_size_bytes=request_metadata.get("response_size_bytes"),
            )
        )
        db_session.commit()
        if request_metadata.get("response_size_bytes") is None:
            raise ValueError(f"Error fetching {autodiscovery_url}")

    @staticmethod
    def extract_gbfs_endpoints(
        gbfs_json_url: str,
    ) -> Tuple[Optional[List[GBFSEndpoint]], GBFSVersion]:
        """
        Extract GBFS endpoints from the GBFS JSON URL.
        @:returns: GBFS endpoints and the version of the GBFS feed.
        """
        logging.info(f"Fetching GBFS data from {gbfs_json_url}")
        gbfs_json = fetch_gbfs_data(gbfs_json_url)
        feeds_matches = parse("$..feeds").find(gbfs_json)
        version_match = parse("$..version").find(gbfs_json)
        if not version_match:
            logging.warning(
                "No version found in the GBFS data. Defaulting to version 1.0."
            )
            gbfs_version = GBFSVersion("1.0", gbfs_json_url)
        else:
            gbfs_version = GBFSVersion(version_match[0].value, gbfs_json_url)
        if not feeds_matches:
            logging.error(
                f"No feeds found in the GBFS data for version {gbfs_version.version}."
            )
            return None, gbfs_version
        endpoints = []
        for feed_match in feeds_matches:
            try:
                parent_element = feed_match.context.path.fields[0]
                # Validate BCP-47 compliance according the GBFS spec
                language = (
                    parent_element if language_tags.tags.check(parent_element) else None
                )
            except AttributeError:
                language = None
            endpoints += GBFSEndpoint.from_dict(feed_match.value, language)

        # If the autodiscovery endpoint is not listed then add it
        if not any(endpoint.name == "gbfs" for endpoint in endpoints):
            endpoints += GBFSEndpoint.from_dict(
                [{"name": "gbfs", "url": gbfs_json_url}], None
            )

        unique_endpoints = list(
            {
                f"{endpoint.name}, {endpoint.language or ''}": endpoint
                for endpoint in endpoints
            }.values()
        )
        logging.info(f"Found version {gbfs_version.version}.")
        logging.info(
            f"Found endpoints {', '.join([endpoint.name for endpoint in endpoints])}."
        )
        return unique_endpoints, gbfs_version

    def extract_gbfs_versions(self, gbfs_json_url: str) -> Optional[List[GBFSVersion]]:
        """Extract GBFS versions from the autodiscovery URL"""
        all_endpoints, version = GBFSDataProcessor.extract_gbfs_endpoints(gbfs_json_url)
        if not all_endpoints or not version:
            return None
        self.gbfs_endpoints[version.version] = all_endpoints

        # Fetch GBFS Versions
        gbfs_versions_endpoint = next(
            (ep for ep in all_endpoints if ep.name == "gbfs_versions"), None
        )

        if gbfs_versions_endpoint:
            logging.info(f"Fetching GBFS versions from {gbfs_versions_endpoint.url}")
            gbfs_versions_json = fetch_gbfs_data(gbfs_versions_endpoint.url)
            versions_matches = parse("$..versions").find(gbfs_versions_json)
            if versions_matches:
                gbfs_versions = GBFSVersion.from_dict(versions_matches[0].value)
                logging.info(
                    f"Found versions {', '.join([version.version for version in gbfs_versions])}"
                )
                return gbfs_versions
            else:
                logging.warning(
                    "No versions found in the GBFS versions data. Defaulting to the autodiscovery URL version."
                )
        return [
            version
        ]  # If no gbfs_versions endpoint, return the version from the autodiscovery URL

    def get_latest_version(self) -> Optional[str]:
        """Get the latest GBFS version."""
        max_version = max(
            (
                version
                for version in self.gbfs_versions
                if not version.version.lower().endswith("RC")
            ),
            key=lambda version: version.version,
            default=None,
        )
        if not max_version:
            logging.error(
                "No non-RC versions found. Trying to set the latest to a RC version."
            )
            max_version = max(
                self.gbfs_versions, key=lambda version: version.version, default=None
            )
        if not max_version:
            logging.error("No versions found.")
            return None
        return max_version.version

    @with_db_session()
    def update_database_entities(self, db_session: Session) -> None:
        """Update the database entities with the processed GBFS data."""
        gbfs_feed = (
            db_session.query(Gbfsfeed)
            .filter(Gbfsfeed.id == self.feed_id)
            .options(joinedload(Gbfsfeed.gbfsversions))
            .one_or_none()
        )
        if not gbfs_feed:
            logging.error(f"GBFS feed with ID {self.feed_id} not found.")
            return
        gbfs_versions_orm = []
        latest_version = self.get_latest_version()
        if not latest_version:
            return

        # Deactivate versions that are not in the current feed
        active_versions = [version.version for version in self.gbfs_versions]
        for gbfs_version_orm in gbfs_feed.gbfsversions:
            if gbfs_version_orm.version not in active_versions:
                db_session.delete(gbfs_version_orm)
                db_session.flush()

        # Update or create GBFS versions and endpoints
        for gbfs_version in self.gbfs_versions:
            gbfs_version_orm = self.update_or_create_gbfs_version(
                db_session, gbfs_version, latest_version
            )
            gbfs_versions_orm.append(gbfs_version_orm)

            gbfs_endpoints = self.gbfs_endpoints.get(gbfs_version.version, [])
            gbfs_endpoints_orm = []
            features = self.validation_reports.get(gbfs_version.version, {}).get(
                "features", []
            )
            for endpoint in gbfs_endpoints:
                gbfs_endpoint_orm = self.update_or_create_gbfs_endpoint(
                    db_session, gbfs_version.version, endpoint, features
                )
                gbfs_endpoint_orm.httpaccesslogs.append(
                    Httpaccesslog(
                        request_method=HTTPMethod.GET.value,
                        request_url=endpoint.url,
                        status_code=endpoint.status_code,
                        latency_ms=endpoint.latency,
                        response_size_bytes=endpoint.response_size_bytes,
                    )
                )
                gbfs_endpoints_orm.append(gbfs_endpoint_orm)

            # Deactivate endpoints that are not in the current feed
            active_endpoints = [endpoint.name for endpoint in gbfs_endpoints]
            for gbfs_endpoint_orm in gbfs_version_orm.gbfsendpoints:
                if gbfs_endpoint_orm.name not in active_endpoints:
                    db_session.delete(gbfs_endpoint_orm)
                    db_session.flush()
            gbfs_version_orm.gbfsendpoints = gbfs_endpoints_orm

            validation_report_orm = self.create_validation_report_entities(
                gbfs_version_orm, self.validation_reports.get(gbfs_version.version, {})
            )
            if validation_report_orm:
                gbfs_version_orm.gbfsvalidationreports.append(validation_report_orm)
        gbfs_feed.gbfsversions = gbfs_versions_orm
        db_session.commit()

    def update_or_create_gbfs_version(
        self, db_session: Session, gbfs_version: GBFSVersion, latest_version: str
    ) -> Gbfsversion:
        """Update or create a GBFS version entity."""
        formatted_id = f"{self.stable_id}_{gbfs_version.version}"
        gbfs_version_orm = (
            db_session.query(Gbfsversion).filter(Gbfsversion.id == formatted_id).first()
        )
        if not gbfs_version_orm:
            gbfs_version_orm = Gbfsversion(
                id=formatted_id, version=gbfs_version.version
            )

        gbfs_version_orm.url = gbfs_version.url  # Update the URL
        gbfs_version_orm.latest = (
            gbfs_version.version == latest_version
        )  # Update the latest flag
        return gbfs_version_orm

    def update_or_create_gbfs_endpoint(
        self,
        db_session: Session,
        version: str,
        endpoint: GBFSEndpoint,
        features: List[str],
    ) -> Gbfsendpoint:
        """Update or create a GBFS endpoint entity."""
        formatted_id = f"{self.stable_id}_{version}_{endpoint.name}"
        if endpoint.language:
            formatted_id += f"_{endpoint.language}"
        gbfs_endpoint_orm = (
            db_session.query(Gbfsendpoint)
            .filter(Gbfsendpoint.id == formatted_id)
            .first()
        )
        if not gbfs_endpoint_orm:
            gbfs_endpoint_orm = Gbfsendpoint(
                id=formatted_id, name=endpoint.name, language=endpoint.language
            )

        gbfs_endpoint_orm.url = endpoint.url  # Update the URL
        gbfs_endpoint_orm.is_feature = endpoint.name in features
        return gbfs_endpoint_orm

    def validate_gbfs_feed_versions(self) -> None:
        """Validate the GBFS feed versions and store the reports in GCS."""
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)

        date_time_utc = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        for version in self.gbfs_versions:
            json_payload = {"url": version.url}
            try:
                response = requests.post(VALIDATOR_URL, json=json_payload)
                response.raise_for_status()
                json_report_summary = response.json()
            except RequestException as e:
                logging.error(f"Validation request failed for {version.url}: {e}")
                continue

            report_summary_blob = bucket.blob(
                f"{self.stable_id}/{version.version}/report_summary_{date_time_utc}.json"
            )
            report_summary_blob.upload_from_string(
                json.dumps(json_report_summary), content_type="application/json"
            )
            report_summary_blob.make_public()
            self.validation_reports[version.version] = {
                "report_summary_url": report_summary_blob.public_url,
                "json_report_summary": json_report_summary,
                "validation_time": date_time_utc,
                "features": [
                    obj["file"].replace(".json", "")
                    for obj in json_report_summary.get("filesSummary", [])
                    if not obj.get("required", True) and obj.get("exists", False)
                ],
            }

    def create_validation_report_entities(
        self, gbfs_version_orm: Gbfsversion, validation_report_data: Dict
    ) -> Optional[Gbfsvalidationreport]:
        """Create a validation report entities."""
        validation_report_url = validation_report_data.get("report_summary_url")
        validation_report_json = validation_report_data.get("json_report_summary")
        validation_time = validation_report_data.get("validation_time")

        validator_version = validation_report_json.get("summary", {}).get(
            "validatorVersion", None
        )
        if validator_version is None or validation_time is None:
            logging.error("Validation version or time not found.")
            return None

        validation_report_id = (
            f"{self.stable_id}_v{gbfs_version_orm.version}_{validation_time}"
        )
        validation_report = Gbfsvalidationreport(
            id=validation_report_id,
            validator_version=validator_version,
            report_summary_url=validation_report_url,
            total_errors_count=validation_report_json.get("summary", {}).get(
                "errorsCount", 0
            ),
        )
        validation_report.gbfsnotices = [
            Gbfsnotice(
                keyword=error["keyword"],
                message=error["message"],
                schema_path=error["schemaPath"],
                gbfs_file=file_summary["file"],
                validation_report_id=validation_report.id,
                count=error["count"],
            )
            for file_summary in validation_report_json.get("filesSummary", [])
            if file_summary["hasErrors"]
            for error in file_summary["groupedErrors"]
        ]
        return validation_report

    def extract_endpoints_for_all_versions(self):
        """Extract endpoints for all versions of the GBFS feed."""
        for version in self.gbfs_versions:
            if version.version in self.gbfs_endpoints:
                continue
            endpoints, _ = self.extract_gbfs_endpoints(version.url)
            if endpoints:
                self.gbfs_endpoints[version.version] = endpoints
            else:
                logging.error(f"No endpoints found for version {version.version}.")

    def trigger_location_extraction(self):
        """Trigger the location extraction process."""
        latest_version = self.get_latest_version()
        if not latest_version:
            logging.error("No latest version found.")
            return
        endpoints = self.gbfs_endpoints.get(latest_version, [])
        # Find the station_information_url endpoint
        station_information_url = next(
            (
                endpoint.url
                for endpoint in endpoints
                if endpoint.name == "station_information"
            ),
            None,
        )
        # If station_information_url is not found, use vehicle_status_url
        vehicle_status_url = next(
            (
                endpoint.url
                for endpoint in endpoints
                if endpoint.name == "vehicle_status"
            ),
            None,
        )
        if not station_information_url and not vehicle_status_url:
            logging.warning("No station_information_url or vehicle_status_url found.")
            return
        client = tasks_v2.CloudTasksClient()
        body = json.dumps(
            {
                "stable_id": self.stable_id,
                "data_type": "gbfs",
                "station_information_url": station_information_url,
                "vehicle_status_url": vehicle_status_url,
            }
        ).encode()
        project_id = os.getenv("PROJECT_ID")
        gcp_region = os.getenv("GCP_REGION")
        queue_name = os.getenv("QUEUE_NAME")
        create_http_task(
            client,
            body,
            f"https://{gcp_region}-{project_id}.cloudfunctions.net/reverse-geolocation-processor",
            project_id,
            gcp_region,
            queue_name,
        )
