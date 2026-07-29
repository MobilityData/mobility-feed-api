#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import unittest
from unittest.mock import MagicMock, patch

from tasks.users.reconcile_announcements_from_brevo import (
    reconcile_announcements_from_brevo,
    reconcile_announcements_from_brevo_handler,
    get_parameters,
)
from shared.common.brevo import BrevoSubscriptionStatus
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationSubscription,
)

FETCH = (
    "tasks.users.reconcile_announcements_from_brevo."
    "_fetch_active_announcements_subscriptions"
)
BREVO = "tasks.users.reconcile_announcements_from_brevo.get_contact_subscription_status"


def _make_user(uid, email=None, is_registered=True):
    return AppUser(
        id=uid,
        email=email if email is not None else f"{uid}@example.com",
        is_registered_to_receive_api_announcements=is_registered,
    )


def _make_sub(user_id, sub_id="sub-1", active=True):
    return NotificationSubscription(
        id=sub_id,
        user_id=user_id,
        notification_type_id="api.announcements",
        active=active,
    )


def _pair(uid, **user_kwargs):
    """Build a (subscription, app_user) row like the join query returns."""
    user = _make_user(uid, **user_kwargs)
    sub = _make_sub(uid, sub_id=f"sub-{uid}")
    return sub, user


def _run(
    rows,
    brevo_status=BrevoSubscriptionStatus.SUBSCRIBED,
    dry_run=False,
    limit=None,
    list_id="42",
):
    """Run the task with the DB fetch and Brevo status patched.

    ``brevo_status`` may be a single status (applied to every row) or a list of
    statuses/exceptions applied per row (as get_contact_subscription_status's
    side_effect). Returns (stats, session, mock_brevo, mock_fetch).
    """
    session = MagicMock()
    env = {"BREVO_API_ANNOUNCEMENTS_LIST_ID": list_id} if list_id else {}
    brevo_kwargs = (
        {"side_effect": brevo_status}
        if isinstance(brevo_status, list)
        else {"return_value": brevo_status}
    )
    with (
        patch(FETCH, return_value=rows) as mock_fetch,
        patch(BREVO, **brevo_kwargs) as mock_brevo,
        patch.dict(os.environ, env, clear=False),
    ):
        if not list_id:
            os.environ.pop("BREVO_API_ANNOUNCEMENTS_LIST_ID", None)
        stats = reconcile_announcements_from_brevo(
            dry_run=dry_run, limit=limit, db_session=session
        )
    return stats, session, mock_brevo, mock_fetch


class TestReconcileAnnouncementsFromBrevo(unittest.TestCase):
    # --- turn-OFF path ---

    def test_unsubscribed_user_reconciled(self):
        """Brevo UNSUBSCRIBED → flag False, subscription deactivated, flushed."""
        sub, user = _pair("u1")

        stats, session, _, _ = _run(
            [(sub, user)], brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED
        )

        self.assertFalse(user.is_registered_to_receive_api_announcements)
        self.assertFalse(sub.active)
        session.flush.assert_called()
        self.assertEqual(stats["reconciled_unsubscribed"], 1)
        self.assertEqual(stats["checked"], 1)

    def test_subscribed_user_untouched(self):
        """Brevo SUBSCRIBED → nothing changes, never re-subscribed."""
        sub, user = _pair("u2")

        stats, session, _, _ = _run(
            [(sub, user)], brevo_status=BrevoSubscriptionStatus.SUBSCRIBED
        )

        self.assertTrue(user.is_registered_to_receive_api_announcements)
        self.assertTrue(sub.active)
        session.flush.assert_not_called()
        self.assertEqual(stats["still_subscribed"], 1)
        self.assertEqual(stats["reconciled_unsubscribed"], 0)

    def test_not_found_user_untouched(self):
        """Brevo NOT_FOUND → left enabled; this task never adds contacts."""
        sub, user = _pair("u3")

        stats, session, _, _ = _run(
            [(sub, user)], brevo_status=BrevoSubscriptionStatus.NOT_FOUND
        )

        self.assertTrue(user.is_registered_to_receive_api_announcements)
        self.assertTrue(sub.active)
        session.flush.assert_not_called()
        self.assertEqual(stats["not_found"], 1)
        self.assertEqual(stats["reconciled_unsubscribed"], 0)

    # --- resilience ---

    def test_brevo_failure_counted_and_does_not_abort(self):
        """A Brevo error on one user is counted and the batch continues."""
        sub_a, user_a = _pair("bad")
        sub_b, user_b = _pair("good")

        stats, _, _, _ = _run(
            [(sub_a, user_a), (sub_b, user_b)],
            brevo_status=[
                Exception("Brevo down"),
                BrevoSubscriptionStatus.UNSUBSCRIBED,
            ],
        )

        self.assertEqual(stats["brevo_failed"], 1)
        # The failed user is untouched; the second user is still reconciled.
        self.assertTrue(user_a.is_registered_to_receive_api_announcements)
        self.assertFalse(user_b.is_registered_to_receive_api_announcements)
        self.assertFalse(sub_b.active)
        self.assertEqual(stats["reconciled_unsubscribed"], 1)
        self.assertEqual(stats["checked"], 2)

    def test_skipped_when_no_email(self):
        """A row with no email is skipped without a Brevo call."""
        sub, user = _pair("noemail", email="")

        stats, _, mock_brevo, _ = _run([(sub, user)])

        mock_brevo.assert_not_called()
        self.assertEqual(stats["skipped_no_email"], 1)
        self.assertEqual(stats["checked"], 0)

    # --- dry run ---

    def test_dry_run_counts_but_no_writes(self):
        """dry_run=True → counted as reconciled, but nothing is mutated/flushed."""
        sub, user = _pair("u4")

        stats, session, mock_brevo, _ = _run(
            [(sub, user)],
            brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            dry_run=True,
        )

        mock_brevo.assert_called_once()  # Brevo still queried for accurate counts
        self.assertTrue(user.is_registered_to_receive_api_announcements)
        self.assertTrue(sub.active)
        session.flush.assert_not_called()
        self.assertEqual(stats["reconciled_unsubscribed"], 1)
        self.assertTrue(stats["dry_run"])

    # --- limit / iteration ---

    def test_limit_is_forwarded_to_fetch(self):
        """limit is passed through to the DB fetch (query-level LIMIT)."""
        sub, user = _pair("u5")

        _, session, _, mock_fetch = _run(
            [(sub, user)], brevo_status=BrevoSubscriptionStatus.SUBSCRIBED, limit=7
        )

        mock_fetch.assert_called_once_with(session, 7)

    def test_idempotent_reconciled_user_drops_out(self):
        """Once deactivated, a subscription is no longer in the active set, so a
        subsequent run examines nothing."""
        stats, _, mock_brevo, _ = _run(
            [], brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED
        )

        mock_brevo.assert_not_called()
        self.assertEqual(stats["checked"], 0)
        self.assertEqual(stats["reconciled_unsubscribed"], 0)

    # --- list id handling ---

    def test_list_id_passed_to_brevo(self):
        """The configured announcements list id is passed to the status check so
        both global blacklist and list-level unsubscribe are honored."""
        sub, user = _pair("u6", email="u6@example.com")

        _, _, mock_brevo, _ = _run(
            [(sub, user)],
            brevo_status=BrevoSubscriptionStatus.SUBSCRIBED,
            list_id="42",
        )

        mock_brevo.assert_called_once_with("u6@example.com", 42)

    def test_missing_list_id_falls_back_to_none(self):
        """Without BREVO_API_ANNOUNCEMENTS_LIST_ID the check still runs, passing
        list_id=None (global email_blacklisted only)."""
        sub, user = _pair("u7", email="u7@example.com")

        stats, _, mock_brevo, _ = _run(
            [(sub, user)],
            brevo_status=BrevoSubscriptionStatus.UNSUBSCRIBED,
            list_id=None,
        )

        mock_brevo.assert_called_once_with("u7@example.com", None)
        self.assertEqual(stats["reconciled_unsubscribed"], 1)


class TestParametersAndHandler(unittest.TestCase):
    def test_get_parameters_defaults(self):
        self.assertEqual(get_parameters({}), (True, None))

    def test_get_parameters_coercion(self):
        self.assertEqual(get_parameters({"dry_run": "false", "limit": "5"}), (False, 5))

    @patch(
        "tasks.users.reconcile_announcements_from_brevo."
        "reconcile_announcements_from_brevo"
    )
    def test_handler_passes_defaults(self, mock_task):
        mock_task.return_value = {"checked": 0, "dry_run": True}
        result = reconcile_announcements_from_brevo_handler.__wrapped__(
            payload=None, db_session=MagicMock()
        )
        mock_task.assert_called_once_with(
            dry_run=True,
            limit=None,
            db_session=mock_task.call_args.kwargs["db_session"],
        )
        self.assertTrue(result["dry_run"])

    @patch(
        "tasks.users.reconcile_announcements_from_brevo."
        "reconcile_announcements_from_brevo"
    )
    def test_handler_passes_explicit_params(self, mock_task):
        mock_task.return_value = {"checked": 3}
        reconcile_announcements_from_brevo_handler.__wrapped__(
            payload={"dry_run": False, "limit": 3}, db_session=MagicMock()
        )
        kw = mock_task.call_args.kwargs
        self.assertFalse(kw["dry_run"])
        self.assertEqual(kw["limit"], 3)


if __name__ == "__main__":
    unittest.main()
