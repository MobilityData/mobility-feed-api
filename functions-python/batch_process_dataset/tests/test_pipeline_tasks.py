import json
import os
import unittest
from unittest.mock import patch, MagicMock

from pipeline_tasks import (
    create_http_reverse_geolocation_processor_task,
    create_http_pmtiles_builder_task,
    create_pipeline_tasks,
)


class SimpleFile:
    def __init__(self, file_name, file_size_bytes=None, hosted_url=None):
        self.file_name = file_name
        self.file_size_bytes = file_size_bytes
        self.hosted_url = hosted_url


class SimpleFeed:
    def __init__(self, stable_id):
        self.stable_id = stable_id


class SimpleDataset:
    def __init__(self, feed_stable_id, dataset_stable_id, files):
        self.feed = SimpleFeed(feed_stable_id)
        self.stable_id = dataset_stable_id
        self.gtfsfiles = files


class TestTaskCreation(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "REVERSE_GEOLOCATION_QUEUE": "rev-geo-queue",
            "PROJECT_ID": "my-project",
            "GCP_REGION": "northamerica-northeast1",
        },
        clear=False,
    )
    @patch("pipeline_tasks.create_http_task")
    @patch("pipeline_tasks.tasks_v2.CloudTasksClient")
    def test_create_http_reverse_geolocation_processor_task_happy_path(
        self, mock_client_cls, mock_create_http_task
    ):
        client_instance = MagicMock()
        mock_client_cls.return_value = client_instance

        stable_id = "feed-123"
        dataset_stable_id = "dataset-abc"
        stops_url = "https://example.com/stops.txt"

        create_http_reverse_geolocation_processor_task(
            stable_id=stable_id,
            dataset_stable_id=dataset_stable_id,
            stops_url=stops_url,
        )

        mock_client_cls.assert_called_once()

        # Validate create_http_task() call
        self.assertEqual(mock_create_http_task.call_count, 1)
        args, kwargs = mock_create_http_task.call_args

        # args = (client, body, url, project_id, gcp_region, queue_name)
        self.assertIs(args[0], client_instance)

        # body content
        body_bytes = args[1]
        payload = json.loads(body_bytes.decode("utf-8"))
        self.assertEqual(
            payload,
            {
                "stable_id": stable_id,
                "stops_url": stops_url,
                "dataset_id": dataset_stable_id,
            },
        )

        # URL & env
        expected_url = (
            "https://northamerica-northeast1-my-project.cloudfunctions.net/"
            "reverse-geolocation-processor"
        )
        self.assertEqual(args[2], expected_url)
        self.assertEqual(args[3], "my-project")
        self.assertEqual(args[4], "northamerica-northeast1")
        self.assertEqual(args[5], "rev-geo-queue")

    @patch.dict(
        os.environ,
        {
            "PMTILES_BUILDER_QUEUE": "pmtiles-queue",
            "PROJECT_ID": "my-project",
            "GCP_REGION": "northamerica-northeast1",
        },
        clear=False,
    )
    @patch("pipeline_tasks.create_http_task")
    @patch("pipeline_tasks.tasks_v2.CloudTasksClient")
    def test_create_http_pmtiles_builder_task_happy_path(
        self, mock_client_cls, mock_create_http_task
    ):
        client_instance = MagicMock()
        mock_client_cls.return_value = client_instance

        stable_id = "feed-456"
        dataset_stable_id = "dataset-def"

        create_http_pmtiles_builder_task(
            stable_id=stable_id,
            dataset_stable_id=dataset_stable_id,
        )

        mock_client_cls.assert_called_once()
        self.assertEqual(mock_create_http_task.call_count, 1)

        args, _ = mock_create_http_task.call_args

        # body content
        body_bytes = args[1]
        payload = json.loads(body_bytes.decode("utf-8"))
        self.assertEqual(
            payload,
            {
                "feed_stable_id": stable_id,
                "dataset_stable_id": dataset_stable_id,
            },
        )

        expected_url = "https://northamerica-northeast1-my-project.cloudfunctions.net/pmtiles_builder"
        self.assertEqual(args[2], expected_url)
        self.assertEqual(args[3], "my-project")
        self.assertEqual(args[4], "northamerica-northeast1")
        self.assertEqual(args[5], "pmtiles-queue")

    @patch.dict(
        os.environ,
        {
            "REVERSE_GEOLOCATION_QUEUE": "rev-geo-queue",
            "PMTILES_BUILDER_QUEUE": "pmtiles-queue",
            "PROJECT_ID": "proj-1",
            "GCP_REGION": "na-ne1",
        },
        clear=False,
    )
    @patch("pipeline_tasks.create_http_pmtiles_builder_task")
    @patch("pipeline_tasks.create_http_reverse_geolocation_processor_task")
    def test_create_pipeline_tasks_both_tasks_created(
        self,
        mock_rev_geo_task,
        mock_pmtiles_task,
    ):
        # stops.txt present (has hosted_url) → reverse geo task should be created
        # routes.txt present and size in (0, 1_000_000) → pmtiles task should be created
        dataset = SimpleDataset(
            feed_stable_id="feed-A",
            dataset_stable_id="dataset-1",
            files=[
                SimpleFile("stops.txt", hosted_url="https://x.com/stops.txt"),
                SimpleFile("routes.txt", file_size_bytes=250_000),
            ],
        )

        create_pipeline_tasks(dataset)

        mock_rev_geo_task.assert_called_once_with(
            "feed-A", "dataset-1", "https://x.com/stops.txt"
        )
        mock_pmtiles_task.assert_called_once_with("feed-A", "dataset-1")

    @patch.dict(
        os.environ,
        {
            "REVERSE_GEOLOCATION_QUEUE": "rev-geo-queue",
            "PMTILES_BUILDER_QUEUE": "pmtiles-queue",
            "PROJECT_ID": "proj-1",
            "GCP_REGION": "na-ne1",
        },
        clear=False,
    )
    @patch("pipeline_tasks.create_http_pmtiles_builder_task")
    @patch("pipeline_tasks.create_http_reverse_geolocation_processor_task")
    def test_create_pipeline_tasks_missing_stops_or_routes(
        self,
        mock_rev_geo_task,
        mock_pmtiles_task,
    ):
        # No stops.txt → no reverse geolocation task
        # No routes.txt → no pmtiles task
        dataset = SimpleDataset(
            feed_stable_id="feed-B",
            dataset_stable_id="dataset-2",
            files=[
                SimpleFile("trips.txt"),
                SimpleFile("calendar.txt"),
            ],
        )

        create_pipeline_tasks(dataset)

        mock_rev_geo_task.assert_not_called()
        mock_pmtiles_task.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "REVERSE_GEOLOCATION_QUEUE": "rev-geo-queue",
            "PMTILES_BUILDER_QUEUE": "pmtiles-queue",
            "PROJECT_ID": "proj-1",
            "GCP_REGION": "na-ne1",
        },
        clear=False,
    )
    @patch("pipeline_tasks.logging.info")
    @patch("pipeline_tasks.create_http_pmtiles_builder_task")
    @patch("pipeline_tasks.create_http_reverse_geolocation_processor_task")
    def test_create_pipeline_tasks_routes_size_edge_cases(
        self,
        mock_rev_geo_task,
        mock_pmtiles_task,
        mock_log_info,
    ):
        # Case 1: routes size == 0 → NO pmtiles
        dataset_zero = SimpleDataset(
            feed_stable_id="feed-C",
            dataset_stable_id="dataset-3",
            files=[
                SimpleFile("stops.txt", hosted_url="https://x.com/stops.txt"),
                SimpleFile("routes.txt", file_size_bytes=0),
            ],
        )
        create_pipeline_tasks(dataset_zero)
        mock_pmtiles_task.assert_not_called()

        # Case 2: routes size >= 1_000_000 → NO pmtiles, log info
        mock_pmtiles_task.reset_mock()
        dataset_large = SimpleDataset(
            feed_stable_id="feed-D",
            dataset_stable_id="dataset-4",
            files=[
                SimpleFile("stops.txt", hosted_url="https://x.com/stops.txt"),
                SimpleFile("routes.txt", file_size_bytes=1_000_000),
            ],
        )
        create_pipeline_tasks(dataset_large)
        mock_pmtiles_task.assert_not_called()
        # Ensure we logged skip message (don’t assert exact string; check key fragments)
        self.assertTrue(mock_log_info.called)
        log_msg = mock_log_info.call_args[0][0]
        self.assertIn("Skipping PMTiles task", log_msg)
        self.assertIn("dataset-4", log_msg)
        self.assertIn("routes.txt size", log_msg)

        # Case 3: routes size in (0, 1_000_000) → create pmtiles
        mock_pmtiles_task.reset_mock()
        dataset_ok = SimpleDataset(
            feed_stable_id="feed-E",
            dataset_stable_id="dataset-5",
            files=[
                SimpleFile("stops.txt", hosted_url="https://x.com/stops.txt"),
                SimpleFile("routes.txt", file_size_bytes=999_999),
            ],
        )
        create_pipeline_tasks(dataset_ok)
        mock_pmtiles_task.assert_called_once_with("feed-E", "dataset-5")
