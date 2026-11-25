from endpoints.integration_tests import IntegrationTests

# Seeded by integration-tests/fixtures/test_data.json with the isNotificationsEnabled flag.
TEST_USER_ID = "integration-tests-user"
TEST_USER_EMAIL = "integration-tests@example.com"
FEED_ID = "mdb-745"
NOTIFICATION_ID = "feed.url_updated"
# UserServiceAPI.yaml documents 201 for POST /v1/user/subscriptions and 204 for the DELETE
# endpoints, but the generated routes keep FastAPI's default 200.
CREATED = (200, 201)
DELETED = (200, 204)


class UserServiceEndpointTests(IntegrationTests):
    """The User Service endpoints, as the seeded test user.

    Authenticates with the x-goog-authenticated-user-* headers the API accepts for local
    development, so it only runs against the API the PR workflow starts. The Brevo-backed
    endpoints (announcements sync and the announcements opt-in) are not covered.
    """

    def __init__(self, file_path, access_token, url, progress, console):
        super().__init__(file_path, access_token, url, progress, console)

    def _user_request(
        self, method, url_suffix, expected_status, json=None, params=None
    ):
        response = self.send_request(
            method,
            url_suffix,
            params=params,
            json=json,
            headers={
                "x-goog-authenticated-user-id": TEST_USER_ID,
                "x-goog-authenticated-user-email": f"accounts.google.com:{TEST_USER_EMAIL}",
            },
        )
        expected = (
            expected_status
            if isinstance(expected_status, tuple)
            else (expected_status,)
        )
        assert response.status_code in expected, (
            f"Expected {expected_status} for {method} {url_suffix}, got "
            f"{response.status_code}: {response.text[:300]}"
        )
        return response.json() if response.content else None

    def _remove_test_subscriptions(self):
        """Delete the user's subscriptions to the test type, so a re-run starts clean."""
        for sub in self._user_request("GET", "v1/user/subscriptions", 200):
            if sub["notification_id"] == NOTIFICATION_ID:
                self._user_request(
                    "DELETE", f"v1/user/subscriptions/{sub['id']}", DELETED
                )

    def _subscribe(self):
        sub = self._user_request(
            "POST",
            "v1/user/subscriptions",
            CREATED,
            json={"notification_id": NOTIFICATION_ID, "feed_ids": [FEED_ID]},
        )
        assert sub["notification_id"] == NOTIFICATION_ID
        assert sub["active"] is True
        return sub

    def test_user_profile(self):
        """GET and PUT /v1/user read and update the user's profile."""
        user = self._user_request("GET", "v1/user", 200)
        assert user["id"] == TEST_USER_ID
        assert user["email"] == TEST_USER_EMAIL

        updated = self._user_request(
            "PUT", "v1/user", 200, json={"legacy_org_name": "Integration Tests Org"}
        )
        assert updated["legacy_org_name"] == "Integration Tests Org"
        assert self._user_request("GET", "v1/user", 200)["legacy_org_name"] == (
            "Integration Tests Org"
        )

    def test_user_identity_required(self):
        """The user endpoints answer 401 without an identity."""
        response = self.get_response("v1/user/subscriptions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}."

    def test_notification_types(self):
        """GET /v1/notifications lists the types a user can subscribe to."""
        types = {t["id"] for t in self._user_request("GET", "v1/notifications", 200)}
        assert NOTIFICATION_ID in types, f"Got {types}."
        # Only listed for users with the admin summary flag, which the test user lacks.
        assert "admin.event_summary" not in types

    def test_user_subscriptions(self):
        """Create, list, update and delete a feed subscription through /v1/user/subscriptions."""
        self._remove_test_subscriptions()
        sub = self._subscribe()

        listed = self._user_request("GET", "v1/user/subscriptions", 200)
        assert sub["id"] in {s["id"] for s in listed}

        groups = self._user_request("GET", "v1/user/subscriptions/feeds", 200)
        assert FEED_ID in {g["feed_id"] for g in groups}, f"Got {groups}."
        group = self._user_request("GET", f"v1/user/subscriptions/feeds/{FEED_ID}", 200)
        assert sub["id"] in {s["id"] for s in group["subscriptions"]}

        updated = self._user_request(
            "PATCH",
            f"v1/user/subscriptions/{sub['id']}",
            200,
            json={"active": False, "cadence": "daily"},
        )
        assert updated["active"] is False
        assert updated["cadence"] == "daily"

        self._user_request("DELETE", f"v1/user/subscriptions/{sub['id']}", DELETED)
        listed = self._user_request("GET", "v1/user/subscriptions", 200)
        assert sub["id"] not in {s["id"] for s in listed}

    def test_subscription_by_id(self):
        """GET and DELETE /v1/subscriptions/{id}, the unauthenticated unsubscribe link."""
        self._remove_test_subscriptions()
        sub = self._subscribe()

        response = self.get_response(f"v1/subscriptions/{sub['id']}")
        assert (
            response.status_code == 200
        ), f"Got {response.status_code}: {response.text}"
        assert response.json()["id"] == sub["id"]

        response = self.send_request(
            "DELETE", f"v1/subscriptions/{sub['id']}", params={"scope": "one"}
        )
        assert (
            response.status_code in DELETED
        ), f"Got {response.status_code}: {response.text}"
        response = self.get_response(f"v1/subscriptions/{sub['id']}")
        assert (
            response.status_code == 404
        ), f"Expected 404 after unsubscribe, got {response.status_code}."
