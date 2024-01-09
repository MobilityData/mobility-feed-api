import json

from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders
from database.database import Database
from database_gen.sqlacodegen_models import Feed, Externalid, Location, Gtfsdataset

redirect_target_id = "test_target_id"
redirect_comment = "Some comment"
expected_redirect_response = {"target_id": redirect_target_id, "comment": redirect_comment}


def check_redirect(response: dict):
    assert (
        response["redirects"][0] == expected_redirect_response
    ), f'Response feed redirect was {response["redirects"][0]} instead of {expected_redirect_response}'


def test_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_select = mocker.patch.object(Database(), "select")

    mock_feed = Feed(stable_id="test_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_select.return_value = [[(mock_feed, redirect_target_id, mock_external_id, redirect_comment)]]
    response = client.request(
        "GET",
        "/v1/feeds",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feed = response.json()[0]
    assert response_feed["id"] == "test_id", f"Response feed id was {response_feed.id} instead of test_id"
    assert (
        response_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_feed["external_ids"][0]["external_id"]} instead of test_associated_id'
    assert (
        response_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_feed["external_ids"][0]["source"]} instead of test_source'
    check_redirect(response_feed)


def test_feed_get(client: TestClient, mocker):
    """
    Unit test for get_feeds
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_select.return_value = [[(mock_feed, redirect_target_id, mock_external_id, redirect_comment)]]

    response = client.request(
        "GET",
        "/v1/feeds/test_id",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_feed = response.json()
    assert response_feed["id"] == "test_id", f"Response feed id was {response_feed.id} instead of test_id"
    assert (
        response_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_feed["external_ids"][0]["external_id"]} instead of test_associated_id'
    assert (
        response_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_feed["external_ids"][0]["source"]} instead of test_source'

    check_redirect(response_feed)


def test_gtfs_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feeds
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_latest_datasets = Gtfsdataset(stable_id="test_latest_dataset_id", hosted_url="test_hosted_url", latest=True)
    mock_locations = Location(
        id="test_location_id",
        country_code="test_country_code",
        subdivision_name="test_subdivision_name",
        municipality="test_municipality",
    )
    mock_bounding_box = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [-70.248666, 43.655373],
                    [-70.248666, 43.71619],
                    [-70.11018, 43.71619],
                    [-70.11018, 43.655373],
                    [-70.248666, 43.655373],
                ]
            ],
        }
    )
    mock_select.return_value = [
        [
            (
                mock_feed,
                redirect_target_id,
                mock_external_id,
                redirect_comment,
                mock_latest_datasets,
                mock_bounding_box,
                mock_locations,
            )
        ]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_feeds",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_feed = response.json()[0]
    assert (
        response_gtfs_feed["id"] == "test_gtfs_id"
    ), f"Response feed id was {response_gtfs_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_gtfs_feed["external_ids"][0]["external_id"]} \
        instead of test_associated_id'
    assert (
        response_gtfs_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_gtfs_feed["external_ids"][0]["source"]} instead of test_source'
    check_redirect(response_gtfs_feed)
    assert (
        response_gtfs_feed["locations"][0]["country_code"] == "test_country_code"
    ), f'Response feed country code was {response_gtfs_feed["locations"][0]["country_code"]} \
        instead of test_country_code'
    assert (
        response_gtfs_feed["locations"][0]["subdivision_name"] == "test_subdivision_name"
    ), f'Response feed subdivision name was {response_gtfs_feed["locations"][0]["subdivision_name"]} \
        instead of test_subdivision_name'
    assert (
        response_gtfs_feed["locations"][0]["municipality"] == "test_municipality"
    ), f'Response feed municipality was {response_gtfs_feed["locations"][0]["municipality"]} \
        instead of test_municipality'
    assert (
        response_gtfs_feed["latest_dataset"]["id"] == "test_latest_dataset_id"
    ), f'Response feed latest dataset id was {response_gtfs_feed["latest_dataset"]["id"]} \
        instead of test_latest_dataset_id'
    assert (
        response_gtfs_feed["latest_dataset"]["hosted_url"] == "test_hosted_url"
    ), f'Response feed hosted url was {response_gtfs_feed["latest_dataset"]["hosted_url"]} \
        instead of test_hosted_url'


def test_gtfs_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_feed
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_latest_datasets = Gtfsdataset(stable_id="test_latest_dataset_id", hosted_url="test_hosted_url", latest=True)
    mock_locations = Location(
        id="test_location_id",
        country_code="test_country_code",
        subdivision_name="test_subdivision_name",
        municipality="test_municipality",
    )
    mock_bounding_box = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [-70.248666, 43.655373],
                    [-70.248666, 43.71619],
                    [-70.11018, 43.71619],
                    [-70.11018, 43.655373],
                    [-70.248666, 43.655373],
                ]
            ],
        }
    )
    mock_select.return_value = [
        [
            (
                mock_feed,
                redirect_target_id,
                mock_external_id,
                redirect_comment,
                mock_latest_datasets,
                mock_bounding_box,
                mock_locations,
            )
        ]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_feeds/test_gtfs_id",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_feed = response.json()
    assert (
        response_gtfs_feed["id"] == "test_gtfs_id"
    ), f"Response feed id was {response_gtfs_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_gtfs_feed["external_ids"][0]["external_id"]} \
        instead of test_associated_id'
    assert (
        response_gtfs_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_gtfs_feed["external_ids"][0]["source"]} instead of test_source'

    check_redirect(response_gtfs_feed)

    assert (
        response_gtfs_feed["locations"][0]["country_code"] == "test_country_code"
    ), f'Response feed country code was {response_gtfs_feed["locations"][0]["country_code"]} \
        instead of test_country_code'
    assert (
        response_gtfs_feed["locations"][0]["subdivision_name"] == "test_subdivision_name"
    ), f'Response feed subdivision name was {response_gtfs_feed["locations"][0]["subdivision_name"]} \
        instead of test_subdivision_name'
    assert (
        response_gtfs_feed["locations"][0]["municipality"] == "test_municipality"
    ), f'Response feed municipality was {response_gtfs_feed["locations"][0]["municipality"]} \
        instead of test_municipality'
    assert (
        response_gtfs_feed["latest_dataset"]["id"] == "test_latest_dataset_id"
    ), f'Response feed latest dataset id was {response_gtfs_feed["latest_dataset"]["id"]} \
        instead of test_latest_dataset_id'
    assert (
        response_gtfs_feed["latest_dataset"]["hosted_url"] == "test_hosted_url"
    ), f'Response feed hosted url was {response_gtfs_feed["latest_dataset"]["hosted_url"]} \
        instead of test_hosted_url'


def test_gtfs_rt_feeds_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feeds
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_rt_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_entity_types = "test_entity_type"
    mock_feed_references = "test_feed_reference"
    mock_select.return_value = [
        [(mock_feed, redirect_target_id, mock_external_id, redirect_comment, mock_entity_types, mock_feed_references)]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_rt_feed = response.json()[0]
    assert (
        response_gtfs_rt_feed["id"] == "test_gtfs_rt_id"
    ), f"Response feed id was {response_gtfs_rt_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_rt_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_gtfs_rt_feed["external_ids"][0]["external_id"]} \
        instead of test_associated_id'
    assert (
        response_gtfs_rt_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_gtfs_rt_feed["external_ids"][0]["source"]} instead of test_source'

    check_redirect(response_gtfs_rt_feed)

    assert (
        response_gtfs_rt_feed["entity_types"][0] == "test_entity_type"
    ), f'Response feed entity type was {response_gtfs_rt_feed["entity_types"][0]} instead of test_entity_type'
    assert (
        response_gtfs_rt_feed["feed_references"][0] == "test_feed_reference"
    ), f'Response feed feed reference was {response_gtfs_rt_feed["feed_references"][0]} instead of test_feed_reference'


def test_gtfs_rt_feed_get(client: TestClient, mocker):
    """
    Unit test for get_gtfs_rt_feed
    """
    mock_select = mocker.patch.object(Database(), "select")
    mock_feed = Feed(stable_id="test_gtfs_rt_id")
    mock_external_id = Externalid(associated_id="test_associated_id", source="test_source")
    mock_entity_types = "test_entity_type"
    mock_feed_references = "test_feed_reference"
    mock_select.return_value = [
        [(mock_feed, redirect_target_id, mock_external_id, redirect_comment, mock_entity_types, mock_feed_references)]
    ]

    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/test_gtfs_id",
        headers=authHeaders,
    )

    assert mock_select.call_count == 1, f"select() was called {mock_select.call_count} times instead of 3 times"
    assert response.status_code == 200, f"Response status code was {response.status_code} instead of 200"
    response_gtfs_rt_feed = response.json()
    assert (
        response_gtfs_rt_feed["id"] == "test_gtfs_rt_id"
    ), f"Response feed id was {response_gtfs_rt_feed.id} instead of test_gtfs_id"
    assert (
        response_gtfs_rt_feed["external_ids"][0]["external_id"] == "test_associated_id"
    ), f'Response feed external id was {response_gtfs_rt_feed["external_ids"][0]["external_id"]} \
        instead of test_associated_id'
    assert (
        response_gtfs_rt_feed["external_ids"][0]["source"] == "test_source"
    ), f'Response feed source was {response_gtfs_rt_feed["external_ids"][0]["source"]} instead of test_source'

    check_redirect(response_gtfs_rt_feed)

    assert (
        response_gtfs_rt_feed["entity_types"][0] == "test_entity_type"
    ), f'Response feed entity type was {response_gtfs_rt_feed["entity_types"][0]} instead of test_entity_type'
    assert (
        response_gtfs_rt_feed["feed_references"][0] == "test_feed_reference"
    ), f'Response feed feed reference was {response_gtfs_rt_feed["feed_references"][0]} instead of test_feed_reference'
