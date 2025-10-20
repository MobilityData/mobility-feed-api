import copy
from datetime import datetime
from unittest.mock import Mock
import json

from fastapi.testclient import TestClient

from feeds.impl.models.feed_impl import FeedImpl
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Externalid,
    Gtfsdataset,
    Redirectingid,
    Gtfsfeed,
    Gtfsrealtimefeed,
)
from shared.feed_filters.feed_filter import FeedFilter
from tests.test_utils.database import TEST_GTFS_FEED_STABLE_IDS, TEST_GTFS_RT_FEED_STABLE_ID
from tests.test_utils.token import authHeaders

target_feed = Feed(stable_id="test_target_id")
redirect_target_id = "test_target_id"
redirect_comment = "Some comment"
expected_redirect_response = {"target_id": redirect_target_id, "comment": redirect_comment}

mock_feed = Feed(
    stable_id="test_id",
    data_type="gtfs",
    status="active",
    provider="test_provider",
    feed_name="test_feed_name",
    created_at=datetime.fromisoformat("2023-07-10T22:06:00+00:00"),
    note="test_note",
    feed_contact_email="test_feed_contact_email",
    producer_url="test_producer_url",
    authentication_type="1",
    authentication_info_url="test_authentication_info_url",
    api_key_parameter_name="test_api_key_parameter_name",
    license_url="test_license_url",
    externalids=[
        Externalid(
            associated_id="test_associated_id",
            source="test_source",
        )
    ],
    redirectingids=[
        Redirectingid(
            source_id="source_id",
            target_id="test_target_id",
            redirect_comment="Some comment",
            target=Feed(stable_id="test_target_id"),
        )
    ],
)

expected_feed_response = json.loads(
    FeedImpl(
        id="test_id",
        data_type="gtfs",
        created_at="2023-07-10T22:06:00Z",
        status="active",
        provider="test_provider",
        feed_name="test_feed_name",
        note="test_note",
        feed_contact_email="test_feed_contact_email",
        source_info={
            "authentication_type": 1,
            "authentication_info_url": "test_authentication_info_url",
            "api_key_parameter_name": "test_api_key_parameter_name",
            "license_url": "test_license_url",
            "producer_url": "test_producer_url",
        },
        external_ids=[{"external_id": "test_associated_id", "source": "test_source"}],
        related_links=[],
        redirects=[{"comment": "Some comment", "target_id": "test_target_id"}],
    ).model_dump_json()
)


def check_redirect(response: dict):
    assert (
        response["redirects"][0] == expected_redirect_response
    ), f'Response feed redirect was {response["redirects"][0]} instead of {expected_redirect_response}'


def test_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    # Build the chain of calls to mimic what is done in impl.feeds_api_impl.FeedsApiImpl.get_feeds
    mock_filter = mocker.patch.object(FeedFilter, "filter")
    mock_filter_limit = Mock()
    mock_filter_offset = Mock()
    mock_filter_order_by = Mock()
    mock_options = Mock()
    mock_filter.return_value.filter.return_value.order_by.return_value = mock_filter_order_by
    mock_filter_order_by.options.return_value = mock_options
    mock_options.limit.return_value = mock_filter_limit
    mock_filter_limit.offset.return_value = mock_filter_offset
    # Target is set to None as deep copy is failing for unknown reasons
    # At the end of the test, the target is set back to the original value
    mock_feed.redirectingids[0].target = None
    mock_feed_2 = copy.deepcopy(mock_feed)
    # Target is set back to the original value
    mock_feed.redirectingids[0].target = target_feed
    mock_feed_2.stable_id = "test_id_2"
    mock_feed_2.redirectingids[0].target = target_feed
    mock_filter_offset.all.return_value = [mock_feed, mock_feed_2]

    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feeds = response.json()
    assert len(response_feeds) == 2, f"Response feeds length was {len(response_feeds)} instead of 2"
    assert (
        response_feeds[0] == expected_feed_response
    ), f"Response feed was {response_feeds[0]} instead of {expected_feed_response}"
    assert (
        response_feeds[1]["id"] == "test_id_2"
    ), f"Response feed id was {response_feeds[1]['id']} instead of test_id_2"


def test_feed_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_filter = mocker.patch.object(FeedFilter, "filter")
    mock_filter.return_value.filter.return_value.first.return_value = mock_feed

    response = client.request(
        "GET",
        "/v1/feeds/test_id",
        headers=authHeaders,
    )

    assert mock_filter.call_count == 1, (
        f"create_feed_filter() was called {mock_filter.call_count} times instead of 1 " f"time"
    )
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feed = response.json()

    assert (
        response_feed == expected_feed_response
    ), f"Response feed was {response_feed} instead of {expected_feed_response.dict()}"


def test_gtfs_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feeds
    """
    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        feed_mdb_10 = db.get_query_model(session, Gtfsfeed).filter(Gtfsfeed.stable_id == "mdb-10").first()
        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_feed = response.json()[0]
        assert_gtfs(feed_mdb_10, response_gtfs_feed)


def test_gtfs_feeds_get_no_bounding_box(client: TestClient, mocker):
    """
    Testing for issue #431 where latest_dataset would be None if bounding_box was None.
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_id")
    mock_latest_datasets = Gtfsdataset(stable_id="test_latest_dataset_id", hosted_url="test_hosted_url")

    mock_select.return_value = [
        [
            (
                mock_feed,
                None,  # redirect_id
                None,  # external_id
                None,  # redirect_comment
                mock_latest_datasets,
                None,  # Set the bounding_box to None
                None,  # locations
            )
        ]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
    )

    response_gtfs_feed = response.json()[0]
    assert response_gtfs_feed["latest_dataset"] is not None, "Response feed latest dataset was None"


def test_gtfs_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feed
    """
    response = client.request(
        "GET",
        f"/v1/gtfs_feeds/{TEST_GTFS_FEED_STABLE_IDS[0]}",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        gtfs_feed = (
            db.get_query_model(session, Gtfsfeed).filter(Gtfsfeed.stable_id == TEST_GTFS_FEED_STABLE_IDS[0]).first()
        )
        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_feed = response.json()
        assert_gtfs(gtfs_feed, response_gtfs_feed)


def test_gtfs_rt_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feeds
    """
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds",
        headers=authHeaders,
    )

    db = Database()
    with db.start_db_session() as session:
        gtfs_rt_feed = (
            db.get_query_model(session, Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == TEST_GTFS_RT_FEED_STABLE_ID)
            .first()
        )

        assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
        response_gtfs_rt_feed = response.json()[0]
        assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed)


def test_gtfs_rt_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feed
    """
    response = client.request(
        "GET",
        f"/v1/gtfs_rt_feeds/{TEST_GTFS_RT_FEED_STABLE_ID}",
        headers=authHeaders,
    )

    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_rt_feed = response.json()
    db = Database()
    with db.start_db_session() as session:
        gtfs_rt_feed = (
            db.get_query_model(session, Gtfsrealtimefeed)
            .filter(Gtfsrealtimefeed.stable_id == TEST_GTFS_RT_FEED_STABLE_ID)
            .first()
        )
        assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed)


def assert_gtfs(gtfs_feed, response_gtfs_feed):
    assert (
        response_gtfs_feed["id"] == gtfs_feed.stable_id
    ), f"Response feed id was {response_gtfs_feed['id']} instead of {gtfs_feed.stable_id}"
    assert (
        response_gtfs_feed["external_ids"][0]["external_id"]
        == sorted(gtfs_feed.externalids, key=lambda x: x.associated_id)[0].associated_id
    ), f'Response feed external id was {response_gtfs_feed["external_ids"][0]["external_id"]} \
        instead of {gtfs_feed.externalids[0].associated_id}'
    assert response_gtfs_feed["external_ids"][0]["source"] == gtfs_feed.externalids[0].source, (
        f'Response feed source was {response_gtfs_feed["external_ids"][0]["source"]} instead of '
        f"{gtfs_feed.externalids[0].source}"
    )
    assert (
        response_gtfs_feed["redirects"][0]["target_id"]
        == sorted(gtfs_feed.redirectingids, key=lambda x: x.target.stable_id)[0].target.stable_id
    ), (
        f'Response feed redirect was {response_gtfs_feed["redirects"][0]["target_id"]} instead of '
        f"{gtfs_feed.redirectingids[0].target.stable_id}"
    )
    assert (
        response_gtfs_feed["locations"][0]["country_code"] == gtfs_feed.locations[0].country_code
    ), f'Response feed country code was {response_gtfs_feed["locations"][0]["country_code"]} \
        instead of {gtfs_feed.locations[0].country_code}'
    assert (
        response_gtfs_feed["locations"][0]["subdivision_name"] == gtfs_feed.locations[0].subdivision_name
    ), f'Response feed subdivision name was {response_gtfs_feed["locations"][0]["subdivision_name"]} \
        instead of {gtfs_feed.locations[0].subdivision_name}'
    assert (
        response_gtfs_feed["locations"][0]["municipality"] == gtfs_feed.locations[0].municipality
    ), f'Response feed municipality was {response_gtfs_feed["locations"][0]["municipality"]} \
        instead of {gtfs_feed.locations[0].municipality}'
    # It seems the resulting are not always in the same order, so find the latest instead of using a hardcoded index
    # latest_dataset = next((dataset for dataset in gtfs_feed.gtfsdatasets if dataset.latest), None)
    if gtfs_feed.latest_dataset is not None:
        assert (
            response_gtfs_feed["latest_dataset"]["id"] == gtfs_feed.latest_dataset.stable_id
        ), f'Response feed latest dataset id was {response_gtfs_feed["latest_dataset"]["id"]} \
            instead of {gtfs_feed.latest_dataset.stable_id}'
    else:
        raise Exception("No latest dataset found")

    assert (
        response_gtfs_feed["latest_dataset"]["hosted_url"] == gtfs_feed.latest_dataset.hosted_url
    ), f'Response feed hosted url was {response_gtfs_feed["latest_dataset"]["hosted_url"]} \
        instead of test_hosted_url'
    assert response_gtfs_feed["latest_dataset"]["bounding_box"] is not None, "Response feed bounding_box was None"
    assert response_gtfs_feed["created_at"] is not None, "Response feed created_at was None"


def assert_gtfs_rt(gtfs_rt_feed, response_gtfs_rt_feed):
    assert (
        response_gtfs_rt_feed["id"] == gtfs_rt_feed.stable_id
    ), f"Response feed id was {response_gtfs_rt_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_rt_feed["external_ids"][0]["external_id"]
        == sorted(gtfs_rt_feed.externalids, key=lambda x: x.associated_id)[0].associated_id
    ), f'Response feed external id was {response_gtfs_rt_feed["external_ids"][0]["external_id"]} \
        instead of {gtfs_rt_feed.externalids[0].associated_id}'
    assert response_gtfs_rt_feed["external_ids"][0]["source"] == gtfs_rt_feed.externalids[0].source, (
        f'Response feed source was {response_gtfs_rt_feed["external_ids"][0]["source"]} instead of '
        f"{gtfs_rt_feed.externalids[0].source}"
    )
    assert (
        response_gtfs_rt_feed["redirects"][0]["target_id"]
        == sorted(gtfs_rt_feed.redirectingids, key=lambda x: x.target_id)[0].target.stable_id
    ), (
        f'Response feed redirect was {response_gtfs_rt_feed["redirects"][0]["target_id"]} instead of '
        f"{gtfs_rt_feed.redirectingids[0].target.stable_id}"
    )
    assert response_gtfs_rt_feed["entity_types"][0] == gtfs_rt_feed.entitytypes[0].name, (
        f'Response feed entity type was {response_gtfs_rt_feed["entity_types"][0]}'
        f"instead of {gtfs_rt_feed.entitytypes[0].name}"
    )
    assert (
        response_gtfs_rt_feed["feed_references"][0] == gtfs_rt_feed.gtfs_feeds[0].stable_id
    ), f'response feed feed reference was {response_gtfs_rt_feed["feed_references"][0]} instead of test_feed_reference'
    assert response_gtfs_rt_feed["created_at"] is not None, "Response feed created_at was None"
