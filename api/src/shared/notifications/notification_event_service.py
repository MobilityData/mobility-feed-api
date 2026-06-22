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
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from shared.database.users_database import with_users_db_session
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

    The event is written immediately and best-effort (see :func:`_emit`). It is
    fire-and-forget: if the surrounding feed-change transaction is later rolled
    back, the event row remains. This is an accepted trade-off — duplicate or
    rare spurious events are bounded by the dispatcher, which commits its
    delivery log after every send.
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

    The event is written immediately and best-effort (see :func:`_emit`). It is
    fire-and-forget: if the surrounding feed-change transaction is later rolled
    back, the event row remains. This is an accepted trade-off — duplicate or
    rare spurious events are bounded by the dispatcher, which commits its
    delivery log after every send.
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
    to the users DB, immediately and best-effort.

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

    Fire-and-forget: any failure is logged and swallowed so the calling
    feed-change code is never blocked or rolled back. If ``USERS_DATABASE_URL``
    is not configured (e.g. the populate_db CI scripts that only reach the feeds
    DB), the call is a no-op with a warning.
    """
    load_dotenv()
    if not os.getenv("USERS_DATABASE_URL"):
        primary_feed = feeds[0][0] if feeds else None
        logger.warning(
            "notification_event_service: USERS_DATABASE_URL not configured; " "skipping %s/%s for feed=%s",
            notification_type_id,
            event_subtype,
            primary_feed,
        )
        return
    try:
        _persist_event(
            notification_type_id=notification_type_id,
            event_subtype=event_subtype,
            source=source,
            feeds=feeds,
            payload=payload,
        )
    except Exception as exc:
        primary_feed = feeds[0][0] if feeds else None
        logger.exception(
            "notification_event_service: failed to persist event " "type=%s subtype=%s feed=%s: %s",
            notification_type_id,
            event_subtype,
            primary_feed,
            exc,
        )


@with_users_db_session
def _persist_event(
    notification_type_id: str,
    event_subtype: str,
    source: str,
    feeds: Optional[List[Tuple[str, str]]] = None,
    payload: Optional[Dict[str, Any]] = None,
    db_session=None,
) -> None:
    """Insert the notification_event (and its feed rows) on ``db_session``.

    Wrapped by :func:`with_users_db_session`, which opens a users-DB session and
    commits when this function returns. Exceptions propagate to :func:`_emit`,
    which logs and swallows them.
    """
    from shared.users_database_gen.sqlacodegen_models import (
        NotificationEvent,
        NotificationEventFeed,
    )

    event_id = str(uuid.uuid4())
    db_session.add(
        NotificationEvent(
            id=event_id,
            notification_type_id=notification_type_id,
            event_subtype=event_subtype,
            source=source,
            payload=payload,
        )
    )
    for feed_stable_id, role in feeds or []:
        db_session.add(
            NotificationEventFeed(
                id=str(uuid.uuid4()),
                notification_event_id=event_id,
                feed_stable_id=feed_stable_id,
                role=role,
            )
        )
    logger.info(
        "notification_event created: type=%s subtype=%s feeds=%s source=%s id=%s",
        notification_type_id,
        event_subtype,
        [f[0] for f in (feeds or [])],
        source,
        event_id,
    )
