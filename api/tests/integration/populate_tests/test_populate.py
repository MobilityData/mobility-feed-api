# coding: utf-8
import pytest
from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders

# Test the populate script. The assumption is that the populate script is called to populate the database for these
# tests, so we can check if certain behaviours are correct.


@pytest.mark.parametrize(
    "values",
    [
        {
            "feed_id": "mdb-40",
            "expected_official": True,
            "assert_fail_message": "mdb-40, changed is_official from TRUE to empty. Should retain True in the DB",
        },
        {
            "feed_id": "mdb-50",
            "expected_official": False,
            "assert_fail_message": "mdb-50, changed is_official from FALSE to empty. Should retain False in the DB",
        },
        {
            "feed_id": "mdb-1562",
            "expected_official": True,
            "assert_fail_message": "mdb-1562, changed is_official from FALSE to TRUE. Should change to True in the DB",
        },
        {
            "feed_id": "mdb-1563",
            "expected_official": False,
            "assert_fail_message": "mdb-1563, changed is_official from TRUE to FALSE. Should change to False in the DB",
        },
    ],
    ids=[
        "official_change_true_to_empty",
        "official_change_false_to_empty",
        "official_change_false_to_true",
        "official_change_true_to_false",
    ],
)
def test_is_official_overwrite(client: TestClient, values):
    """Test case for feeds_gtfs_id_get with a non-existent feed"""
    feed_id = values["feed_id"]
    expected_official = values["expected_official"]

    response = client.request(
        "GET",
        "/v1/feeds/{id}".format(id=feed_id),
        headers=authHeaders,
    )

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["official"] is expected_official, values["assert_fail_message"]


def test_is_feed_reference_overwrite(client: TestClient):
    feed_id = "mdb-1562"
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id=feed_id),
        headers=authHeaders,
    )
    json_response = response.json()
    assert json_response["feed_references"] == ["mdb-50"]

    feed_id = "mdb-1563"
    response = client.request(
        "GET",
        "/v1/gtfs_rt_feeds/{id}".format(id=feed_id),
        headers=authHeaders,
    )
    json_response = response.json()
    assert json_response["feed_references"] == ["mdb-50"]
