import unittest
from unittest.mock import patch

from main import (
    ingest_data_to_big_query_gtfs,
    ingest_data_to_big_query_gbfs,
)


class TestMain(unittest.TestCase):
    @patch("main.BigQueryDataTransferGTFS")
    @patch("helpers.logger.Logger.init_logger")
    @patch("main.logging.info")
    def test_ingest_data_to_big_query_gtfs(
        self, mock_logging_info, mock_init_logger, mock_big_query_transfer_gtfs
    ):
        mock_instance = mock_big_query_transfer_gtfs.return_value
        mock_instance.send_data_to_bigquery.return_value = (
            "Data successfully loaded to BigQuery",
            200,
        )

        response = ingest_data_to_big_query_gtfs(None)

        mock_init_logger.assert_called_once()
        mock_logging_info.assert_any_call("Function triggered")
        mock_instance.send_data_to_bigquery.assert_called_once()
        self.assertEqual(response, ("Data successfully loaded to BigQuery", 200))

    @patch("main.BigQueryDataTransferGBFS")
    @patch("helpers.logger.Logger.init_logger")
    @patch("main.logging.info")
    def test_ingest_data_to_big_query_gbfs(
        self, mock_logging_info, mock_init_logger, mock_biq_query_transfer_gbfs
    ):
        mock_instance = mock_biq_query_transfer_gbfs.return_value
        mock_instance.send_data_to_bigquery.return_value = (
            "Data successfully loaded to BigQuery",
            200,
        )

        response = ingest_data_to_big_query_gbfs(None)

        mock_init_logger.assert_called_once()
        mock_logging_info.assert_any_call("Function triggered")
        mock_instance.send_data_to_bigquery.assert_called_once()
        self.assertEqual(response, ("Data successfully loaded to BigQuery", 200))
