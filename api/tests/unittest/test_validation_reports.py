from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders

ENDPOINT = "/v1/gtfs_feeds/mdb-1/validation_reports"


def get(client: TestClient, **params):
    response = client.request("GET", ENDPOINT, headers=authHeaders, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_one_entry_per_dataset(client: TestClient):
    """mdb-1 has two datasets, each with two reports: one entry each, not one per report."""
    body = get(client)

    assert body["feed_id"] == "mdb-1"
    assert body["total"] == 2
    assert {item["dataset_id"] for item in body["items"]} == {"dataset-1", "dataset-2"}
    assert sum(item["is_latest"] for item in body["items"]) == 1


def test_latest_is_the_feeds_current_dataset(client: TestClient):
    body = get(client)
    flagged = [item["dataset_id"] for item in body["items"] if item["is_latest"]]

    assert body["latest"]["is_latest"] is True
    assert flagged == [body["latest"]["dataset_id"]]


def test_notices_are_returned_with_counts(client: TestClient):
    """The notice codes behind the counts, which is what the error state is rendered from."""
    body = get(client)
    notices = [n for item in body["items"] for n in item["notices"]]

    assert notices, "the seeded feed has notices"
    assert all(n["severity"] in ("ERROR", "WARNING", "INFO") for n in notices)
    assert all(n["total"] > 0 for n in notices)
    assert all(n["code"] for n in notices)


def test_errors_are_listed_before_warnings(client: TestClient):
    body = get(client)
    for item in body["items"]:
        severities = [n["severity"] for n in item["notices"]]
        assert severities == sorted(severities, key=lambda s: ["ERROR", "WARNING", "INFO"].index(s))


def test_severity_filters_the_notices(client: TestClient):
    body = get(client, severity=["ERROR"])

    for item in body["items"]:
        assert all(n["severity"] == "ERROR" for n in item["notices"])


def test_severity_does_not_change_the_counts(client: TestClient):
    """The filter narrows what is listed, not what was found."""
    unfiltered = get(client)
    filtered = get(client, severity=["ERROR"])

    assert [i["total_warning"] for i in filtered["items"]] == [i["total_warning"] for i in unfiltered["items"]]


def test_min_errors_filters_entries(client: TestClient):
    body = get(client, min_errors=1)

    assert body["total"] <= 2
    assert all(item["total_error"] >= 1 for item in body["items"])


def test_min_errors_zero_keeps_everything(client: TestClient):
    assert get(client, min_errors=0)["total"] == 2


def test_latest_ignores_the_filters(client: TestClient):
    """The headline entry is the feed's current dataset whatever was asked for."""
    body = get(client, min_errors=1000000)

    assert body["items"] == []
    assert body["latest"] is not None
    assert body["latest"]["is_latest"] is True


def test_validated_before_excludes_everything(client: TestClient):
    body = get(client, validated_before="2000-01-01T00:00:00Z")

    assert body["total"] == 0
    assert body["items"] == []


def test_paging(client: TestClient):
    body = get(client, limit=1, offset=0)

    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["total"] == 2
    assert len(body["items"]) == 1


def test_invalid_date_is_rejected(client: TestClient):
    response = client.request("GET", ENDPOINT, headers=authHeaders, params={"validated_after": "not-a-date"})
    assert response.status_code == 422


def test_inverted_range_is_rejected(client: TestClient):
    response = client.request(
        "GET",
        ENDPOINT,
        headers=authHeaders,
        params={"validated_after": "2026-01-01T00:00:00Z", "validated_before": "2025-01-01T00:00:00Z"},
    )
    assert response.status_code == 422


def test_unknown_feed_is_404(client: TestClient):
    response = client.request("GET", "/v1/gtfs_feeds/mdb-does-not-exist/validation_reports", headers=authHeaders)
    assert response.status_code == 404
