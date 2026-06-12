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
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
        Optional free-form JSON payload (e.g. redirect_comment).
    """
    _emit(
        notification_type_id="feed.url_updated",
        update_type="feed_redirected",
        feed_stable_id=source_stable_id,
        target_feed_stable_id=target_stable_id,
        old_url=old_url,
        new_url=new_url,
        source=source,
        extra_data=extra_data,
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

    Only emit when ``old_url != new_url`` (callers are responsible for this check).

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
        Optional free-form JSON payload.
    """
    _emit(
        notification_type_id="feed.url_updated",
        update_type="url_replaced",
        feed_stable_id=feed_stable_id,
        old_url=old_url,
        new_url=new_url,
        source=source,
        extra_data=extra_data,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _emit(
    notification_type_id: str,
    update_type: str,
    source: str,
    feed_stable_id: Optional[str] = None,
    target_feed_stable_id: Optional[str] = None,
    old_url: Optional[str] = None,
    new_url: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Write one notification_event row to the users DB.

    Gracefully degrades if the users DB is unavailable:
    - ``USERS_DATABASE_URL`` not set → log warning, return.
    - Any DB error → log exception, return.

    This ensures that feed-change code paths are never blocked.
    """
    try:
        # Import here to avoid circular imports and to allow graceful degradation
        # when the users DB is not configured (e.g. populate_db CI scripts).
        from shared.database.users_database import UsersDatabase
        from shared.users_database_gen.sqlacodegen_models import NotificationEvent
    except ImportError as exc:
        logger.warning("notification_event_service: import error, skipping emit: %s", exc)
        return

    try:
        db = UsersDatabase()
    except Exception as exc:
        logger.warning(
            "notification_event_service: users DB unavailable (%s), " "skipping %s/%s for feed=%s",
            exc,
            notification_type_id,
            update_type,
            feed_stable_id,
        )
        return

    event = NotificationEvent(
        id=str(uuid.uuid4()),
        notification_type_id=notification_type_id,
        update_type=update_type,
        feed_stable_id=feed_stable_id,
        target_feed_stable_id=target_feed_stable_id,
        old_url=old_url,
        new_url=new_url,
        source=source,
        extra_data=extra_data,
    )

    try:
        with db.start_db_session() as session:
            session.add(event)
        logger.info(
            "notification_event created: type=%s update_type=%s feed=%s source=%s id=%s",
            notification_type_id,
            update_type,
            feed_stable_id,
            source,
            event.id,
        )
    except Exception as exc:
        logger.exception(
            "notification_event_service: failed to persist event " "type=%s update_type=%s feed=%s: %s",
            notification_type_id,
            update_type,
            feed_stable_id,
            exc,
        )
