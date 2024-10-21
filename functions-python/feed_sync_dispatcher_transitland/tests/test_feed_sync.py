import pytest
from unittest.mock import Mock, patch
from requests import Session as RequestsSession
from sqlalchemy.orm import Session as DBSession
from feed_sync_dispatcher_transitland.src.main import TransitFeedSyncProcessor
import pandas as pd


@pytest.fixture
def processor():
    return TransitFeedSyncProcessor()


@patch("feed_sync_dispatcher_transitland.src.main.requests.Session.get")
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


@patch("feed_sync_dispatcher_transitland.src.main.requests.Session.get")
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
    feeds_data = {
        "feeds": [
            {
                "id": "feed1",
                "urls": {"static_current": "http://example.com/feed1"},
                "spec": "gtfs",
                "onestop_id": "onestop1",
                "authorization": {},
            }
        ]
    }
    result = processor.extract_feeds_data(feeds_data)
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
    mock_db_session.execute.return_value.fetchone.return_value = (1,)
    result = processor.check_external_id(mock_db_session, "onestop1", "TLD")
    assert result is True

    mock_db_session.execute.return_value.fetchone.return_value = None
    result = processor.check_external_id(mock_db_session, "onestop2", "TLD")
    assert result is False


def test_get_mbd_feed_url(processor):
    mock_db_session = Mock(spec=DBSession)
    mock_db_session.execute.return_value.fetchone.return_value = (
        "http://example.com/feed1",
    )
    result = processor.get_mbd_feed_url(mock_db_session, "onestop1", "TLD")
    assert result == "http://example.com/feed1"

    mock_db_session.execute.return_value.fetchone.return_value = None
    result = processor.get_mbd_feed_url(mock_db_session, "onestop2", "TLD")
    assert result is None


def test_process_sync_new_feed(processor):
    mock_db_session = Mock(spec=DBSession)
    feeds_data = {
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
    operators_data = {
        "operators": [
            {
                "name": "Operator 1",
                "feeds": [{"id": "feed1"}],
                "agencies": [{"places": [{"adm0_name": "USA"}]}],
            }
        ],
        "feeds": [],
    }

    processor.get_data = Mock(side_effect=[feeds_data, operators_data])

    processor.check_url_status = Mock(return_value=True)

    with patch.object(processor, "check_external_id", return_value=False):
        payloads = processor.process_sync(
            db_session=mock_db_session, execution_id="exec123"
        )
        assert len(payloads) == 1
        assert payloads[0].payload.payload_type == "new"
        assert payloads[0].payload.external_id == "onestop1"


def test_process_sync_updated_feed(processor):
    mock_db_session = Mock(spec=DBSession)
    feeds_data = {
        "feeds": [
            {
                "id": "feed1",
                "urls": {"static_current": "http://example.com/feed1_updated"},
                "spec": "gtfs",
                "onestop_id": "onestop1",
                "authorization": {},
            }
        ],
        "operators": [],
    }
    operators_data = {
        "operators": [
            {
                "name": "Operator 1",
                "feeds": [{"id": "feed1"}],
                "agencies": [{"places": [{"adm0_name": "USA"}]}],
            }
        ],
        "feeds": [],
    }

    processor.get_data = Mock(side_effect=[feeds_data, operators_data])

    processor.check_url_status = Mock(return_value=True)

    processor.check_external_id = Mock(return_value=True)

    processor.get_mbd_feed_url = Mock(return_value="http://example.com/feed1")

    payloads = processor.process_sync(
        db_session=mock_db_session, execution_id="exec123"
    )

    assert len(payloads) == 1
    assert payloads[0].payload.payload_type == "update"
    assert payloads[0].payload.external_id == "onestop1"


@patch("feed_sync_dispatcher_transitland.src.main.TransitFeedSyncProcessor.get_data")
def test_process_sync_unchanged_feed(mock_get_data, processor):
    mock_db_session = Mock(spec=DBSession)
    feeds_data = {
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
    operators_data = {
        "operators": [
            {
                "name": "Operator 1",
                "feeds": [{"id": "feed1"}],
                "agencies": [{"places": [{"adm0_name": "USA"}]}],
            }
        ],
        "feeds": [],
    }
    mock_get_data.side_effect = [feeds_data, operators_data]

    with patch.object(processor, "check_external_id", return_value=True), patch.object(
        processor, "get_mbd_feed_url", return_value="http://example.com/feed1"
    ):
        payloads = processor.process_sync(
            db_session=mock_db_session, execution_id="exec123"
        )
        assert (
            len(payloads) == 0
        )  # No payload should be created since feed hasn't changed


@patch("feed_sync_dispatcher_transitland.src.main.requests.head")
def test_check_url_status(mock_head, processor):
    mock_head.return_value.status_code = 200
    result = processor.check_url_status("http://example.com")
    assert result is True

    mock_head.return_value.status_code = 404
    result = processor.check_url_status("http://example.com")
    assert result is False


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