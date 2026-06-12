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
"""brevo_notification_sender — transactional email delivery via Brevo.

Brevo (formerly Sendinblue) is already used by this project for contact
management (``shared.common.brevo``).  This module extends that integration
to **transactional email** using ``sib_api_v3_sdk.TransactionalEmailsApi``.

Environment variables
---------------------
BREVO_API_KEY
    Brevo API key (required).
BREVO_SENDER_EMAIL
    From-address for outgoing emails (default: ``noreply@mobilitydatabase.org``).
BREVO_SENDER_NAME
    From-name (default: ``Mobility Database``).
BREVO_TEMPLATE_FEED_URL_UPDATED
    Integer Brevo template ID for ``feed.url_updated`` single-event emails.
    When not set, a plain-text fallback is used.
BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST
    Integer Brevo template ID for ``feed.url_updated`` digest emails.
    When not set, a plain-text fallback is used.
BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY
    Integer Brevo template ID for ``admin.event_summary`` emails.
    When not set, a plain-text fallback is used.

Design
------
* ``send_single`` sends one email for one notification_event.
* ``send_digest`` sends one email batching multiple notification_events.
* Both raise ``BrevSendError`` on failure so the caller can update
  ``notification_log.status`` and ``retry_count`` accordingly.
* Template params are passed as ``params`` to the Brevo API; Brevo renders
  them via its template engine.  When no template ID is configured, a minimal
  HTML fallback is built inline.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_SENDER_EMAIL = "noreply@mobilitydatabase.org"
_DEFAULT_SENDER_NAME = "Mobility Database"


class BrevoSendError(Exception):
    """Raised when a Brevo API call fails.  Callers catch this to record failure."""


@dataclass
class EmailRecipient:
    email: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"email": self.email}
        if self.name:
            d["name"] = self.name
        return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_single(
    recipient: EmailRecipient,
    notification_event,  # NotificationEvent ORM object
    subscription,  # NotificationSubscription ORM object
) -> None:
    """Send a single-event notification email.

    Parameters
    ----------
    recipient:
        Destination email address and name.
    notification_event:
        The ``NotificationEvent`` ORM instance to notify about.
    subscription:
        The ``NotificationSubscription`` ORM instance (used for unsubscribe context).

    Raises
    ------
    BrevoSendError
        When the Brevo API returns an error.
    """
    template_id = _int_env("BREVO_TEMPLATE_FEED_URL_UPDATED")
    params = _build_single_params(notification_event, subscription)
    subject = _build_single_subject(notification_event)
    html = _build_single_html(notification_event) if template_id is None else None

    _send(
        recipient=recipient,
        subject=subject,
        html_content=html,
        template_id=template_id,
        params=params,
    )


def send_digest(
    recipient: EmailRecipient,
    notification_events: List,  # List[NotificationEvent]
    subscription,  # NotificationSubscription ORM object
) -> None:
    """Send a digest email batching multiple notification events.

    Parameters
    ----------
    recipient:
        Destination email address and name.
    notification_events:
        The ``NotificationEvent`` instances to include in the digest.
    subscription:
        The ``NotificationSubscription`` ORM instance.

    Raises
    ------
    BrevoSendError
        When the Brevo API returns an error.
    """
    if not notification_events:
        logger.debug("send_digest called with empty event list; skipping")
        return

    notification_type_id = notification_events[0].notification_type_id

    if notification_type_id == "admin.event_summary":
        template_id = _int_env("BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY")
    else:
        template_id = _int_env("BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST")

    params = _build_digest_params(notification_events, subscription)
    subject = _build_digest_subject(notification_events)
    html = _build_digest_html(notification_events) if template_id is None else None

    _send(
        recipient=recipient,
        subject=subject,
        html_content=html,
        template_id=template_id,
        params=params,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _send(
    recipient: EmailRecipient,
    subject: str,
    html_content: Optional[str],
    template_id: Optional[int],
    params: Dict[str, Any],
) -> None:
    """Low-level send via Brevo TransactionalEmailsApi.

    Raises BrevoSendError on any failure.
    """
    try:
        import sib_api_v3_sdk
    except ImportError as exc:
        raise BrevoSendError(f"sib_api_v3_sdk is not installed: {exc}") from exc

    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        raise BrevoSendError("BREVO_API_KEY environment variable is not set")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = api_key

    client = sib_api_v3_sdk.ApiClient(configuration)
    api = sib_api_v3_sdk.TransactionalEmailsApi(client)

    sender_email = os.getenv("BREVO_SENDER_EMAIL", _DEFAULT_SENDER_EMAIL)
    sender_name = os.getenv("BREVO_SENDER_NAME", _DEFAULT_SENDER_NAME)

    send_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[recipient.to_dict()],
        sender={"email": sender_email, "name": sender_name},
        subject=subject if template_id is None else None,
        html_content=html_content,
        template_id=template_id,
        params=params if template_id is not None else None,
    )

    try:
        result = api.send_transac_email(send_email)
        logger.info(
            "Brevo email sent to %s (message_id=%s)",
            recipient.email,
            getattr(result, "message_id", "n/a"),
        )
    except sib_api_v3_sdk.rest.ApiException as exc:
        raise BrevoSendError(f"Brevo API error {exc.status} sending to {recipient.email}: {exc.reason}") from exc
    except Exception as exc:
        raise BrevoSendError(f"Unexpected error sending to {recipient.email}: {exc}") from exc


def _int_env(var: str) -> Optional[int]:
    """Return an env var as int, or None if not set / not parseable."""
    val = os.getenv(var)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        logger.warning("Environment variable %s=%r is not a valid integer; ignoring", var, val)
        return None


# ---------------------------------------------------------------------------
# Email content builders (plain-HTML fallback when no template is configured)
# ---------------------------------------------------------------------------


def _build_single_subject(event) -> str:
    if event.update_type == "feed_redirected":
        return f"[Mobility Database] Feed {event.feed_stable_id} has been redirected"
    return f"[Mobility Database] Feed {event.feed_stable_id} URL updated"


def _build_digest_subject(events: List) -> str:
    count = len(events)
    type_id = events[0].notification_type_id if events else "notification"
    if type_id == "admin.event_summary":
        return "[Mobility Database] Daily notification dispatch summary"
    return f"[Mobility Database] {count} feed URL update{'s' if count != 1 else ''}"


def _build_single_params(event, subscription) -> Dict[str, Any]:
    return {
        "feed_stable_id": event.feed_stable_id,
        "target_feed_stable_id": event.target_feed_stable_id,
        "update_type": event.update_type,
        "old_url": event.old_url or "",
        "new_url": event.new_url or "",
        "source": event.source or "",
        "event_created_at": event.created_at.isoformat() if event.created_at else "",
        "subscription_id": subscription.id,
    }


def _build_digest_params(events: List, subscription) -> Dict[str, Any]:
    return {
        "event_count": len(events),
        "subscription_id": subscription.id,
        "events": [
            {
                "feed_stable_id": e.feed_stable_id,
                "target_feed_stable_id": e.target_feed_stable_id,
                "update_type": e.update_type,
                "old_url": e.old_url or "",
                "new_url": e.new_url or "",
                "source": e.source or "",
                "created_at": e.created_at.isoformat() if e.created_at else "",
                "extra_data": e.extra_data or {},
            }
            for e in events
        ],
    }


def _build_single_html(event) -> str:
    if event.update_type == "feed_redirected":
        return (
            f"<p>Feed <strong>{event.feed_stable_id}</strong> has been deprecated "
            f"and now redirects to <strong>{event.target_feed_stable_id}</strong>.</p>"
            f"<p>New URL: <a href='{event.new_url}'>{event.new_url}</a></p>"
        )
    return (
        f"<p>The URL for feed <strong>{event.feed_stable_id}</strong> has changed.</p>"
        f"<p>Old URL: {event.old_url}</p>"
        f"<p>New URL: <a href='{event.new_url}'>{event.new_url}</a></p>"
    )


def _build_digest_html(events: List) -> str:
    if not events:
        return "<p>No feed URL changes in this period.</p>"

    if events[0].notification_type_id == "admin.event_summary":
        rows = "".join(
            f"<tr><td>{e.feed_stable_id or '-'}</td>"
            f"<td>{e.update_type}</td>"
            f"<td>{(e.extra_data or {}).get('sent', 0)}</td>"
            f"<td>{(e.extra_data or {}).get('failed', 0)}</td></tr>"
            for e in events
        )
        return (
            "<h2>Notification Dispatch Summary</h2>"
            "<table border='1'><thead>"
            "<tr><th>Feed</th><th>Type</th><th>Sent</th><th>Failed</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>"
        )

    rows = "".join(
        f"<tr><td>{e.feed_stable_id}</td><td>{e.update_type}</td>"
        f"<td>{e.old_url or '-'}</td><td>{e.new_url or '-'}</td>"
        f"<td>{e.source or '-'}</td></tr>"
        for e in events
    )
    return (
        "<h2>Feed URL Updates</h2>"
        "<table border='1'><thead>"
        "<tr><th>Feed</th><th>Type</th><th>Old URL</th><th>New URL</th><th>Source</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>"
    )
