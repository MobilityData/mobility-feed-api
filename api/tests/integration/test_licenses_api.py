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
            [
                {
                    "name": "license-rule-1",
                    "label": "license-rule-1-label",
                    "description": "Rule 1 description",
                    "type": "permission",
                },
                {
                    "name": "license-rule-2",
                    "label": "license-rule-2-label",
                    "description": "Rule 2 description",
                    "type": "condition",
                },
            ],
        ),
        (
            "license-2",
            False,
            "License 2 name",
            "https://license-2",
            "This is license-2",
            [
                {
                    "name": "license-rule-2",
                    "label": "license-rule-2-label",
                    "description": "Rule 2 description",
                    "type": "condition",
                },
                {
                    "name": "license-rule-3",
                    "label": "license-rule-3-label",
                    "description": "Rule 3 description",
                    "type": "limitation",
                },
            ],
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
    # Transform the license rules array into a dictionary so we don't have to worry about order.
    actual_rules = {rule["name"]: rule for rule in body.get("license_rules", [])}
    expected_rule_map = {rule["name"]: rule for rule in expected_rules}
    assert actual_rules == expected_rule_map


def test_get_licenses_list_contains_test_licenses(client: TestClient):
    """GET /v1/licenses returns a list that includes license-1 and license-2 from test data."""
    response = client.request("GET", "/v1/licenses", headers=authHeaders, params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    ids = {item.get("id") for item in body}
    assert "license-1" in ids
    assert "license-2" in ids
    # List endpoint returns the base license schema, so license_rules should not be present.
    for item in body:
        assert "license_rules" not in item
