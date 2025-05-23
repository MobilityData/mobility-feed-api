import os
import unittest
from unittest.mock import patch

import faker

from gbfs_data_processor import GBFSDataProcessor
from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Gbfsfeed
from test_shared.test_utils.database_utils import (
    default_db_url,
    clean_testing_db,
)


def mock_fetch_gbfs_data(url):
    # Return different data based on the URL
    if "gbfs.json" in url:
        return {
            "data": {
                "feeds": [
                    {
                        "name": "system_information",
                        "url": "https://example.com/system_information.json",
                    },
                    {
                        "name": "vehicle_status",
                        "url": "https://example.com/vehicle_status.json",
                    },
                    {
                        "name": "gbfs_versions",
                        "url": "https://example.com/gbfs_versions.json",
                    },
                ]
            },
            "version": "2.2",
        }
    elif "gbfs_versions.json" in url:
        return {
            "data": {
                "versions": [
                    {"version": "2.2", "url": "https://example.com/2.2/gbfs.json"},
                    {"version": "2.1", "url": "https://example.com/2.1/gbfs.json"},
                ]
            }
        }
    else:
        # Default case: return an empty dictionary
        return {}


def mock_get_request_metadata(*args, **kwargs):
    return {
        "latency": 100,
        "status_code": 200,
        "response_size_bytes": 1000,
    }


class TestGbfsDataProcessor(unittest.TestCase):
    def setUp(self):
        clean_testing_db()
        self.faker = faker.Faker()
        self.stable_id = "test_stable_id"
        self.feed_id = self.faker.uuid4(cast_to=str)
        self.processor = GBFSDataProcessor(
            stable_id=self.stable_id, feed_id=self.feed_id
        )

    @with_db_session(db_url=default_db_url)
    @patch("gbfs_data_processor.create_http_task")
    @patch("gbfs_data_processor.tasks_v2")
    @patch(
        "gbfs_data_processor.GBFSEndpoint.get_request_metadata",
        side_effect=mock_get_request_metadata,
    )
    @patch("google.cloud.storage.Client")
    @patch("gbfs_data_processor.fetch_gbfs_data", side_effect=mock_fetch_gbfs_data)
    @patch("requests.post")
    @patch("requests.get")
    @patch.dict(
        os.environ,
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": "test",
        },
    )
    def test_fetch_gbfs_files(
        self, _, mock_post, __, mock_cloud_storage_client, ___, ____, _____, db_session
    ):
        autodiscovery_url = "http://example.com/gbfs.json"
        # Add GBFS feed to the database
        gbfs_feed = Gbfsfeed(
            id=self.feed_id,
            operator=self.faker.company(),
            operator_url=self.faker.url(),
            stable_id=self.stable_id,
            auto_discovery_url=autodiscovery_url,
            status="active",
            operational_status="published",
        )
        session = db_session
        session.add(gbfs_feed)
        session.commit()
        (
            mock_cloud_storage_client.return_value.bucket.return_value.blob.return_value
        ).public_url = self.faker.url()
        with patch("logging.info"), patch("logging.error"), patch("logging.warning"):
            mock_post.return_value.json.return_value = {
                "summary": {
                    "validatorVersion": "1.0.13",
                    "version": {"detected": "2.2", "validated": "2.2"},
                    "hasErrors": True,
                    "errorsCount": 5,
                },
                "filesSummary": [
                    {
                        "required": True,
                        "exists": True,
                        "file": "gbfs.json",
                        "hasErrors": True,
                        "errorsCount": 2,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": True,
                        "file": "gbfs_versions.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": True,
                        "exists": True,
                        "file": "system_information.json",
                        "hasErrors": True,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "vehicle_types.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "station_information.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "station_status.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "free_bike_status.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "system_hours.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "system_calendar.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "system_regions.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": True,
                        "file": "vehicle_status.json",
                        "hasErrors": True,
                        "errorsCount": 2,
                        "groupedErrors": [
                            {
                                "keyword": "type",
                                "message": "must be string",
                                "schemaPath": "#/properties/data/properties/plans/items/properties/plan_id/type",
                                "count": 1,
                            },
                            {
                                "keyword": "type",
                                "message": "must be string",
                                "schemaPath": "#/properties/data/properties/plans/items/properties/url/type",
                                "count": 1,
                            },
                        ],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "system_alerts.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                    {
                        "required": False,
                        "exists": False,
                        "file": "geofencing_zones.json",
                        "hasErrors": False,
                        "errorsCount": 0,
                        "groupedErrors": [],
                    },
                ],
            }
            self.processor.process_gbfs_data(autodiscovery_url)
            gbfs_feed = (
                session.query(Gbfsfeed)
                .filter_by(stable_id=self.stable_id)
                .one_or_none()
            )

            # Validate versions
            self.assertEqual(len(gbfs_feed.gbfsversions), 2)
            versions = [version.version for version in gbfs_feed.gbfsversions]
            # Validate that autodiscovery url endpoint is added to all versions
            for gbfs_version in gbfs_feed.gbfsversions:
                assert any(
                    endpoint.name == "gbfs" for endpoint in gbfs_version.gbfsendpoints
                )
            self.assertIn("2.2", versions)
            self.assertIn("2.1", versions)
