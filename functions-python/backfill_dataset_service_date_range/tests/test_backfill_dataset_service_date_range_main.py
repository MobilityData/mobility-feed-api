from unittest.mock import patch, Mock, MagicMock
from main import backfill_datasets, backfill_dataset_service_date_range, is_version_gte
from shared.database_gen.sqlacodegen_models import Gtfsdataset
from test_shared.test_utils.database_utils import default_db_url
from datetime import datetime, timezone

import requests

import os


def version_compare():
    assert not is_version_gte("6.0.0", "1")
    assert not is_version_gte("6.0.0", "1.1")
    assert not is_version_gte("6.0.0", "1.1.1")
    assert is_version_gte("6.0.0", "6.0.0-SNAPSHOT")
    assert is_version_gte("6.0.0", "6.0.2")
    assert is_version_gte("6.0.0", "6.1.0")
    assert is_version_gte("6.0.0", "10.1.0-SNAPSHOT")


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets(mock_get, mock_storage_client):
    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_session = MagicMock()
    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validator_version="6.0.0",
            validated_at="2022-01-01T00:00:00Z",
            json_report="http://example-2.com/report.json",
        ),
        MagicMock(
            validator_version="5.0.0",
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://example-3.com/report.json",
        ),
        MagicMock(
            validator_version="6.0.0",
            validated_at="2024-01-01T00:00:00Z",
            json_report="http://example-1.com/report.json",
        ),
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "summary": {
            "feedInfo": {
                "feedServiceWindowStart": "2023-01-01",
                "feedServiceWindowEnd": "2023-12-31",
            }
        }
    }
    mock_get.return_value = mock_response

    changes_count = backfill_datasets(mock_session)

    expected_range_start = datetime.strptime("2023-01-01", "%Y-%m-%d").replace(
        hour=0, minute=0, tzinfo=timezone.utc
    )
    expected_range_end = datetime.strptime("2023-12-31", "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    assert changes_count == 1
    assert mock_dataset.service_date_range_start == expected_range_start
    assert mock_dataset.service_date_range_end == expected_range_end
    mock_get.assert_called_once_with(
        "http://example-1.com/report.json"
    )  # latest validation report
    mock_session.commit.assert_called_once()


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets_service_date_range_swap(mock_get, mock_storage_client):
    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_session = MagicMock()
    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validator_version="6.0.0",
            validated_at="2022-01-01T00:00:00Z",
            json_report="http://example-2.com/report.json",
        ),
        MagicMock(
            validator_version="5.0.0",
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://example-3.com/report.json",
        ),
        MagicMock(
            validator_version="6.0.0",
            validated_at="2024-01-01T00:00:00Z",
            json_report="http://example-1.com/report.json",
        ),
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "summary": {
            "feedInfo": {
                "feedServiceWindowStart": "2023-12-31",
                "feedServiceWindowEnd": "2023-01-01",
            }
        }
    }
    mock_get.return_value = mock_response

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 1

    expected_range_start = datetime.strptime("2023-01-01", "%Y-%m-%d").replace(
        hour=0, minute=0, tzinfo=timezone.utc
    )
    expected_range_end = datetime.strptime("2023-12-31", "%Y-%m-%d").replace(
        hour=23, minute=59, tzinfo=timezone.utc
    )

    assert mock_dataset.service_date_range_start == expected_range_start
    assert mock_dataset.service_date_range_end == expected_range_end
    mock_get.assert_called_once_with(
        "http://example-1.com/report.json"
    )  # latest validation report
    mock_session.commit.assert_called_once()


@patch("logging.error", autospec=True)
@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets_error_commit(mock_get, mock_storage_client, mock_logger):
    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_session = MagicMock()
    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validator_version="6.0.0",
            validated_at="2022-01-01T00:00:00Z",
            json_report="http://example-2.com/report.json",
        )
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query
    mock_session.commit.side_effect = Exception("Commit failed")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "summary": {
            "feedInfo": {
                "feedServiceWindowStart": "2023-01-01",
                "feedServiceWindowEnd": "2023-12-31",
            }
        }
    }
    mock_get.return_value = mock_response

    try:
        backfill_datasets(mock_session)
    except Exception:
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets_no_validation_reports(mock_get, mock_storage_client):
    # Mock the session and query
    mock_session = MagicMock()

    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = []

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 0
    mock_session.commit.assert_called_once()


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets_invalid_json(mock_get, mock_storage_client):
    mock_session = MagicMock()

    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://example.com/report.json",
        )
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "wrong1": {"wrong2": {"wrong3": "2023-01-01", "wrong": "2023-12-31"}}
    }
    mock_get.return_value = mock_response

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 0
    mock_session.commit.assert_called_once()


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_invalid_validation_report_values(mock_get, mock_storage_client):
    mock_session = MagicMock()

    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validator_version="6.0.0",
            validated_at="2024-01-01T00:00:00Z",
            json_report="http://example-1.com/report.json",
        ),
    ]

    mock_dataset_2 = Mock(spec=Gtfsdataset)
    mock_dataset_2.id = 2
    mock_dataset_2.stable_id = "mdb-2-202406181921"
    mock_dataset_2.service_date_range_end = None
    mock_dataset_2.service_date_range_start = None
    mock_dataset_2.validation_reports = [
        MagicMock(
            validator_version="6.0.0",
            validated_at="2024-01-01T00:00:00Z",
            json_report="http://example-3.com/report.json",
        ),
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset, mock_dataset_2]
    mock_session.query.return_value = mock_query

    mock_get.side_effect = [
        MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "feedInfo": {
                        "feedServiceWindowStart": "",
                        "feedServiceWindowEnd": "2023-12-31",
                    }
                }
            },
        ),
        MagicMock(
            status_code=200,
            json=lambda: {
                "summary": {
                    "feedInfo": {
                        "feedServiceWindowStart": "2023-01-01",
                        "feedServiceWindowEnd": "",
                    }
                }
            },
        ),
    ]

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 0


@patch("google.cloud.storage.Client", autospec=True)
@patch("requests.get")
def test_backfill_datasets_fail_to_get_validation_report(mock_get, mock_storage_client):
    mock_session = MagicMock()

    # Mock the storage client and bucket
    mock_bucket = MagicMock()
    mock_client_instance = mock_storage_client.return_value
    mock_client_instance.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_bucket.blob.return_value = mock_blob

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.stable_id = "mdb-392-202406181921"
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://missing.com/report.json",
        )
    ]

    mock_query = MagicMock()
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [mock_dataset]
    mock_session.query.return_value = mock_query

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 500
    mock_get.side_effect = requests.exceptions.RequestException("URL not found")

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 0
    mock_get.assert_called_once_with("http://missing.com/report.json")
    mock_session.commit.assert_called_once()


@patch("main.Logger", autospec=True)
@patch("main.backfill_datasets")
def test_backfill_dataset_service_date_range(mock_backfill_datasets, mock_logger):
    mock_backfill_datasets.return_value = 5

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = backfill_dataset_service_date_range(None)

    mock_backfill_datasets.asser_called_once()
    assert response_body == "Script executed successfully. 5 datasets updated"
    assert status_code == 200


@patch("main.Logger", autospec=True)
@patch("main.backfill_datasets")
def test_backfill_dataset_service_date_range_error_raised(
    mock_backfill_datasets, mock_logger
):
    mock_backfill_datasets.side_effect = Exception("Mocked exception")

    with patch.dict(os.environ, {"FEEDS_DATABASE_URL": default_db_url}):
        response_body, status_code = backfill_dataset_service_date_range(None)

    mock_backfill_datasets.asser_called_once()
    assert (
        response_body
        == "Error setting the datasets service date range values: Mocked exception"
    )
    assert status_code == 500
