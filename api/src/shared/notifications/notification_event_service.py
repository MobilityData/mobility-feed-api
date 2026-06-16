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
"""notification_event_service — best-effort writers for notification_event rows.

Design principles
-----------------
* Each public function writes a single notification_event row to the users DB.
* All functions are **fire-and-forget**: errors are logged and swallowed so that
  the calling feed-change code is never blocked or rolled back.
* If ``USERS_DATABASE_URL`` is not configured (e.g. in the populate_db CI scripts
  that only have access to the feeds DB), the call is a no-op with a warning.

Usage
-----
    from shared.notifications.notification_event_service import (
        emit_feed_redirected,
        emit_url_replaced,
    )

    # After creating a Redirectingid row:
    emit_feed_redirected(
        source_stable_id="mdb-1",
        target_stable_id="tdg-42",
        old_url="https://old.example.com/feed.zip",
        new_url="https://new.example.com/feed.zip",
        source="tdg_redirects",
    )

    # After detecting a producer_url change:
    emit_url_replaced(
        feed_stable_id="mdb-7",
        old_url="https://old.example.com/feed.zip",
        new_url="https://new.example.com/feed.zip",
        source="tdg_import",
    )
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from shared.notifications.notification_constants import (
    FeedUrlUpdateType,
    NotificationFeedRole,
    NotificationTypeId,
)

logger = logging.getLogger(__name__)


def normalize_url(url: Optional[str]) -> str:
    """Normalize a producer URL for change detection.

    Comparisons should ignore case and leading/trailing whitespace so that
    cosmetic differences (e.g. ``" HTTPS://Example.com "`` vs
    ``"https://example.com"``) do not trigger a notification event.
    """
    if url is None:
        return ""
    return url.strip().casefold()


def urls_differ(old_url: Optional[str], new_url: Optional[str]) -> bool:
    """Return True if two URLs differ after normalization (case/whitespace-insensitive)."""
    return normalize_url(old_url) != normalize_url(new_url)


def emit_feed_redirected(
    source_stable_id: str,
    target_stable_id: str,
    old_url: Optional[str],
    new_url: Optional[str],
    source: str,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Create a ``feed.url_updated / feed_redirected`` notification_event.

    Called when a new ``Redirectingid`` row is created — meaning a feed has been
    deprecated and now points users to a different feed.

    Parameters
    ----------
    source_stable_id:
        stable_id of the feed that is being deprecated (the source of the redirect).
    target_stable_id:
        stable_id of the feed that subscribers should follow instead.
    old_url:
        producer_url of the source feed at deprecation time (may be None).
    new_url:
        producer_url of the target feed (may be None).
    source:
        Human-readable tag identifying the process that triggered this
        (e.g. ``NotificationSource.TDG_REDIRECTS``).
    extra_data:
        Optional extra free-form JSON merged into the event payload
        (e.g. redirect_comment).
    """
    payload: Dict[str, Any] = {"old_url": old_url, "new_url": new_url}
    if extra_data:
        payload.update(extra_data)
    _emit(
        notification_type_id=NotificationTypeId.FEED_URL_UPDATED,
        event_subtype=FeedUrlUpdateType.FEED_REDIRECTED,
        source=source,
        feeds=[
            (source_stable_id, NotificationFeedRole.SUBJECT),
            (target_stable_id, NotificationFeedRole.TARGET),
        ],
        payload=payload,
    )


def emit_url_replaced(
    feed_stable_id: str,
    old_url: str,
    new_url: str,
    source: str,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Create a ``feed.url_updated / url_replaced`` notification_event.

    Called when automation changes ``Feed.producer_url`` **in-place** — the feed
    keeps the same ``stable_id`` but its source URL has changed.

    Only emit when the URLs differ after normalization (case- and
    surrounding-whitespace-insensitive); identical URLs are skipped.

    Parameters
    ----------
    feed_stable_id:
        stable_id of the feed whose URL changed.
    old_url:
        The previous producer_url value.
    new_url:
        The new producer_url value.
    source:
        Human-readable tag identifying the process (e.g. ``NotificationSource.TDG_IMPORT``).
    extra_data:
        Optional extra free-form JSON merged into the event payload.
    """
    if not urls_differ(old_url, new_url):
        logger.debug(
            "Skipping url_replaced event for %s: URLs are equivalent after normalization",
            feed_stable_id,
        )
        return
    payload: Dict[str, Any] = {"old_url": old_url, "new_url": new_url}
    if extra_data:
        payload.update(extra_data)
    _emit(
        notification_type_id=NotificationTypeId.FEED_URL_UPDATED,
        event_subtype=FeedUrlUpdateType.URL_REPLACED,
        source=source,
        feeds=[(feed_stable_id, NotificationFeedRole.SUBJECT)],
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _emit(
    notification_type_id: str,
    event_subtype: str,
    source: str,
    feeds: Optional[List[Tuple[str, str]]] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one notification_event row (plus its notification_event_feed rows)
    to the users DB.

    Parameters
    ----------
    notification_type_id:
        Row id in ``notification_type`` (e.g. ``feed.url_updated``).
    event_subtype:
        Discriminator within the type (e.g. ``url_replaced``).
    source:
        Tag identifying the emitting process.
    feeds:
        Optional list of ``(feed_stable_id, role)`` tuples relating this event to
        one-or-more feeds. ``role`` is a ``NotificationFeedRole`` value.
    payload:
        Optional type-specific JSON payload.

    Gracefully degrades if the users DB is unavailable:
    - ``USERS_DATABASE_URL`` not set → log warning, return.
    - Any DB error → log exception, return.

    This ensures that feed-change code paths are never blocked.
    """
    try:
        # Import here to avoid circular imports and to allow graceful degradation
        # when the users DB is not configured (e.g. populate_db CI scripts).
        from shared.database.users_database import UsersDatabase
        from shared.users_database_gen.sqlacodegen_models import (
            NotificationEvent,
            NotificationEventFeed,
        )
    except ImportError as exc:
        logger.warning("notification_event_service: import error, skipping emit: %s", exc)
        return

    try:
        db = UsersDatabase()
    except Exception as exc:
        primary_feed = feeds[0][0] if feeds else None
        logger.warning(
            "notification_event_service: users DB unavailable (%s), " "skipping %s/%s for feed=%s",
            exc,
            notification_type_id,
            event_subtype,
            primary_feed,
        )
        return

    event_id = str(uuid.uuid4())
    event = NotificationEvent(
        id=event_id,
        notification_type_id=notification_type_id,
        event_subtype=event_subtype,
        source=source,
        payload=payload,
    )
    feed_rows = [
        NotificationEventFeed(
            id=str(uuid.uuid4()),
            notification_event_id=event_id,
            feed_stable_id=feed_stable_id,
            role=role,
        )
        for feed_stable_id, role in (feeds or [])
    ]

    primary_feed = feeds[0][0] if feeds else None
    try:
        with db.start_db_session() as session:
            session.add(event)
            for feed_row in feed_rows:
                session.add(feed_row)
        logger.info(
            "notification_event created: type=%s subtype=%s feeds=%s source=%s id=%s",
            notification_type_id,
            event_subtype,
            [f[0] for f in (feeds or [])],
            source,
            event_id,
        )
    except Exception as exc:
        logger.exception(
            "notification_event_service: failed to persist event " "type=%s subtype=%s feed=%s: %s",
            notification_type_id,
            event_subtype,
            primary_feed,
            exc,
        )
