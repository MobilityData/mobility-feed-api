import json
import os
import unittest
from unittest.mock import patch, MagicMock

from pipeline_tasks import (
    create_http_reverse_geolocation_processor_task,
    get_changed_files,
    create_pipeline_tasks,
)


class SimpleFile:
    def __init__(
        self, file_name, file_size_bytes=None, hosted_url=None, file_hash=None
    ):
        self.file_name = file_name
        self.file_size_bytes = file_size_bytes
        self.hosted_url = hosted_url
        self.hash = file_hash


class SimpleFeed:
    def __init__(self, stable_id):
        self.stable_id = stable_id


class SimpleDataset:
    def __init__(self, feed_id, dataset_id, feed_stable_id, dataset_stable_id, files):
        self.feed_id = feed_id
        self.id = dataset_id
        self.feed = SimpleFeed(feed_stable_id)
        self.stable_id = dataset_stable_id
        self.gtfsfiles = files


class TestPipelineTasks(unittest.TestCase):
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
    def test_create_http_reverse_geolocation_processor_task(
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
        self.assertEqual(mock_create_http_task.call_count, 1)
        args, _ = mock_create_http_task.call_args

        # (client, body, url, project_id, gcp_region, queue_name)
        self.assertIs(args[0], client_instance)
        payload = json.loads(args[1].decode("utf-8"))
        self.assertEqual(
            payload,
            {
                "stable_id": stable_id,
                "stops_url": stops_url,
                "dataset_id": dataset_stable_id,
            },
        )
        self.assertEqual(
            args[2],
            "https://northamerica-northeast1-my-project.cloudfunctions.net/reverse-geolocation-processor",
        )
        self.assertEqual(args[3], "my-project")
        self.assertEqual(args[4], "northamerica-northeast1")
        self.assertEqual(args[5], "rev-geo-queue")


class TestHasFileChanged(unittest.TestCase):
    def _make_mock_session_chain(self, previous_dataset):
        """
        Build a mock db_session with the chained call:
        db_session.query(...).filter(...).order_by(...).first() -> previous_dataset
        """
        mock_first = MagicMock(return_value=previous_dataset)
        mock_order_by = MagicMock(first=mock_first)
        mock_filter = MagicMock(order_by=MagicMock(return_value=mock_order_by))
        mock_query = MagicMock(filter=MagicMock(return_value=mock_filter))
        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        return mock_session

    def test_no_previous_dataset_returns_true(self):
        dataset = SimpleDataset(
            feed_id=1,
            dataset_id=10,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-1",
            files=[SimpleFile("stops.txt", file_hash="h1")],
        )
        mock_session = self._make_mock_session_chain(previous_dataset=None)

        result = get_changed_files(dataset, db_session=mock_session)
        self.assertTrue("stops.txt" in result)

    def test_previous_without_target_file_returns_true(self):
        prev = SimpleDataset(
            feed_id=1,
            dataset_id=9,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-0",
            files=[SimpleFile("routes.txt", file_hash="x")],  # no stops.txt here
        )
        dataset = SimpleDataset(
            feed_id=1,
            dataset_id=10,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-1",
            files=[SimpleFile("stops.txt", file_hash="h1")],
        )
        mock_session = self._make_mock_session_chain(previous_dataset=prev)

        result = get_changed_files(dataset, db_session=mock_session)
        self.assertTrue("stops.txt" in result)

    def test_new_dataset_missing_target_file_returns_false(self):
        prev = SimpleDataset(
            feed_id=1,
            dataset_id=9,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-0",
            files=[SimpleFile("stops.txt", file_hash="h0")],
        )
        dataset = SimpleDataset(
            feed_id=1,
            dataset_id=10,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-1",
            files=[SimpleFile("routes.txt", file_hash="x")],  # no stops.txt now
        )
        mock_session = self._make_mock_session_chain(previous_dataset=prev)

        result = get_changed_files(dataset, db_session=mock_session)
        self.assertFalse("stops.txt" in result)

    def test_hash_diff_returns_true(self):
        prev = SimpleDataset(
            feed_id=1,
            dataset_id=9,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-0",
            files=[SimpleFile("stops.txt", file_hash="h0")],
        )
        dataset = SimpleDataset(
            feed_id=1,
            dataset_id=10,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-1",
            files=[SimpleFile("stops.txt", file_hash="h1")],
        )
        mock_session = self._make_mock_session_chain(previous_dataset=prev)

        result = get_changed_files(dataset, db_session=mock_session)
        self.assertTrue("stops.txt" in result)

    def test_hash_same_returns_false(self):
        prev = SimpleDataset(
            feed_id=1,
            dataset_id=9,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-0",
            files=[SimpleFile("stops.txt", file_hash="h0")],
        )
        dataset = SimpleDataset(
            feed_id=1,
            dataset_id=10,
            feed_stable_id="feed-A",
            dataset_stable_id="ds-1",
            files=[SimpleFile("stops.txt", file_hash="h0")],
        )
        mock_session = self._make_mock_session_chain(previous_dataset=prev)

        result = get_changed_files(dataset, db_session=mock_session)
        self.assertFalse("stops.txt" in result)

    class TestCreatePipelineTasks(unittest.TestCase):
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
        @patch("tasks.create_http_pmtiles_builder_task")
        @patch("tasks.create_http_reverse_geolocation_processor_task")
        @patch("tasks.has_file_changed")
        def test_pipeline_creates_tasks_when_changed_and_sizes_ok(
            self,
            mock_has_changed,
            mock_rev_geo_task,
            mock_pmtiles_task,
        ):
            # Both files changed
            mock_has_changed.side_effect = lambda dataset, fname, db_session: True

            dataset = SimpleDataset(
                feed_id=1,
                dataset_id=10,
                feed_stable_id="feed-A",
                dataset_stable_id="ds-1",
                files=[
                    SimpleFile(
                        "stops.txt",
                        hosted_url="https://x.com/stops.txt",
                        file_hash="s1",
                    ),
                    SimpleFile("routes.txt", file_size_bytes=250_000, file_hash="r1"),
                ],
            )

            # Bypass decorator by calling __wrapped__, supply a mock db_session
            mock_session = MagicMock()
            create_pipeline_tasks(dataset, db_session=mock_session)

            mock_rev_geo_task.assert_called_once_with(
                "feed-A", "ds-1", "https://x.com/stops.txt"
            )
            mock_pmtiles_task.assert_called_once_with("feed-A", "ds-1")

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
        @patch("tasks.create_http_pmtiles_builder_task")
        @patch("tasks.create_http_reverse_geolocation_processor_task")
        @patch("tasks.has_file_changed")
        def test_pipeline_skips_when_not_changed(
            self,
            mock_has_changed,
            mock_rev_geo_task,
            mock_pmtiles_task,
        ):
            # No files changed
            mock_has_changed.return_value = False

            dataset = SimpleDataset(
                feed_id=1,
                dataset_id=10,
                feed_stable_id="feed-B",
                dataset_stable_id="ds-2",
                files=[
                    SimpleFile(
                        "stops.txt",
                        hosted_url="https://x.com/stops.txt",
                        file_hash="same",
                    ),
                    SimpleFile("routes.txt", file_size_bytes=250_000, file_hash="same"),
                ],
            )

            mock_session = MagicMock()
            create_pipeline_tasks(dataset, db_session=mock_session)

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
        @patch("tasks.logging.info")
        @patch("tasks.create_http_pmtiles_builder_task")
        @patch("tasks.has_file_changed", return_value=True)
        def test_pipeline_routes_size_edges(
            self,
            mock_has_changed,
            mock_pmtiles_task,
            mock_log_info,
        ):
            # size == 0 → skip pmtiles
            dataset_zero = SimpleDataset(
                feed_id=1,
                dataset_id=11,
                feed_stable_id="feed-C",
                dataset_stable_id="ds-3",
                files=[
                    SimpleFile(
                        "stops.txt", hosted_url="https://x.com/stops.txt", file_hash="s"
                    ),
                    SimpleFile("routes.txt", file_size_bytes=0, file_hash="r"),
                ],
            )
            mock_session = MagicMock()
            create_pipeline_tasks(dataset_zero, db_session=mock_session)
            mock_pmtiles_task.assert_not_called()

            # size >= 1_000_000 → skip pmtiles + log info
            mock_pmtiles_task.reset_mock()
            dataset_large = SimpleDataset(
                feed_id=1,
                dataset_id=12,
                feed_stable_id="feed-D",
                dataset_stable_id="ds-4",
                files=[
                    SimpleFile(
                        "stops.txt", hosted_url="https://x.com/stops.txt", file_hash="s"
                    ),
                    SimpleFile("routes.txt", file_size_bytes=1_000_000, file_hash="r"),
                ],
            )
            create_pipeline_tasks(dataset_large, db_session=mock_session)
            mock_pmtiles_task.assert_not_called()
            self.assertTrue(mock_log_info.called)
            msg = mock_log_info.call_args[0][0]
            self.assertIn("Skipping PMTiles task", msg)
            self.assertIn("ds-4", msg)
            self.assertIn("routes.txt size", msg)

            # size in (0, 1_000_000) and changed → create pmtiles
            mock_pmtiles_task.reset_mock()
            dataset_ok = SimpleDataset(
                feed_id=1,
                dataset_id=13,
                feed_stable_id="feed-E",
                dataset_stable_id="ds-5",
                files=[
                    SimpleFile(
                        "stops.txt", hosted_url="https://x.com/stops.txt", file_hash="s"
                    ),
                    SimpleFile("routes.txt", file_size_bytes=999_999, file_hash="r"),
                ],
            )
            create_pipeline_tasks(dataset_ok, db_session=mock_session)
            mock_pmtiles_task.assert_called_once_with("feed-E", "ds-5")
