import pytest
from unittest.mock import Mock, patch, call
from requests import Session as RequestsSession
from sqlalchemy.orm import Session as DBSession

from database_gen.sqlacodegen_models import Gtfsfeed
from main import (
    TransitFeedSyncProcessor,
)
import pandas as pd
from requests.exceptions import HTTPError

from helpers.feed_sync.feed_sync_common import FeedSyncPayload


@pytest.fixture
def processor():
    return TransitFeedSyncProcessor()


@patch("main.requests.Session.get")
def test_get_data(mock_get, processor):
    mock_response = Mock()
    mock_response.json.return_value = {
        "feeds": [
            {
                "id": "feed1",
                "urls": {"static_current": "http://example.com/feed1"},
                "spec": "gtfs",
                "onestop_id": "onestop1",
                "authorization": {},
            }
        ],
        "operators": [],
    }
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    result = processor.get_data(
        "https://api.transit.land", "dummy_api_key", session=RequestsSession()
    )
    assert "feeds" in result
    assert result["feeds"][0]["id"] == "feed1"


@patch("main.requests.Session.get")
def test_get_data_rate_limit(mock_get, processor):
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"feeds": [], "operators": []}
    mock_get.return_value = mock_response

    result = processor.get_data(
        "https://api.transit.land",
        "dummy_api_key",
        session=RequestsSession(),
        max_retries=1,
    )
    assert result == {"feeds": [], "operators": []}


def test_extract_feeds_data(processor):
    feeds_data = [
        {
            "id": "feed1",
            "urls": {"static_current": "http://example.com"},
            "spec": "gtfs",
            "onestop_id": "onestop1",
            "authorization": {},
        }
    ]
    result = processor.extract_feeds_data(feeds_data, [])
    assert len(result) == 1
    assert result[0]["feed_id"] == "feed1"


def test_extract_operators_data(processor):
    operators_data = {
        "operators": [
            {
                "name": "Operator 1",
                "feeds": [{"id": "feed1"}],
                "agencies": [{"places": [{"adm0_name": "USA"}]}],
            }
        ]
    }
    result = processor.extract_operators_data(operators_data)
    assert len(result) == 1
    assert result[0]["operator_name"] == "Operator 1"


def test_check_external_id(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.query.return_value.filter.return_value.all.return_value = (1,)
    result = processor.check_external_id(mock_db_session, "onestop1", "TLD")
    assert result is True

    mock_db_session.query.return_value.filter.return_value.all.return_value = None
    result = processor.check_external_id(mock_db_session, "onestop2", "TLD")
    assert result is False


def test_get_mbd_feed_url(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.query.return_value.filter.return_value.all.return_value = [
        Gtfsfeed(producer_url="http://example.com/feed1")
    ]
    result = processor.get_mbd_feed_url(mock_db_session, "onestop1", "TLD")
    assert result == "http://example.com/feed1"

    mock_db_session.query.return_value.filter.return_value.all.return_value = None
    result = processor.get_mbd_feed_url(mock_db_session, "onestop2", "TLD")
    assert result is None


def test_process_sync_new_feed(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.query.return_value.all.return_value = []
    feeds_data = [
        {
            "id": "feed1",
            "urls": {"static_current": "http://example.com"},
            "spec": "gtfs",
            "onestop_id": "onestop1",
            "authorization": {},
        }
    ]
    operators_data = [
        {
            "name": "Operator 1",
            "feeds": [{"id": "feed1"}],
            "agencies": [{"places": [{"adm0_name": "USA"}]}],
        }
    ]
    processor.get_data = Mock(
        return_value={"feeds": feeds_data, "operators": operators_data}
    )
    processor.check_external_id = Mock(return_value=False)
    payloads = processor.process_sync(mock_db_session, "exec123")
    assert len(payloads) == 1, "Expected 1 payload"
    assert payloads[0].payload.payload_type == "new"


def test_process_sync_updated_feed(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.query.return_value.all.return_value = []
    feeds_data = [
        {
            "id": "feed1",
            "urls": {"static_current": "http://example.com"},
            "spec": "gtfs",
            "onestop_id": "onestop1",
            "authorization": {},
        }
    ]
    operators_data = [
        {
            "name": "Operator 1",
            "feeds": [{"id": "feed1"}],
            "agencies": [{"places": [{"adm0_name": "USA"}]}],
        }
    ]
    processor.get_data = Mock(
        return_value={"feeds": feeds_data, "operators": operators_data}
    )
    processor.check_external_id = Mock(return_value=True)
    processor.get_mbd_feed_url = Mock(return_value="http://example-2.com")
    payloads = processor.process_sync(mock_db_session, "exec123")
    assert len(payloads) == 1, "Expected 1 payload"
    assert payloads[0].payload.payload_type == "update"


def test_process_sync_unchanged_feed(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.query.return_value.all.return_value = []
    feeds_data = [
        {
            "id": "feed1",
            "urls": {"static_current": "http://example.com"},
            "spec": "gtfs",
            "onestop_id": "onestop1",
            "authorization": {},
        }
    ]
    operators_data = [
        {
            "name": "Operator 1",
            "feeds": [{"id": "feed1"}],
            "agencies": [{"places": [{"adm0_name": "USA"}]}],
        }
    ]
    processor.get_data = Mock(
        return_value={"feeds": feeds_data, "operators": operators_data}
    )
    processor.check_external_id = Mock(return_value=True)
    processor.get_mbd_feed_url = Mock(return_value="http://example.com")
    payloads = processor.process_sync(mock_db_session, "exec123")
    assert len(payloads) == 0, "No payloads expected"


def test_merge_and_filter_dataframes(processor):
    operators = [
        {
            "operator_name": "Operator 1",
            "operator_feed_id": "feed1",
            "country": "USA",
            "state_province": "CA",
            "city_name": "San Francisco",
        },
        {
            "operator_name": "Operator 2",
            "operator_feed_id": "feed2",
            "country": "Japan",
            "state_province": "Tokyo",
            "city_name": "Tokyo",
        },
    ]
    feeds = [
        {
            "feed_id": "feed1",
            "feed_url": "http://example.com/feed1",
            "spec": "gtfs",
            "feeds_onestop_id": "onestop1",
            "auth_info_url": None,
            "auth_param_name": None,
            "type": None,
        },
        {
            "feed_id": "feed2",
            "feed_url": "http://example.com/feed2",
            "spec": "gtfs",
            "feeds_onestop_id": "onestop2",
            "auth_info_url": None,
            "auth_param_name": None,
            "type": None,
        },
    ]

    operators_df = pd.DataFrame(operators)
    feeds_df = pd.DataFrame(feeds)

    combined_df = pd.merge(
        operators_df,
        feeds_df,
        left_on="operator_feed_id",
        right_on="feed_id",
        how="inner",
    )
    combined_df = combined_df[combined_df["feed_url"].notna()]
    countries_not_included = ["France", "Japan"]
    filtered_df = combined_df[
        ~combined_df["country"]
        .str.lower()
        .isin([c.lower() for c in countries_not_included])
    ]

    assert len(filtered_df) == 1
    assert filtered_df.iloc[0]["operator_name"] == "Operator 1"
    assert filtered_df.iloc[0]["feed_id"] == "feed1"


def test_publish_callback_success(processor):
    future = Mock()
    future.exception.return_value = None
    payload = FeedSyncPayload(external_id="onestop1", payload=None)
    topic_path = "projects/project-id/topics/topic-name"

    with patch("builtins.print") as mock_print:
        processor.publish_callback(future, payload, topic_path)
        mock_print.assert_called_with("Published transit land feed onestop1.")


def test_publish_callback_failure(processor):
    future = Mock()
    future.exception.return_value = Exception("Publish error")
    payload = FeedSyncPayload(external_id="onestop1", payload=None)
    topic_path = "projects/project-id/topics/topic-name"

    with patch("builtins.print") as mock_print:
        processor.publish_callback(future, payload, topic_path)
        mock_print.assert_called_with(
            f"Error publishing transit land feed onestop1 to Pub/Sub topic {topic_path}: Publish error"
        )


def test_get_data_retries(processor):
    # Mock the requests session
    mock_session = Mock(spec=RequestsSession)

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError()
    mock_response.status_code = 500

    mock_session.get.return_value = mock_response

    with patch("time.sleep", return_value=None) as mock_sleep:
        result = processor.get_data(
            url="http://example.com",
            api_key="dummy_api_key",
            session=mock_session,
            max_retries=3,
            initial_delay=1,
            max_delay=2,
        )

        assert mock_session.get.call_count == 3

        assert mock_sleep.call_count == 2

        mock_sleep.assert_has_calls([call(1), call(1)])

        assert result == {"feeds": [], "operators": []}
