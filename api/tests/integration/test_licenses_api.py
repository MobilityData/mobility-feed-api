# coding: utf-8
import pytest
from fastapi.testclient import TestClient

from tests.test_utils.token import authHeaders


@pytest.mark.parametrize(
    "license_id, expected_is_spdx, expected_name, expected_url, expected_description, expected_rules",
    [
        (
            "license-1",
            True,
            "License 1 name",
            "https://license-1",
            "This is license-1",
            ["license-rule-1", "license-rule-2"],
        ),
        (
            "license-2",
            False,
            "License 2 name",
            "https://license-2",
            "This is license-2",
            ["license-rule-2", "license-rule-3"],
        ),
    ],
)
def test_get_license_by_id(
    client: TestClient,
    license_id: str,
    expected_is_spdx: bool,
    expected_name: str,
    expected_url: str,
    expected_description: str,
    expected_rules: list,
):
    """GET /v1/licenses/{id} returns the expected license fields for known test licenses."""
    response = client.request("GET", f"/v1/licenses/{license_id}", headers=authHeaders)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == license_id
    assert body.get("is_spdx") is expected_is_spdx
    assert body.get("name") == expected_name
    assert body.get("url") == expected_url
    assert body.get("description") == expected_description
    # license_rules should be present and match expected (order not important)
    assert set(body.get("license_rules", [])) == set(expected_rules)


def test_get_licenses_list_contains_test_licenses(client: TestClient):
    """GET /v1/licenses returns a list that includes license-1 and license-2 from test data."""
    response = client.request("GET", "/v1/licenses", headers=authHeaders, params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    ids = {item.get("id") for item in body}
    assert "license-1" in ids
    assert "license-2" in ids
    # build a mapping of id -> license_rules
    rules_map = {item.get("id"): set(item.get("license_rules", [])) for item in body}
    assert rules_map.get("license-1") == set(["license-rule-1", "license-rule-2"])
    assert rules_map.get("license-2") == set(["license-rule-2", "license-rule-3"])
