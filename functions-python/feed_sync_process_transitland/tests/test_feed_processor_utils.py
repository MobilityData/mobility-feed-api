from unittest.mock import patch

import requests

from shared.database_gen.sqlacodegen_models import Gtfsfeed, Gtfsrealtimefeed
from feed_processor_utils import (
    check_url_status,
    get_feed_model,
    get_tlnd_authentication_type,
    create_new_feed,
)
from shared.helpers.database import configure_polymorphic_mappers
from shared.helpers.feed_sync.models import TransitFeedSyncPayload
from test_shared.test_utils.database_utils import default_db_url, get_testing_session


@patch("requests.head")
def test_check_url_status(mock_head):
    mock_head.return_value.status_code = 200
    assert check_url_status("http://example.com")
    mock_head.return_value.status_code = 404
    assert not check_url_status("http://example.com/404")
    mock_head.return_value.status_code = 403
    assert check_url_status("http://example.com/403")
    mock_head.side_effect = requests.RequestException("Error")
    assert not check_url_status("http://example.com/exception")


def test_get_feed_model():
    assert get_feed_model("gtfs") == (Gtfsfeed, "gtfs")
    assert get_feed_model("gtfs_rt") == (Gtfsrealtimefeed, "gtfs_rt")
    try:
        get_feed_model("invalid")
        assert False
    except ValueError:
        assert True


def test_get_tlnd_authentication_type() -> str:
    assert get_tlnd_authentication_type(None) == "0"
    assert get_tlnd_authentication_type("") == "0"
    assert get_tlnd_authentication_type("query_param") == "1"
    assert get_tlnd_authentication_type("header") == "2"
    try:
        get_tlnd_authentication_type("invalid")
        assert False
    except ValueError:
        assert True


@patch.dict("os.environ", {"FEEDS_DATABASE_URL": default_db_url})
def test_create_new_feed_gtfs_rt():
    payload = {
        "spec": "gtfs_rt",
        "entity_types": "tu",
        "feed_url": "http://example.com",
        "feed_id": "102_tu",
        "stable_id": "tld-102_tu",
        "type": "query_param",
        "auth_info_url": "http://example.com/info",
        "auth_param_name": "key",
        "operator_name": "Operator 1",
        "external_id": "onestop1",
        "source": "tld",
        "country": "USA",
        "state_province": "California",
        "city_name": "San Francisco",
    }
    feed_payload = TransitFeedSyncPayload(**payload)
    configure_polymorphic_mappers()
    session = get_testing_session()
    new_feed = create_new_feed(session, "tld-102_tu", feed_payload)
    session.delete(new_feed)
    assert new_feed.stable_id == "tld-102_tu"
    assert new_feed.data_type == "gtfs_rt"
    assert len(new_feed.entitytypes) == 1
