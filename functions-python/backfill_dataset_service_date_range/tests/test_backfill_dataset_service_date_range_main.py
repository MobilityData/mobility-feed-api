from unittest.mock import patch, Mock, MagicMock
from main import backfill_datasets, backfill_dataset_service_date_range
from shared.database_gen.sqlacodegen_models import Gtfsdataset
from test_shared.test_utils.database_utils import default_db_url

import requests

import os


@patch("requests.get")
def test_backfill_datasets(mock_get):
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_query.options.return_value = mock_query

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validated_at="2022-01-01T00:00:00Z",
            json_report="http://example-2.com/report.json",
        ),
        MagicMock(
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://example-3.com/report.json",
        ),
        MagicMock(
            validated_at="2024-01-01T00:00:00Z",
            json_report="http://example-1.com/report.json",
        ),
    ]

    mock_query.filter.return_value = [mock_dataset]

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

    assert changes_count == 1
    assert mock_dataset.service_date_range_start == "2023-01-01"
    assert mock_dataset.service_date_range_end == "2023-12-31"
    mock_get.assert_called_once_with(
        "http://example-1.com/report.json"
    )  # latest validation report
    mock_session.commit.assert_called_once()


@patch("requests.get")
def test_backfill_datasets_no_validation_reports(mock_get):
    # Mock the session and query
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_query.options.return_value = mock_query

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = []

    mock_query.filter.return_value = [mock_dataset]

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 0
    mock_session.commit.assert_called_once()


@patch("requests.get")
def test_backfill_datasets_invalid_json(mock_get):
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_query.options.return_value = mock_query

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://example.com/report.json",
        )
    ]

    mock_query.filter.return_value = [mock_dataset]

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


@patch("requests.get")
def test_backfill_datasets_fail_to_get_validation_report(mock_get):
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_query.options.return_value = mock_query

    mock_dataset = Mock(spec=Gtfsdataset)
    mock_dataset.id = 1
    mock_dataset.service_date_range_end = None
    mock_dataset.service_date_range_start = None
    mock_dataset.validation_reports = [
        MagicMock(
            validated_at="2023-01-01T00:00:00Z",
            json_report="http://missing.com/report.json",
        )
    ]

    mock_query.filter.return_value = [mock_dataset]

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
