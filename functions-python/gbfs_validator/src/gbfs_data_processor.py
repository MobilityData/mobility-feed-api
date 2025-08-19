import json
import language_tags
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
from shared.helpers.logger import get_logger
from shared.helpers.utils import create_http_task

FEATURE_ENDPOINTS = [
    "manifest",
    "gbfs_versions",
    "vehicle_types",
    "station_status",
    "vehicle_status",
    "free_bike_status",
    "system_regions",
    "system_pricing_plans",
    "system_alerts",
    "geofencing_zones",
]


class GBFSDataProcessor:
    def __init__(self, stable_id: str, feed_id: str):
        self.stable_id = stable_id
        self.feed_id = feed_id
        self.gbfs_versions: List[GBFSVersion] = []
        self.gbfs_endpoints: Dict[str, List[GBFSEndpoint]] = {}
        self.validation_reports: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger(GBFSDataProcessor.__name__, stable_id)

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
        self.logger.info("Accessing auto-discovery URL: %s", autodiscovery_url)
        request_metadata = GBFSEndpoint.get_request_metadata(
            autodiscovery_url, self.logger
        )
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

    def extract_gbfs_endpoints(
        self, gbfs_json_url: str, extracted_from: str, latency: bool = True
    ) -> Tuple[Optional[List[GBFSEndpoint]], GBFSVersion]:
        """
        Extract GBFS endpoints from the GBFS JSON URL.
        @:returns: GBFS endpoints and the version of the GBFS feed.
        """
        self.logger.info("Fetching GBFS data from %s", gbfs_json_url)
        gbfs_json = fetch_gbfs_data(gbfs_json_url)
        feeds_matches = parse("$..feeds").find(gbfs_json)
        version_match = parse("$..version").find(gbfs_json)
        if not version_match:
            self.logger.warning(
                "No version found in the GBFS data. Defaulting to version 1.0."
            )
            gbfs_version = GBFSVersion("1.0", gbfs_json_url, extracted_from)
        else:
            gbfs_version = GBFSVersion(
                version_match[0].value, gbfs_json_url, extracted_from
            )
        if not feeds_matches:
            self.logger.error(
                "No feeds found in the GBFS data for version %s.", gbfs_version.version
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
            endpoints += GBFSEndpoint.from_dict(feed_match.value, language, latency)

        # If the autodiscovery endpoint is not listed, then add it
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
        if len(unique_endpoints) != len(endpoints):
            self.logger.warning(
                "Duplicate endpoints found. This is a spec violation. Duplicates have been ignored."
            )

        self.logger.info("Found version %s.", gbfs_version.version)
        self.logger.info(
            "Found endpoints %s.", ", ".join([endpoint.name for endpoint in endpoints])
        )
        return unique_endpoints, gbfs_version

    def extract_gbfs_versions(self, gbfs_json_url: str) -> Optional[List[GBFSVersion]]:
        """Extract GBFS versions from the autodiscovery URL"""
        all_endpoints, version = self.extract_gbfs_endpoints(
            gbfs_json_url, "autodiscovery"
        )
        if not all_endpoints or not version:
            return None
        version_id = f"{self.stable_id}_{version.version}_{version.extracted_from}"
        self.gbfs_endpoints[version_id] = all_endpoints

        # Fetch GBFS Versions
        gbfs_versions_endpoint = next(
            (ep for ep in all_endpoints if ep.name == "gbfs_versions"), None
        )

        if gbfs_versions_endpoint:
            self.logger.info(
                "Fetching GBFS versions from %s", gbfs_versions_endpoint.url
            )
            gbfs_versions_json = fetch_gbfs_data(gbfs_versions_endpoint.url)
            versions_matches = parse("$..versions").find(gbfs_versions_json)
            if versions_matches:
                extracted_versions = GBFSVersion.from_dict(
                    versions_matches[0].value, "gbfs_versions"
                )
                autodiscovery_url_in_extracted = any(
                    version.url == gbfs_json_url for version in extracted_versions
                )
                if len(extracted_versions) > 0 and not autodiscovery_url_in_extracted:
                    self.logger.warning(
                        "The autodiscovery URL is not included in gbfs_versions. There could be duplication"
                        " of versions."
                    )
                gbfs_versions = [
                    version
                    for version in extracted_versions
                    if version.url != gbfs_json_url
                ] + [version]
                self.logger.info(
                    "Found versions %s",
                    ", ".join([version.version for version in gbfs_versions]),
                )
                return gbfs_versions
            else:
                self.logger.warning(
                    "No versions found in the GBFS versions data. Defaulting to the autodiscovery URL version."
                )
        return [
            version
        ]  # If no gbfs_versions endpoint, return the version from the autodiscovery URL

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
            self.logger.error("GBFS feed with ID %s not found.", self.feed_id)
            return
        gbfs_versions_orm = []

        # Deactivate versions that are not in the current feed
        active_versions = [version.version for version in self.gbfs_versions]
        for gbfs_version_orm in gbfs_feed.gbfsversions:
            if gbfs_version_orm.version not in active_versions:
                db_session.delete(gbfs_version_orm)
                db_session.flush()

        # Update or create GBFS versions and endpoints
        for gbfs_version in self.gbfs_versions:
            gbfs_version_orm = self.update_or_create_gbfs_version(
                db_session, gbfs_version
            )
            gbfs_versions_orm.append(gbfs_version_orm)

            gbfs_endpoints = self.gbfs_endpoints.get(gbfs_version_orm.id, [])
            gbfs_endpoints_orm = []
            features = self.validation_reports.get(gbfs_version_orm.id, {}).get(
                "features", []
            )
            for endpoint in gbfs_endpoints:
                gbfs_endpoint_orm = self.update_or_create_gbfs_endpoint(
                    db_session, gbfs_version_orm.id, endpoint, features
                )
                if endpoint.status_code is not None:
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
                gbfs_version_orm, self.validation_reports.get(gbfs_version_orm.id, {})
            )
            if validation_report_orm:
                gbfs_version_orm.gbfsvalidationreports.append(validation_report_orm)
        gbfs_feed.gbfsversions = gbfs_versions_orm
        db_session.commit()

    def update_or_create_gbfs_version(
        self, db_session: Session, gbfs_version: GBFSVersion
    ) -> Gbfsversion:
        """Update or create a GBFS version entity."""
        formatted_id = (
            f"{self.stable_id}_{gbfs_version.version}_{gbfs_version.extracted_from}"
        )
        gbfs_version_orm = (
            db_session.query(Gbfsversion).filter(Gbfsversion.id == formatted_id).first()
        )
        if not gbfs_version_orm:
            gbfs_version_orm = Gbfsversion(
                id=formatted_id,
                version=gbfs_version.version,
                source=gbfs_version.extracted_from,
            )

        gbfs_version_orm.url = gbfs_version.url  # Update the URL
        return gbfs_version_orm

    def update_or_create_gbfs_endpoint(
        self,
        db_session: Session,
        version_id: str,
        endpoint: GBFSEndpoint,
        features: List[str],
    ) -> Gbfsendpoint:
        """Update or create a GBFS endpoint entity."""
        formatted_id = f"{version_id}_{endpoint.name}"
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
        gbfs_endpoint_orm.url = endpoint.url
        gbfs_endpoint_orm.is_feature = (
            endpoint.name in features and endpoint.name in FEATURE_ENDPOINTS
        )
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
                self.logger.error("Validation request failed for %s", version.url)
                self.logger.error(e)
                continue

            report_summary_blob = bucket.blob(
                f"{self.stable_id}/{version.version}/report_summary_{date_time_utc}.json"
            )
            report_summary_blob.upload_from_string(
                json.dumps(json_report_summary), content_type="application/json"
            )
            report_summary_blob.make_public()
            version_id = f"{self.stable_id}_{version.version}_{version.extracted_from}"
            self.validation_reports[version_id] = {
                "report_summary_url": report_summary_blob.public_url,
                "json_report_summary": json_report_summary,
                "validation_time": date_time_utc,
                "features": [
                    obj["file"].replace(".json", "")
                    for obj in json_report_summary.get("filesSummary", [])
                    if not obj.get("required", True) and obj.get("exists", False)
                ],
            }
            self.logger.info(
                f"Validated GBFS feed version: {version.version} with URL: {version.url}"
            )

    def create_validation_report_entities(
        self, gbfs_version_orm: Gbfsversion, validation_report_data: Dict
    ) -> Optional[Gbfsvalidationreport]:
        """Create a validation report entities."""
        validation_report_url = validation_report_data.get("report_summary_url")
        validation_report_json = validation_report_data.get("json_report_summary")
        validation_time = validation_report_data.get("validation_time")
        if not validation_report_url:
            self.logger.error("Validation report doesn't exist")
            return None

        validator_version = validation_report_json.get("summary", {}).get(
            "validatorVersion", None
        )
        if validator_version is None or validation_time is None:
            self.logger.error("Validation version or time not found.")
            return None

        validation_report_id = (
            f"{self.stable_id}_v{gbfs_version_orm.id}_{validation_time}"
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

    def validate_gbfs_endpoint_url(self, endpoint_url: str) -> bool:
        """Checks if a gbfs endpoint exists across all versions with the specified URL."""
        for version in self.gbfs_versions:
            version_id = f"{self.stable_id}_{version.version}_{version.extracted_from}"
            endpoints = self.gbfs_endpoints.get(version_id, [])
            if any(endpoint.url == endpoint_url for endpoint in endpoints):
                return True
        return False

    def extract_endpoints_for_all_versions(self):
        """Extract endpoints for all versions of the GBFS feed."""
        version_delete_list = []
        for version in self.gbfs_versions:
            version_id = f"{self.stable_id}_{version.version}_{version.extracted_from}"
            if version_id in self.gbfs_endpoints:
                continue
            self.logger.info(f"Extracting endpoints for version {version.version}.")
            # Avoid fetching latency data for 'gbfs_versions' endpoint
            endpoints, _ = self.extract_gbfs_endpoints(
                version.url, "gbfs_versions", latency=False
            )
            if endpoints:
                # Check if the gbfs endpoint is already present in another version
                gbfs_endpoint_url = next(
                    (ep.url for ep in endpoints if ep.name == "gbfs"), None
                )
                if (
                    gbfs_endpoint_url
                    and version.extracted_from == "gbfs_versions"
                    and self.validate_gbfs_endpoint_url(gbfs_endpoint_url)
                ):
                    self.logger.warning(
                        "The 'gbfs' endpoint URL %s is already present in another version.",
                        gbfs_endpoint_url,
                    )
                    version_delete_list.append(version)
                    continue

                self.gbfs_endpoints[version_id] = endpoints
            else:
                self.logger.error("No endpoints found for version %s.", version.version)
        # Remove versions that had no endpoints extracted
        for version in version_delete_list:
            version_id = f"{self.stable_id}_{version.version}_{version.extracted_from}"
            self.logger.warning(
                "Removing version %s due to duplicated 'gbfs' endpoint.", version_id
            )
            self.gbfs_versions.remove(version)

    def trigger_location_extraction(self):
        """Trigger the location extraction process."""
        autodiscovery_version = next(
            (
                version
                for version in self.gbfs_versions
                if version.extracted_from == "autodiscovery"
            ),
            None,
        )
        if not autodiscovery_version:
            self.logger.error(
                "No autodiscovery version found. Cannot trigger location extraction."
            )
            return
        version_id = f"{self.stable_id}_{autodiscovery_version.version}_{autodiscovery_version.extracted_from}"
        endpoints = self.gbfs_endpoints.get(version_id, [])

        def get_endpoint_url(name: str) -> Optional[str]:
            return next(
                (endpoint.url for endpoint in endpoints if endpoint.name == name), None
            )

        # Get the URLs for the required endpoints
        station_information_url = get_endpoint_url("station_information")
        vehicle_status_url = get_endpoint_url("vehicle_status")
        free_bike_status_url = get_endpoint_url("free_bike_status")

        if (
            not station_information_url
            and not vehicle_status_url
            and not free_bike_status_url
        ):
            self.logger.warning(
                "No station_information_url or vehicle_status_url or free_bike_status_url found."
            )
            return
        client = tasks_v2.CloudTasksClient()
        body = json.dumps(
            {
                "stable_id": self.stable_id,
                "data_type": "gbfs",
                "station_information_url": station_information_url,
                "vehicle_status_url": vehicle_status_url,
                "free_bike_status_url": free_bike_status_url,
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
