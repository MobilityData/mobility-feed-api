import pytest
from unittest.mock import patch, Mock, MagicMock
from sqlalchemy.orm import Session
from main import backfill_datasets
from shared.database_gen.sqlacodegen_models import Gtfsdataset

import logging
import json
import requests

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
        MagicMock(validated_at="2022-01-01T00:00:00Z", json_report="http://example-2.com/report.json"),
        MagicMock(validated_at="2023-01-01T00:00:00Z", json_report="http://example-3.com/report.json"),
        MagicMock(validated_at="2024-01-01T00:00:00Z", json_report="http://example-1.com/report.json")
    ]
   
    mock_query.filter.return_value = [mock_dataset]

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "summary": {
            "feedInfo": {
                "feedStartDate": "2023-01-01",
                "feedEndDate": "2023-12-31"
            }
        }
    }
    mock_get.return_value = mock_response

    changes_count = backfill_datasets(mock_session)

    assert changes_count == 1
    assert mock_dataset.service_date_range_start == "2023-01-01"
    assert mock_dataset.service_date_range_end == "2023-12-31"
    mock_get.assert_called_once_with("http://example-1.com/report.json") # latest validation report
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
        MagicMock(validated_at="2023-01-01T00:00:00Z", json_report="http://example.com/report.json")
    ]
   
    mock_query.filter.return_value = [mock_dataset]

    # Mock the requests.get response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "wrong": {
            "wrong": {
                "wrong": "2023-01-01",
                "wrong": "2023-12-31"
            }
        }
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
        MagicMock(validated_at="2023-01-01T00:00:00Z", json_report="http://missing.com/report.json")
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