#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""Regression test: a slow external (Brevo) call in a delete request must NOT freeze the API.

The generated FastAPI routes are ``async def`` but invoke synchronous impl methods that perform
blocking I/O (the Brevo HTTP call). If that blocking call runs on the event loop, every other
request to the API is frozen until it returns. This test drives a delete whose Brevo call is slow
and, concurrently, runs a lightweight asyncio "heartbeat". If the event loop keeps ticking while
the slow delete is in flight, the API is not blocked.
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import httpx

import user_service.impl.subscription_helpers as helpers

SUB_ID = "sub-loop-test"
SLOW_SECONDS = 1.0
HEARTBEAT_INTERVAL = 0.01


def _build_mock_session():
    """A mock users-DB session whose .get returns an announcements subscription + a user."""
    sub = MagicMock()
    sub.id = SUB_ID
    sub.notification_type_id = helpers.ANNOUNCEMENTS_NOTIFICATION_TYPE_ID
    sub.user_id = "u1"
    sub.active = True

    user = MagicMock()
    user.email = "user@example.com"

    session = MagicMock()

    def _get(model, key):
        return sub if "Subscription" in model.__name__ else user

    session.get.side_effect = _get
    return session, sub


async def _delete_with_heartbeat(app):
    """Issue the slow delete while counting event-loop heartbeats during the request."""
    ticks = {"n": 0}
    stop = {"flag": False}

    async def heartbeat():
        while not stop["flag"]:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            ticks["n"] += 1

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        hb = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.05)  # let the heartbeat establish a baseline cadence
        before = ticks["n"]
        response = await client.delete(f"/v1/subscriptions/{SUB_ID}")
        during = ticks["n"] - before
        stop["flag"] = True
        await hb

    return response, during


def test_slow_brevo_delete_does_not_block_event_loop():
    from main import app
    from user_service_gen.security_api import get_token_Authentication

    session, sub = _build_mock_session()
    fake_db = MagicMock()
    fake_db.start_db_session.return_value.__enter__.return_value = session
    fake_db.start_db_session.return_value.__exit__.return_value = False

    def _slow_remove(*_args, **_kwargs):
        time.sleep(SLOW_SECONDS)

    app.dependency_overrides[get_token_Authentication] = lambda: "test-token"
    try:
        with patch("shared.database.users_database.UsersDatabase", return_value=fake_db), patch.object(
            helpers, "remove_contact_from_list", side_effect=_slow_remove
        ), patch.object(helpers, "get_announcements_list_id", return_value=1):
            response, ticks_during = asyncio.run(_delete_with_heartbeat(app))
    finally:
        app.dependency_overrides.pop(get_token_Authentication, None)

    # The announcements subscription is disabled (not deleted), so the request succeeds.
    assert response.status_code < 400
    assert sub.active is False

    # While the ~1s Brevo call was in flight, the event loop must have kept ticking. A non-blocked
    # loop ticks ~SLOW_SECONDS / HEARTBEAT_INTERVAL (~100) times; a blocked loop ticks ~0.
    expected_min_ticks = int((SLOW_SECONDS / HEARTBEAT_INTERVAL) * 0.5)
    assert ticks_during >= expected_min_ticks, (
        f"Event loop appears blocked during the slow delete: only {ticks_during} heartbeats "
        f"(expected >= {expected_min_ticks}). The blocking Brevo call is running on the event loop."
    )
