import logging
import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import requests

from shared.dataset_service.main import Status

BUCKET_NAME = os.getenv("BUCKET_NAME", "mobilitydata-gbfs-snapshots-dev")
VALIDATOR_URL = os.getenv(
    "VALIDATOR_URL",
    "https://gbfs-validator.mobilitydata.org/.netlify/functions/validator-summary",
)


@dataclass(frozen=True)
class GBFSEndpoint:
    name: str
    url: str
    latency: Optional[float]
    status_code: int
    response_size_bytes: Optional[int]
    language: Optional[str] = None

    @staticmethod
    def get_request_metadata(
        url: str, logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch the endpoint and return latency, status code, and response size."""
        try:
            logger = logger or logging.getLogger(__name__)
            response = requests.get(url)
            response.raise_for_status()
            return {
                "latency": response.elapsed.total_seconds() * 1000,
                "status_code": response.status_code,
                "response_size_bytes": len(response.content),
            }
        except requests.exceptions.RequestException as error:
            logger.error("Error fetching %s. Error %s", url, error)
            return {
                "latency": None,
                "status_code": error.response.status_code if error.response else 400,
                "response_size_bytes": None,
            }

    @staticmethod
    def from_dict(
        data: List[Dict[str, Any]], language: Optional[str]
    ) -> List["GBFSEndpoint"]:
        """Creates a list of GBFSEndpoint objects from a list of dictionaries."""
        endpoints = []
        for file in data:
            if "name" in file and "url" in file:
                metadata = GBFSEndpoint.get_request_metadata(file["url"])
                if metadata:
                    endpoints.append(
                        GBFSEndpoint(
                            name=file["name"],
                            url=file["url"],
                            latency=metadata["latency"],
                            status_code=metadata["status_code"],
                            response_size_bytes=metadata["response_size_bytes"],
                            language=language,
                        )
                    )
        return endpoints


@dataclass(frozen=True)
class GBFSVersion:
    version: str
    url: str

    @staticmethod
    def from_dict(data: List[Dict[str, Any]]) -> List["GBFSVersion"]:
        """Creates a list of GBFSFile objects from a list of dictionaries."""
        return [
            GBFSVersion(version["version"], version["url"])
            for version in data
            if "version" in version and "url" in version
        ]


def fetch_gbfs_data(url: str) -> Dict[str, Any]:
    """Fetch the GBFS data from the autodiscovery URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def save_trace_with_error(trace, error, trace_service):
    """Helper function to save trace with an error."""
    trace.error_message = error
    trace.status = Status.FAILED
    trace_service.save(trace)
