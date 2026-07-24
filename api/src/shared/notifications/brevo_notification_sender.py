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
    When not set, an inline HTML fallback is used.
BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST
    Integer Brevo template ID for ``feed.url_updated`` digest emails.
    When not set, an inline HTML fallback is used.
BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY
    Integer Brevo template ID for ``admin.event_summary`` emails.
    When not set, an inline HTML fallback is used.
BREVO_MAX_RPS
    Maximum Brevo API requests per second (default: ``900``). Stays below
    Brevo's hard limit of 1000 rps. Enforced by a shared token-bucket limiter.

Design
------
* ``send_single`` sends one email for one notification_event.
* ``send_digest`` sends one email batching multiple notification_events.
* Both raise ``BrevoSendError`` on failure so the caller can update
  ``notification_log.status`` and ``retry_count`` accordingly.
* Template params are passed as ``params`` to the Brevo API; Brevo renders
  them via its template engine.  When no template ID is configured, a minimal
  HTML fallback is built inline.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape as _html_escape
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from shared.common.rate_limiter import RateLimiter, get_rate_limiter
from shared.notifications.notification_constants import (
    NotificationFeedRole,
    NotificationTypeId,
)
from shared.users_database_gen.sqlacodegen_models import NotificationEvent

logger = logging.getLogger(__name__)

_DEFAULT_SENDER_EMAIL = "noreply@mobilitydatabase.org"
_DEFAULT_SENDER_NAME = "Mobility Database"

# ---------------------------------------------------------------------------
# Jinja2 environment (HTML-fallback templates, used when no Brevo-hosted
# template ID is configured for a notification type — see templates/*.html.j2)
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _safe_link_filter(url: Optional[str]) -> Markup:
    """Render a safe ``<a>`` for a URL, escaping it and only linking http(s).

    Non-http(s) (or empty) values are rendered as escaped text only, so a
    crafted ``javascript:`` / malformed value cannot become a live link or
    break out of the ``href`` attribute. Always returns ``Markup`` (content is
    already escaped here) so the autoescaping Jinja environment does not
    escape it a second time.
    """
    if not url:
        return Markup("")
    escaped = _html_escape(str(url), quote=True)
    if str(url).strip().lower().startswith(("http://", "https://")):
        return Markup(f'<a href="{escaped}">{escaped}</a>')
    return Markup(escaped)


def _thousands_sep(n: Optional[int]) -> str:
    """Format an integer with thousands separators; ``None`` renders as an em dash."""
    return "{:,}".format(int(n)) if n is not None else "—"


_jinja_env.filters["safe_link"] = _safe_link_filter
_jinja_env.filters["thousands_sep"] = _thousands_sep
# Fallback for the shared footer's copyright year when a template doesn't pass
# `notification_date` (see _base_email.html.j2).
_jinja_env.globals["current_year"] = lambda: datetime.now(timezone.utc).year


_DEFAULT_WEBSITE_URL = "https://mobilitydatabase.org"


def _website_url() -> str:
    return os.getenv("MOBILITY_DATABASE_WEBSITE_URL", _DEFAULT_WEBSITE_URL).rstrip("/")


def _feed_page_url(stable_id: Optional[str]) -> Optional[str]:
    """Link to a feed's page on the Mobility Database website, or None if unknown."""
    return f"{_website_url()}/feeds/{stable_id}" if stable_id else None


def _subscriptions_management_url() -> str:
    """Link to the subscriptions management page.

    Used for both the "Manage subscriptions" and "Unsubscribe" footer links —
    there is no one-click unsubscribe endpoint yet (see docs/notifications.md
    "Future Work"), so "Unsubscribe" currently points here too rather than to
    a dead link.
    TODO: implement a one-click unsubscribe endpoint and update the footer link to point there.
    """
    return f"{_website_url()}/account/notifications"


# Brevo's transactional email API allows up to 1000 requests/second. Default
# below that to leave headroom for clock skew and other API consumers.
BREVO_MAX_RPS_ENV = "BREVO_MAX_RPS"
DEFAULT_BREVO_MAX_RPS = 900.0
_BREVO_RATE_LIMITER_NAME = "brevo"


def _configured_brevo_rps() -> float:
    raw = os.getenv(BREVO_MAX_RPS_ENV)
    if not raw:
        return DEFAULT_BREVO_MAX_RPS
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid %s=%r; falling back to %.0f rps",
            BREVO_MAX_RPS_ENV,
            raw,
            DEFAULT_BREVO_MAX_RPS,
        )
        return DEFAULT_BREVO_MAX_RPS
    if value <= 0:
        logger.warning(
            "%s must be > 0 (got %r); falling back to %.0f rps",
            BREVO_MAX_RPS_ENV,
            raw,
            DEFAULT_BREVO_MAX_RPS,
        )
        return DEFAULT_BREVO_MAX_RPS
    return value


def get_brevo_rate_limiter() -> RateLimiter:
    """Return the process-wide Brevo rate limiter (token bucket).

    Configured from ``BREVO_MAX_RPS`` (default :data:`DEFAULT_BREVO_MAX_RPS`).
    Callers should ``acquire()`` before each Brevo API request.
    """
    return get_rate_limiter(_BREVO_RATE_LIMITER_NAME, _configured_brevo_rps())


_DIGEST_EMAIL_SUBJECT_DICTIONARY = {
    NotificationTypeId.FEED_URL_UPDATED: "[Mobility Database] %s feed URL update%s",
    NotificationTypeId.ADMIN_EVENT_SUMMARY: "[Mobility Database] Daily notification dispatch summary",
}

_SINGLE_EMAIL_SUBJECT_DICTIONARY = {
    NotificationTypeId.FEED_URL_UPDATED: "[Mobility Database] Feed %s has been updated",
    NotificationTypeId.ADMIN_EVENT_SUMMARY: "[Mobility Database] Daily notification dispatch summary",
}


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


def get_template_id_by_notification(
    notification_type_id: str,
    *,
    digest: bool = False,
) -> Optional[int]:
    match notification_type_id:
        case NotificationTypeId.FEED_URL_UPDATED:
            if digest:
                return _int_env("BREVO_TEMPLATE_FEED_URL_UPDATED_DIGEST")
            return _int_env("BREVO_TEMPLATE_FEED_URL_UPDATED")
        case NotificationTypeId.ADMIN_EVENT_SUMMARY:
            return _int_env("BREVO_TEMPLATE_ADMIN_EVENT_SUMMARY")
        case _:
            return None


# ---------------------------------------------------------------------------
# Event accessors — read feeds (from notification_event_feed) and payload
# ---------------------------------------------------------------------------


def _feeds_with_role(event, role: str) -> List[str]:
    """Return the stable_ids of feeds attached to ``event`` with the given role."""
    return [f.feed_stable_id for f in (getattr(event, "notification_event_feeds", None) or []) if f.role == role]


def subject_feed(event) -> Optional[str]:
    """First feed in the 'subject' role, or None."""
    feeds = _feeds_with_role(event, NotificationFeedRole.SUBJECT)
    return feeds[0] if feeds else None


def target_feed(event) -> Optional[str]:
    """First feed in the 'target' role, or None."""
    feeds = _feeds_with_role(event, NotificationFeedRole.TARGET)
    return feeds[0] if feeds else None


def event_payload(event) -> Dict[str, Any]:
    """Type-specific payload dict for ``event`` (never None)."""
    return event.payload or {}


# ---------------------------------------------------------------------------
# Email content builders (plain-HTML fallback when no template is configured)
# ---------------------------------------------------------------------------


def build_single_subject(event) -> str:
    template = _SINGLE_EMAIL_SUBJECT_DICTIONARY.get(event.notification_type_id)
    if template is None:
        return f"[Mobility Database] Notification for {event.notification_type_id}"

    if "%s" in template:
        return template % (subject_feed(event) or "unknown")
    return template


def build_digest_subject(events: List) -> str:
    count = len(events)
    type_id = events[0].notification_type_id if events else "notification"
    template = _DIGEST_EMAIL_SUBJECT_DICTIONARY.get(type_id)
    if template is None:
        return f"[Mobility Database] {count} notification{'s' if count != 1 else ''}"

    placeholder_count = template.count("%s")
    if placeholder_count == 2:
        return template % (count, "s" if count != 1 else "")
    if placeholder_count == 1:
        return template % count
    return template


def _event_row_dict(event) -> Dict[str, Any]:
    """Flatten a NotificationEvent into the row shape used both as Brevo
    template params (``build_params_feed_url_updated``) and as the Jinja
    template context for the HTML fallback (``build_single_html``/``build_digest_html``)."""
    payload = event_payload(event)
    subject_stable_id = subject_feed(event)
    target_stable_id = target_feed(event)
    return {
        "feed_stable_id": subject_stable_id,
        "feed_url": _feed_page_url(subject_stable_id),
        "target_feed_stable_id": target_stable_id,
        "target_feed_url": _feed_page_url(target_stable_id),
        "event_subtype": event.event_subtype,
        "old_url": payload.get("old_url") or "",
        "new_url": payload.get("new_url") or "",
        "provider": payload.get("provider") or "",
        "target_provider": payload.get("target_provider") or "",
        "source": event.source or "",
        "created_at": event.created_at.isoformat() if event.created_at else "",
        "payload": payload,
    }


def build_params_feed_url_updated(events: List, subscription):
    return {
        "event_count": len(events),
        "subscription_id": subscription.id,
        "events": [_event_row_dict(e) for e in events],
    }


def build_params_admin_event_summary(events: List, subscription):
    summary_event = events[0] if events else None
    return {
        "event_count": len(events),
        "subscription_id": subscription.id,
        "summary": event_payload(summary_event) if summary_event else {},
    }


def build_params_by_notification(
    notification_type_id: str, events: List[NotificationEvent], subscription
) -> Dict[str, Any]:
    match notification_type_id:
        case NotificationTypeId.FEED_URL_UPDATED:
            return build_params_feed_url_updated(events, subscription)
        case NotificationTypeId.ADMIN_EVENT_SUMMARY:
            return build_params_admin_event_summary(events, subscription)
        case _:
            raise ValueError(f"Unsupported notification type for Brevo params: {notification_type_id}")


def _subscription_footer_context(subscription) -> Dict[str, str]:
    """Context vars for the shared footer's "Manage subscriptions"/"Unsubscribe"
    links (see _base_email.html.j2). Empty when no subscription is available
    (e.g. a template rendered outside the subscription-driven send path)."""
    if subscription is None:
        return {}
    url = _subscriptions_management_url()
    return {"subscriptions_url": url, "unsubscribe_url": url}


def build_single_html(event, subscription=None) -> str:
    """Render the HTML-fallback body for a single-event email via Jinja2.

    Templates live in ``templates/`` alongside this module and are the single
    source of truth for fallback markup; Brevo-hosted templates (when
    configured) render server-side from the ``params`` dicts below instead.
    """
    if event.notification_type_id == NotificationTypeId.ADMIN_EVENT_SUMMARY:
        return build_admin_summary_html(event)
    row = _event_row_dict(event)
    context = {"row": row, **_subscription_footer_context(subscription)}
    return _jinja_env.get_template("feed_url_updated_single.html.j2").render(**context)


def build_admin_summary_html(event) -> str:
    """Render the dispatch-statistics summary for an ``admin.event_summary`` event."""
    return _jinja_env.get_template("admin_event_summary.html.j2").render(summary=event_payload(event))


def build_admin_digest_html(events: List) -> str:
    """Render one or more ``admin.event_summary`` events inside a single shared
    header/footer. Unlike concatenating ``build_admin_summary_html`` per event
    (each of which is a *full* HTML document), this renders exactly one
    document with one summary block per event."""
    summaries = [event_payload(e) for e in events]
    return _jinja_env.get_template("admin_event_summary_digest.html.j2").render(summaries=summaries)


def build_digest_html(events: List, subscription=None) -> str:
    if not events:
        return "<p>No feed URL changes in this period.</p>"

    if events[0].notification_type_id == NotificationTypeId.ADMIN_EVENT_SUMMARY:
        return build_admin_digest_html(events)

    rows = [_event_row_dict(e) for e in events]
    context = {"rows": rows, **_subscription_footer_context(subscription)}
    return _jinja_env.get_template("feed_url_updated_digest.html.j2").render(**context)


def send_single(
    recipient: EmailRecipient,
    notification_event: NotificationEvent,  # NotificationEvent ORM object
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
    template_id = get_template_id_by_notification(
        notification_event.notification_type_id,
        digest=False,
    )
    params = build_params_by_notification(
        notification_event.notification_type_id,
        [notification_event],
        subscription,
    )
    subject = build_single_subject(notification_event)
    # This is case the HTML fallback is used, so we don't need to pass html_content
    html = build_single_html(notification_event, subscription) if template_id is None else None

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

    template_id = get_template_id_by_notification(notification_type_id, digest=True)
    if template_id is None:
        logger.info(
            "No Brevo template configured for notification type %s; using HTML fallback",
            notification_type_id,
        )

    params = build_params_by_notification(
        notification_type_id,
        notification_events,
        subscription,
    )
    subject = build_digest_subject(notification_events)
    html = build_digest_html(notification_events, subscription) if template_id is None else None

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
        from sib_api_v3_sdk.rest import ApiException
    except ImportError as exc:
        raise BrevoSendError(f"sib_api_v3_sdk is not installed: {exc}") from exc

    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        raise BrevoSendError("BREVO_API_KEY environment variable is not set")

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key = {"api-key": api_key}

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
            "Brevo email sent (message_id=%s)",
            getattr(result, "message_id", "n/a"),
        )
    except ApiException as exc:
        raise BrevoSendError(f"Brevo API error {exc.status}: {exc.reason}") from exc
    except Exception as exc:
        raise BrevoSendError(f"Unexpected error sending email: {exc}") from exc


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
