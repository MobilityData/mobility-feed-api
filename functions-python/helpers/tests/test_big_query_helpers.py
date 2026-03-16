import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from big_query_helpers import (
    chunked,
    collect_blobs_and_uris,
    make_staging_table_ref,
    ensure_staging_table_like_target,
    load_uris_into_staging,
    publish_staging_to_target,
    cleanup_success,
    cleanup_failure,
)


class DummyTableReference:
    def __init__(self, project: str, dataset_id: str, table_id: str):
        self.project = project
        self.dataset_id = dataset_id
        self.table_id = table_id


class DummyDatasetReference:
    def __init__(self, project: str, dataset_id: str):
        self.project = project
        self.dataset_id = dataset_id

    def table(self, table_id: str) -> DummyTableReference:
        return DummyTableReference(self.project, self.dataset_id, table_id)


class TestChunked(unittest.TestCase):
    def test_chunked_returns_expected_batches(self):
        items = ["a", "b", "c", "d", "e"]
        result = list(chunked(items, 2))
        self.assertEqual(result, [["a", "b"], ["c", "d"], ["e"]])


class TestCollectBlobsAndUris(unittest.TestCase):
    def test_collect_blobs_and_uris_success(self):
        storage_client = MagicMock()
        blob_one = SimpleNamespace(name="folder/file-one")
        blob_two = SimpleNamespace(name="folder/file-two")
        storage_client.list_blobs.return_value = [blob_one, blob_two]

        blobs, uris = collect_blobs_and_uris(storage_client, "bucket", "prefix/")

        storage_client.list_blobs.assert_called_once_with("bucket", prefix="prefix/")
        self.assertEqual(blobs, [blob_one, blob_two])
        self.assertEqual(
            uris,
            [
                "gs://bucket/folder/file-one",
                "gs://bucket/folder/file-two",
            ],
        )

    def test_collect_blobs_and_uris_failure(self):
        storage_client = MagicMock()
        storage_client.list_blobs.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            collect_blobs_and_uris(storage_client, "bucket", "prefix")


class TestMakeStagingTableRef(unittest.TestCase):
    @patch("big_query_helpers.bigquery.DatasetReference")
    @patch("big_query_helpers.time.time", return_value=1_700_000_000)
    def test_make_staging_table_ref_uses_dataset(self, mock_time, mock_dataset_ref):
        dataset_ref_instance = DummyDatasetReference("proj", "dataset")
        mock_dataset_ref.return_value = dataset_ref_instance
        target_ref = DummyTableReference("proj", "dataset", "table")

        staging_ref = make_staging_table_ref(target_ref)

        mock_dataset_ref.assert_called_once_with("proj", "dataset")
        self.assertIsInstance(staging_ref, DummyTableReference)
        self.assertEqual(staging_ref.project, "proj")
        self.assertEqual(staging_ref.dataset_id, "dataset")
        self.assertEqual(staging_ref.table_id, "table__staging_1700000000")


class TestEnsureStagingTableLikeTarget(unittest.TestCase):
    @patch("big_query_helpers.bigquery.Table")
    def test_ensure_staging_table_like_target(self, mock_table_cls):
        client = MagicMock()
        target_ref = MagicMock()
        staging_ref = MagicMock()
        target_table = MagicMock()
        target_table.schema = ["schema"]
        target_table.time_partitioning = SimpleNamespace(value="tp")
        target_table.range_partitioning = SimpleNamespace(value="rp")
        target_table.clustering_fields = ["cluster_a"]
        client.get_table.return_value = target_table

        staging_table = SimpleNamespace(
            time_partitioning=None,
            range_partitioning=None,
            clustering_fields=None,
        )
        mock_table_cls.return_value = staging_table

        ensure_staging_table_like_target(client, target_ref, staging_ref)

        client.get_table.assert_called_once_with(target_ref)
        mock_table_cls.assert_called_once_with(staging_ref, schema=["schema"])
        self.assertEqual(
            staging_table.time_partitioning, target_table.time_partitioning
        )
        self.assertEqual(
            staging_table.range_partitioning, target_table.range_partitioning
        )
        self.assertEqual(
            staging_table.clustering_fields, target_table.clustering_fields
        )
        client.create_table.assert_called_once_with(staging_table, exists_ok=True)


class TestLoadUrisIntoStaging(unittest.TestCase):
    @patch("big_query_helpers.LoadJobConfig")
    def test_load_uris_into_staging_batches_and_write_modes(self, mock_load_job_config):
        client = MagicMock()
        staging_ref = MagicMock()
        uris = ["uri-1", "uri-2", "uri-3"]
        job_first = MagicMock()
        job_second = MagicMock()
        client.load_table_from_uri.side_effect = [job_first, job_second]
        client.get_table.return_value = MagicMock(num_rows=3)

        mock_load_job_config.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)

        write_disposition = SimpleNamespace(
            WRITE_TRUNCATE="TRUNCATE", WRITE_APPEND="APPEND"
        )
        source_format = SimpleNamespace(NEWLINE_DELIMITED_JSON="JSON")

        with patch("big_query_helpers.MAX_URIS_PER_JOB", 2), patch(
            "big_query_helpers.bigquery.WriteDisposition", write_disposition
        ), patch("big_query_helpers.SourceFormat", source_format):
            load_uris_into_staging(client, staging_ref, uris)

        self.assertEqual(client.load_table_from_uri.call_count, 2)
        first_call = client.load_table_from_uri.call_args_list[0]
        second_call = client.load_table_from_uri.call_args_list[1]
        self.assertEqual(first_call.args[0], ["uri-1", "uri-2"])
        self.assertEqual(second_call.args[0], ["uri-3"])
        self.assertEqual(first_call.kwargs["job_config"].write_disposition, "TRUNCATE")
        self.assertEqual(second_call.kwargs["job_config"].write_disposition, "APPEND")
        job_first.result.assert_called_once()
        job_second.result.assert_called_once()
        client.get_table.assert_called_once_with(staging_ref)


class TestPublishStagingToTarget(unittest.TestCase):
    @patch("big_query_helpers.CopyJobConfig")
    def test_publish_staging_to_target(self, mock_copy_job_config):
        client = MagicMock()
        staging_ref = MagicMock()
        target_ref = MagicMock()
        copy_job = MagicMock()
        client.copy_table.return_value = copy_job
        config_instance = SimpleNamespace()
        mock_copy_job_config.return_value = config_instance

        write_disposition = SimpleNamespace(WRITE_TRUNCATE="TRUNCATE")
        with patch("big_query_helpers.bigquery.WriteDisposition", write_disposition):
            publish_staging_to_target(client, staging_ref, target_ref)

        mock_copy_job_config.assert_called_once_with(write_disposition="TRUNCATE")
        client.copy_table.assert_called_once_with(
            sources=staging_ref, destination=target_ref, job_config=config_instance
        )
        copy_job.result.assert_called_once()


class TestCleanup(unittest.TestCase):
    def test_cleanup_success_removes_table_and_blobs(self):
        client = MagicMock()
        staging_ref = MagicMock()
        blob_one = MagicMock()
        blob_two = MagicMock()

        cleanup_success(client, staging_ref, [blob_one, blob_two])

        client.delete_table.assert_called_once_with(staging_ref, not_found_ok=True)
        blob_one.delete.assert_called_once_with()
        blob_two.delete.assert_called_once_with()

    def test_cleanup_failure_swallows_exceptions(self):
        client = MagicMock()
        staging_ref = MagicMock()
        client.delete_table.side_effect = RuntimeError("failed")

        cleanup_failure(client, staging_ref)

        client.delete_table.assert_called_once_with(staging_ref, not_found_ok=True)
