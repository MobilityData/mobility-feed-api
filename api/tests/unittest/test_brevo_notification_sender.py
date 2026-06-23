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
"""Unit tests for the pure builders, accessors and ``_send`` of
``brevo_notification_sender`` — the bulk of which had no coverage."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import shared.notifications.brevo_notification_sender as bns
from shared.notifications.brevo_notification_sender import (
    BrevoSendError,
    EmailRecipient,
    build_digest_html,
    build_digest_subject,
    build_params_admin_event_summary,
    build_params_by_notification,
    build_params_feed_url_updated,
    build_single_html,
    build_single_subject,
    event_payload,
    get_template_id_by_notification,
    send_digest,
    send_single,
    subject_feed,
    target_feed,
    _int_env,
    _send,
)
from shared.notifications.notification_constants import (
    FeedUrlUpdateType,
    NotificationFeedRole,
    NotificationTypeId,
)


def _feed(stable_id, role):
    return SimpleNamespace(feed_stable_id=stable_id, role=role)


def _event(
    *,
    type_id=NotificationTypeId.FEED_URL_UPDATED,
    subtype=FeedUrlUpdateType.URL_REPLACED,
    feeds=None,
    payload=None,
    source="unit_test",
    created_at=None,
):
    return SimpleNamespace(
        notification_type_id=type_id,
        event_subtype=subtype,
        notification_event_feeds=feeds or [],
        payload=payload,
        source=source,
        created_at=created_at,
    )


_SUBSCRIPTION = SimpleNamespace(id="sub-1")


# ---------------------------------------------------------------------------
# EmailRecipient
# ---------------------------------------------------------------------------


def test_email_recipient_to_dict_with_and_without_name():
    assert EmailRecipient(email="a@b.com").to_dict() == {"email": "a@b.com"}
    assert EmailRecipient(email="a@b.com", name="A B").to_dict() == {
        "email": "a@b.com",
        "name": "A B",
    }


# ---------------------------------------------------------------------------
# get_template_id_by_notification
# ---------------------------------------------------------------------------


def test_get_template_id_feed_url_updated_digest_and_single(monkeypatch):
    monkeypatch.setenv("BREVO_TEMPLATE_FEED_URL_UPDATED", "11")
    monkeypatch.setenv("BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST", "22")
    assert get_template_id_by_notification(NotificationTypeId.FEED_URL_UPDATED) == 11
    assert get_template_id_by_notification(NotificationTypeId.FEED_URL_UPDATED, digest=True) == 22


def test_get_template_id_admin_event_summary(monkeypatch):
    monkeypatch.setenv("BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY", "33")
    assert get_template_id_by_notification(NotificationTypeId.ADMIN_EVENT_SUMMARY) == 33


def test_get_template_id_unknown_type_returns_none():
    assert get_template_id_by_notification("some.unknown.type") is None


# ---------------------------------------------------------------------------
# Event accessors
# ---------------------------------------------------------------------------


def test_feed_accessors_and_payload():
    event = _event(
        feeds=[
            _feed("mdb-1", NotificationFeedRole.SUBJECT),
            _feed("mdb-2", NotificationFeedRole.TARGET),
        ],
        payload={"old_url": "x"},
    )
    assert subject_feed(event) == "mdb-1"
    assert target_feed(event) == "mdb-2"
    assert event_payload(event) == {"old_url": "x"}


def test_feed_accessors_when_missing():
    event = _event(feeds=[], payload=None)
    assert subject_feed(event) is None
    assert target_feed(event) is None
    assert event_payload(event) == {}


# ---------------------------------------------------------------------------
# Subject builders
# ---------------------------------------------------------------------------


def test_build_single_subject_known_and_unknown():
    known = _event(feeds=[_feed("mdb-9", NotificationFeedRole.SUBJECT)])
    assert build_single_subject(known) == "[Mobility Database] Feed mdb-9 has been updated"

    unknown = _event(type_id="other.type")
    assert "other.type" in build_single_subject(unknown)


def test_build_single_subject_uses_unknown_feed_placeholder():
    event = _event(feeds=[])
    assert "unknown" in build_single_subject(event)


def test_build_digest_subject_pluralization():
    two = [_event(), _event()]
    assert build_digest_subject(two) == "[Mobility Database] 2 feed URL updates"
    one = [_event()]
    assert build_digest_subject(one) == "[Mobility Database] 1 feed URL update"


def test_build_digest_subject_unknown_type_fallback():
    events = [_event(type_id="other.type"), _event(type_id="other.type")]
    assert build_digest_subject(events) == "[Mobility Database] 2 notifications"
    single = [_event(type_id="other.type")]
    assert build_digest_subject(single) == "[Mobility Database] 1 notification"


# ---------------------------------------------------------------------------
# Params builders
# ---------------------------------------------------------------------------


def test_build_params_feed_url_updated():
    created = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    event = _event(
        feeds=[
            _feed("mdb-1", NotificationFeedRole.SUBJECT),
            _feed("mdb-2", NotificationFeedRole.TARGET),
        ],
        payload={"old_url": "old", "new_url": "new"},
        created_at=created,
    )
    params = build_params_feed_url_updated([event], _SUBSCRIPTION)
    assert params["event_count"] == 1
    assert params["subscription_id"] == "sub-1"
    item = params["events"][0]
    assert item["feed_stable_id"] == "mdb-1"
    assert item["target_feed_stable_id"] == "mdb-2"
    assert item["old_url"] == "old"
    assert item["new_url"] == "new"
    assert item["created_at"] == created.isoformat()


def test_build_params_feed_url_updated_handles_missing_created_at_and_urls():
    event = _event(feeds=[], payload={}, created_at=None, source=None)
    item = build_params_feed_url_updated([event], _SUBSCRIPTION)["events"][0]
    assert item["old_url"] == ""
    assert item["new_url"] == ""
    assert item["source"] == ""
    assert item["created_at"] == ""


def test_build_params_admin_event_summary_with_and_without_events():
    event = _event(
        type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
        payload={"emails_sent": 5},
    )
    params = build_params_admin_event_summary([event], _SUBSCRIPTION)
    assert params["event_count"] == 1
    assert params["summary"] == {"emails_sent": 5}

    empty = build_params_admin_event_summary([], _SUBSCRIPTION)
    assert empty["event_count"] == 0
    assert empty["summary"] == {}


def test_build_params_by_notification_dispatch_and_unsupported():
    feed_event = _event()
    assert "events" in build_params_by_notification(NotificationTypeId.FEED_URL_UPDATED, [feed_event], _SUBSCRIPTION)
    admin_event = _event(type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY)
    assert "summary" in build_params_by_notification(
        NotificationTypeId.ADMIN_EVENT_SUMMARY, [admin_event], _SUBSCRIPTION
    )
    with pytest.raises(ValueError):
        build_params_by_notification("other.type", [feed_event], _SUBSCRIPTION)


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------


def test_build_single_html_redirected_and_replaced():
    redirected = _event(
        subtype=FeedUrlUpdateType.FEED_REDIRECTED,
        feeds=[
            _feed("mdb-1", NotificationFeedRole.SUBJECT),
            _feed("mdb-2", NotificationFeedRole.TARGET),
        ],
        payload={"new_url": "https://new"},
    )
    html = build_single_html(redirected)
    assert "deprecated" in html
    assert "mdb-2" in html

    replaced = _event(
        subtype=FeedUrlUpdateType.URL_REPLACED,
        feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "https://old", "new_url": "https://new"},
    )
    html = build_single_html(replaced)
    assert "has changed" in html
    assert "https://old" in html


def test_build_single_html_admin_summary():
    event = _event(
        type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
        feeds=[],
        payload={
            "subscriptions_processed": 4,
            "events_found": 7,
            "emails_sent": 5,
            "emails_failed": 2,
            "cadence": "weekly",
        },
    )
    html = build_single_html(event)
    assert "Notification Dispatch Summary" in html
    assert "weekly" in html
    assert "<td>5</td>" in html
    assert "<td>2</td>" in html
    # Must NOT fall through to the feed url-updated layout.
    assert "has changed" not in html
    assert "Old URL" not in html


def test_build_digest_html_empty():
    assert "No feed URL changes" in build_digest_html([])


def test_build_digest_html_admin_summary():
    event = _event(
        type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
        feeds=[],
        payload={"emails_sent": 3, "emails_failed": 1},
    )
    html = build_digest_html([event])
    assert "Notification Dispatch Summary" in html
    assert "<td>3</td>" in html
    assert "<td>1</td>" in html


def test_build_digest_html_feed_url_updates():
    event = _event(
        feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "o", "new_url": "n"},
    )
    html = build_digest_html([event])
    assert "Feed URL Updates" in html
    assert "mdb-1" in html


# ---------------------------------------------------------------------------
# send_single / send_digest orchestration
# ---------------------------------------------------------------------------


@patch.object(bns, "_send")
def test_send_single_uses_html_fallback_when_no_template(mock_send, monkeypatch):
    monkeypatch.delenv("BREVO_TEMPLATE_FEED_URL_UPDATED", raising=False)
    event = _event(
        feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "o", "new_url": "n"},
    )
    send_single(EmailRecipient(email="a@b.com"), event, _SUBSCRIPTION)
    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["template_id"] is None
    assert kwargs["html_content"] is not None


@patch.object(bns, "_send")
def test_send_single_uses_template_when_configured(mock_send, monkeypatch):
    monkeypatch.setenv("BREVO_TEMPLATE_FEED_URL_UPDATED", "77")
    event = _event(
        feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "o", "new_url": "n"},
    )
    send_single(EmailRecipient(email="a@b.com"), event, _SUBSCRIPTION)
    kwargs = mock_send.call_args.kwargs
    assert kwargs["template_id"] == 77
    assert kwargs["html_content"] is None


@patch.object(bns, "_send")
def test_send_digest_empty_is_noop(mock_send):
    send_digest(EmailRecipient(email="a@b.com"), [], _SUBSCRIPTION)
    mock_send.assert_not_called()


@patch.object(bns, "_send")
def test_send_digest_html_fallback(mock_send, monkeypatch):
    monkeypatch.delenv("BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST", raising=False)
    events = [
        _event(
            feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
            payload={"old_url": "o", "new_url": "n"},
        )
    ]
    send_digest(EmailRecipient(email="a@b.com"), events, _SUBSCRIPTION)
    kwargs = mock_send.call_args.kwargs
    assert kwargs["template_id"] is None
    assert kwargs["html_content"] is not None


# ---------------------------------------------------------------------------
# _send low-level
# ---------------------------------------------------------------------------


def test_send_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    with pytest.raises(BrevoSendError, match="BREVO_API_KEY"):
        _send(
            recipient=EmailRecipient(email="a@b.com"),
            subject="s",
            html_content="<p>x</p>",
            template_id=None,
            params={},
        )


def test_send_success(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "key")
    fake_api = MagicMock()
    fake_api.send_transac_email.return_value = SimpleNamespace(message_id="mid-1")
    with patch("sib_api_v3_sdk.TransactionalEmailsApi", return_value=fake_api):
        _send(
            recipient=EmailRecipient(email="a@b.com"),
            subject="s",
            html_content="<p>x</p>",
            template_id=None,
            params={},
        )
    fake_api.send_transac_email.assert_called_once()


def test_send_wraps_api_exception(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "key")
    from sib_api_v3_sdk.rest import ApiException

    fake_api = MagicMock()
    fake_api.send_transac_email.side_effect = ApiException(status=429, reason="Too Many")
    with patch("sib_api_v3_sdk.TransactionalEmailsApi", return_value=fake_api):
        with pytest.raises(BrevoSendError, match="429"):
            _send(
                recipient=EmailRecipient(email="a@b.com"),
                subject="s",
                html_content="<p>x</p>",
                template_id=None,
                params={},
            )


def test_send_wraps_unexpected_exception(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "key")
    fake_api = MagicMock()
    fake_api.send_transac_email.side_effect = RuntimeError("boom")
    with patch("sib_api_v3_sdk.TransactionalEmailsApi", return_value=fake_api):
        with pytest.raises(BrevoSendError, match="Unexpected error"):
            _send(
                recipient=EmailRecipient(email="a@b.com"),
                subject="s",
                html_content="<p>x</p>",
                template_id=None,
                params={},
            )


# ---------------------------------------------------------------------------
# _int_env
# ---------------------------------------------------------------------------


def test_int_env_valid_invalid_and_unset(monkeypatch):
    monkeypatch.setenv("SOME_INT", "42")
    assert _int_env("SOME_INT") == 42
    monkeypatch.setenv("SOME_INT", "not-a-number")
    assert _int_env("SOME_INT") is None
    monkeypatch.delenv("SOME_INT", raising=False)
    assert _int_env("SOME_INT") is None


# ---------------------------------------------------------------------------
# HTML escaping (injection safety)
# ---------------------------------------------------------------------------


def test_build_single_html_escapes_injection():
    event = _event(
        subtype=FeedUrlUpdateType.URL_REPLACED,
        feeds=[_feed("mdb-<script>", NotificationFeedRole.SUBJECT)],
        payload={
            "old_url": "https://x.com/a' onmouseover='alert(1)",
            "new_url": "https://x.com/<b>",
        },
    )
    html = build_single_html(event)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # The raw single-quote attribute breakout must be escaped.
    assert "onmouseover='alert(1)" not in html


def test_link_only_links_http_schemes():
    event = _event(
        subtype=FeedUrlUpdateType.URL_REPLACED,
        feeds=[_feed("mdb-1", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "o", "new_url": "javascript:alert(1)"},
    )
    html = build_single_html(event)
    # A non-http(s) URL must not become a live <a href> link (rendered as plain text only).
    assert "<a href=" not in html
    assert 'href="javascript:' not in html


def test_build_digest_html_escapes_values():
    event = _event(
        feeds=[_feed("<i>mdb</i>", NotificationFeedRole.SUBJECT)],
        payload={"old_url": "<o>", "new_url": "<n>"},
        source="<src>",
    )
    html = build_digest_html([event])
    assert "<i>mdb</i>" not in html
    assert "&lt;i&gt;mdb&lt;/i&gt;" in html
    assert "<o>" not in html
