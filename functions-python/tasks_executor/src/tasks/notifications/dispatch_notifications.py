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
"""dispatch_notifications — match notification_event rows to active subscriptions,
send emails, and record delivery in notification_log.

Invoked by Cloud Scheduler (daily / weekly) or triggered manually via the
tasks_executor. See ``docs/notifications.md`` for the full architecture,
payload reference, retry strategy, active_since semantics, and operational
runbook.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import not_, select
from sqlalchemy.orm import Session

from shared.database.users_database import with_users_db_session
from shared.notifications.brevo_notification_sender import (
    BrevoSendError,
    EmailRecipient,
    get_brevo_rate_limiter,
    send_digest,
    send_single,
)
from shared.notifications.notification_constants import (
    AdminEventUpdateType,
    NotificationCadence,
    NotificationLogStatus,
    NotificationSource,
    NotificationTypeId,
)
from shared.users_database_gen.sqlacodegen_models import (
    AppUser,
    NotificationEvent,
    NotificationLog,
    NotificationSubscription,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_CADENCE = NotificationCadence.WEEKLY
DEFAULT_MAX_RETRIES = 5
_IN_RUN_RETRY_DELAYS = (1, 2, 4)  # seconds between in-run attempts

# Time windows per cadence (look-back for finding relevant events)
_CADENCE_WINDOWS: Dict[str, timedelta] = {
    NotificationCadence.IMMEDIATE: timedelta(hours=1),
    NotificationCadence.DAILY: timedelta(days=1),
    NotificationCadence.WEEKLY: timedelta(weeks=1),
}


# ---------------------------------------------------------------------------
# Public handler
# ---------------------------------------------------------------------------


def dispatch_notifications_handler(
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Cloud Function / tasks_executor entrypoint.

    Parameters are taken from ``payload``; see module docstring for full list.
    """
    payload = payload or {}
    logger.info("dispatch_notifications_handler called with payload=%s", payload)

    cadence: str = payload.get("cadence", DEFAULT_CADENCE)
    dry_run: bool = bool(payload.get("dry_run", True))
    status_filter: str = payload.get("status_filter", "new")
    user_ids: List[str] = payload.get("user_ids", [])
    force: bool = bool(payload.get("force", False))
    since_dt: Optional[str] = payload.get("since_dt")
    until_dt: Optional[str] = payload.get("until_dt")
    max_retries: int = int(payload.get("max_retries", DEFAULT_MAX_RETRIES))

    result = dispatch(
        cadence=cadence,
        dry_run=dry_run,
        status_filter=status_filter,
        user_ids=user_ids,
        force=force,
        since_dt=since_dt,
        until_dt=until_dt,
        max_retries=max_retries,
    )
    logger.info("dispatch_notifications_handler result: %s", result)
    return result


# ---------------------------------------------------------------------------
# Core dispatcher
# ---------------------------------------------------------------------------


@with_users_db_session
def dispatch(
    *,
    cadence: str,
    dry_run: bool,
    status_filter: str,
    user_ids: List[str],
    force: bool,
    since_dt: Optional[str],
    until_dt: Optional[str],
    max_retries: int,
    db_session: Session = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    until = _parse_dt(until_dt) or now
    # explicit_since: only set when the caller explicitly provided since_dt.
    # Used as an additional lower-bound floor in _find_new_events on top of
    # each subscription's active_since.  Never replaces active_since.
    explicit_since: Optional[datetime] = _parse_dt(since_dt)
    # since is kept for logging only; it is no longer used as the correctness
    # gate for new-event discovery (active_since fills that role).
    since = explicit_since or (
        now
        - _CADENCE_WINDOWS.get(cadence, _CADENCE_WINDOWS[NotificationCadence.WEEKLY])
    )

    logger.info(
        "Dispatching cadence=%s status_filter=%s window=[%s, %s] dry_run=%s user_ids=%s",
        cadence,
        status_filter,
        since.isoformat(),
        until.isoformat(),
        dry_run,
        user_ids or "all",
    )

    stats: Dict[str, int] = {
        "subscriptions_processed": 0,
        "events_found": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "permanently_failed": 0,
        "skipped_max_retries": 0,
        "dry_run": int(dry_run),
    }

    # Find active subscriptions to process.
    subscriptions = find_subscriptions(
        db_session=db_session,
        cadence=cadence,
        user_ids=user_ids,
        force=force,
    )
    logger.info("Found %d active subscription(s) to process", len(subscriptions))

    for subscription in subscriptions:
        stats["subscriptions_processed"] += 1
        user = subscription.user

        # Collect notification_events that need a delivery log for this subscription.
        events = find_events_for_subscription(
            db_session=db_session,
            subscription=subscription,
            status_filter=status_filter,
            explicit_since=explicit_since,
            until=until,
            max_retries=max_retries,
        )
        if not events:
            continue

        stats["events_found"] += len(events)
        logger.info(
            "Subscription %s (user=%s cadence=%s digest=%s): %d event(s)",
            subscription.id,
            user.email if user else "?",
            subscription.cadence,
            subscription.digest,
            len(events),
        )

        if dry_run:
            logger.info(
                "[dry_run] Would send %d event(s) to %s",
                len(events),
                user.email if user else "?",
            )
            continue

        recipient = EmailRecipient(
            email=user.email,
            name=user.full_name,
        )

        if subscription.digest:
            _send_and_log_digest(
                db_session=db_session,
                recipient=recipient,
                events=events,
                subscription=subscription,
                stats=stats,
                max_retries=max_retries,
            )
        else:
            for event in events:
                _send_and_log_single(
                    db_session=db_session,
                    recipient=recipient,
                    event=event,
                    subscription=subscription,
                    stats=stats,
                    max_retries=max_retries,
                )

    # After the run, emit an admin.event_summary notification_event.
    if not dry_run:
        emit_admin_summary(db_session=db_session, stats=stats, cadence=cadence)

    return stats


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def find_subscriptions(
    *,
    db_session: Session,
    cadence: str,
    user_ids: List[str],
    force: bool,
) -> List[NotificationSubscription]:
    """Return active subscriptions matching the cadence (or all if force=True)."""
    q = (
        db_session.query(NotificationSubscription)
        .join(AppUser, NotificationSubscription.user_id == AppUser.id)
        .filter(NotificationSubscription.active == True)  # noqa: E712
    )
    if not (force and user_ids):
        # Normal (non-forced) run: filter by cadence.
        if cadence != "all":
            q = q.filter(NotificationSubscription.cadence == cadence)
    if user_ids:
        q = q.filter(NotificationSubscription.user_id.in_(user_ids))
    return q.all()


def find_events_for_subscription(
    *,
    db_session: Session,
    subscription: NotificationSubscription,
    status_filter: str,
    explicit_since: Optional[datetime] = None,
    until: datetime,
    max_retries: int,
) -> List[NotificationEvent]:
    """Return events that need to be (re-)sent for this subscription.

    Parameters
    ----------
    explicit_since:
        Optional caller-provided lower bound (from ``since_dt`` payload param).
        When set, the effective lower bound for new-event discovery becomes
        ``max(subscription.active_since, explicit_since)``.  It can only
        *narrow* the window further — it cannot expand it past ``active_since``.
    until:
        Upper bound for new-event discovery (exclusive for failed events).
    """
    events: List[NotificationEvent] = []

    if status_filter in ("new", "all"):
        events += _find_new_events(
            db_session=db_session,
            subscription=subscription,
            explicit_since=explicit_since,
            until=until,
        )

    if status_filter in ("failed", "all"):
        events += _find_failed_events(
            db_session=db_session,
            subscription=subscription,
            max_retries=max_retries,
        )

    # Deduplicate (an event shouldn't appear in both lists).
    seen: set = set()
    deduped = []
    for e in events:
        if e.id not in seen:
            seen.add(e.id)
            deduped.append(e)
    return deduped


def _find_new_events(
    *,
    db_session: Session,
    subscription: NotificationSubscription,
    explicit_since: Optional[datetime],
    until: datetime,
) -> List[NotificationEvent]:
    """Events with no log row for this subscription, created on or after active_since.

    Lower-bound logic
    -----------------
    The primary lower bound is ``subscription.active_since`` — the moment the
    subscription last became active.  This ensures:

    * Events emitted **before the subscription was created** are never sent.
    * Events emitted **while the subscription was disabled** (the dead zone
      between deactivation and re-activation) are never sent.
    * Events that previously had no log row due to a mid-run crash are **always
      retried** on subsequent runs, regardless of how long ago they occurred.

    If the caller provided an explicit ``since_dt`` override, the effective lower
    bound is ``max(active_since, explicit_since)`` so the override can only
    *further narrow* the window, never widen it past the eligibility floor.
    """
    # Compute the effective lower bound.
    # active_since is the primary gate: only events created after this subscription
    # last became active are eligible.  Fall back to created_at for the transition
    # period before the DB migration is applied and the model regenerated — this is
    # safe because created_at is the original "subscription exists since" boundary.

    lower_bound: datetime = subscription.active_since or subscription.created_at
    # Normalize to UTC if the value is timezone-naive (e.g. SQLite in tests).
    if lower_bound.tzinfo is None:
        lower_bound = lower_bound.replace(tzinfo=timezone.utc)
    if explicit_since is not None and explicit_since > lower_bound:
        lower_bound = explicit_since

    already_logged = select(NotificationLog.notification_event_id).where(
        NotificationLog.subscription_id == subscription.id
    )
    q = (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.notification_type_id == subscription.notification_type_id,
            NotificationEvent.created_at >= lower_bound,
            NotificationEvent.created_at <= until,
            not_(NotificationEvent.id.in_(already_logged)),
        )
        .order_by(NotificationEvent.created_at.asc())
    )
    events = q.all()
    return apply_filter_params(events, subscription)


def _find_failed_events(
    *,
    db_session: Session,
    subscription: NotificationSubscription,
    max_retries: int,
) -> List[NotificationEvent]:
    """Events whose log row has status='failed' and retry_count < max_retries."""
    failed_logs = (
        db_session.query(NotificationLog)
        .filter(
            NotificationLog.subscription_id == subscription.id,
            NotificationLog.status == NotificationLogStatus.FAILED,
            NotificationLog.retry_count < max_retries,
            NotificationLog.notification_event_id.isnot(None),
        )
        .all()
    )
    if not failed_logs:
        return []
    event_ids = [log.notification_event_id for log in failed_logs]
    events = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id.in_(event_ids))
        .all()
    )
    return apply_filter_params(events, subscription)


def apply_filter_params(
    events: List[NotificationEvent],
    subscription: NotificationSubscription,
) -> List[NotificationEvent]:
    """Filter events against subscription.filter_params.

    Supported keys:
      ``feed_ids``: list of feed stable_ids — only return events that reference
                    at least one of those feeds (in any role).
      ``None`` / missing key → all events pass.
    """
    fp = subscription.filter_params
    if not fp:
        return events
    allowed_feed_ids = fp.get("feed_ids")
    if not allowed_feed_ids:
        return events
    allowed = set(allowed_feed_ids)
    return [e for e in events if _event_feed_ids(e) & allowed]


def _event_feed_ids(event: NotificationEvent) -> set:
    """Set of feed stable_ids referenced by an event (across all roles)."""
    return {
        f.feed_stable_id
        for f in (getattr(event, "notification_event_feeds", None) or [])
    }


# ---------------------------------------------------------------------------
# Send + log helpers
# ---------------------------------------------------------------------------


def _send_and_log_single(
    *,
    db_session: Session,
    recipient: EmailRecipient,
    event: NotificationEvent,
    subscription: NotificationSubscription,
    stats: Dict[str, int],
    max_retries: int,
) -> None:
    """Attempt to send a single-event email; write or update a NotificationLog row."""
    log = _get_or_create_log(db_session, event.id, subscription.id, "email")

    if log.retry_count >= max_retries:
        logger.warning(
            "Skipping event %s / sub %s: reached max_retries=%d",
            event.id,
            subscription.id,
            max_retries,
        )
        if log.status != NotificationLogStatus.PERMANENTLY_FAILED:
            log.status = NotificationLogStatus.PERMANENTLY_FAILED
            db_session.flush()
        stats["skipped_max_retries"] += 1
        return

    error = _attempt_send(lambda: send_single(recipient, event, subscription))
    _update_log(db_session, log, error, max_retries)

    if error:
        stats["emails_failed"] += 1
        if log.status == NotificationLogStatus.PERMANENTLY_FAILED:
            stats["permanently_failed"] += 1
    else:
        stats["emails_sent"] += 1


def _send_and_log_digest(
    *,
    db_session: Session,
    recipient: EmailRecipient,
    events: List[NotificationEvent],
    subscription: NotificationSubscription,
    stats: Dict[str, int],
    max_retries: int,
) -> None:
    """Attempt to send a digest email; write or update NotificationLog rows for all events."""
    # For digests: attempt the send once; apply the same result to all event logs.
    error = _attempt_send(lambda: send_digest(recipient, events, subscription))

    for event in events:
        log = _get_or_create_log(db_session, event.id, subscription.id, "email")
        if log.retry_count >= max_retries:
            if log.status != NotificationLogStatus.PERMANENTLY_FAILED:
                log.status = NotificationLogStatus.PERMANENTLY_FAILED
                db_session.flush()
            stats["skipped_max_retries"] += 1
            continue
        _update_log(db_session, log, error, max_retries)

    if error:
        stats["emails_failed"] += len(events)
        failed_permanently = sum(
            1
            for e in events
            if _get_log_status(db_session, e.id, subscription.id)
            == NotificationLogStatus.PERMANENTLY_FAILED
        )
        stats["permanently_failed"] += failed_permanently
    else:
        stats["emails_sent"] += len(events)


def _attempt_send(send_fn) -> Optional[str]:
    """Call ``send_fn()`` up to 3× with back-off. Return None on success, error str on failure.

    Each attempt (including retries) first acquires a token from the shared
    Brevo rate limiter so the dispatch run never exceeds Brevo's rps limit.
    """
    rate_limiter = get_brevo_rate_limiter()
    last_error: Optional[str] = None
    for i, delay in enumerate((*_IN_RUN_RETRY_DELAYS, None)):
        rate_limiter.acquire()
        try:
            send_fn()
            return None
        except BrevoSendError as exc:
            last_error = str(exc)
            logger.warning(
                "Send attempt %d/%d failed: %s",
                i + 1,
                len(_IN_RUN_RETRY_DELAYS) + 1,
                exc,
            )
            if delay is not None:
                time.sleep(delay)
    return last_error


def _get_or_create_log(
    db_session: Session,
    event_id: str,
    subscription_id: str,
    channel: str,
) -> NotificationLog:
    """Return the existing NotificationLog for (event, subscription, channel) or create one."""
    log = (
        db_session.query(NotificationLog)
        .filter_by(
            notification_event_id=event_id,
            subscription_id=subscription_id,
            channel=channel,
        )
        .one_or_none()
    )
    if log is None:
        log = NotificationLog(
            id=str(uuid.uuid4()),
            notification_event_id=event_id,
            subscription_id=subscription_id,
            channel=channel,
            status=NotificationLogStatus.FAILED,  # optimistic: overwritten below
            retry_count=0,
        )
        db_session.add(log)
        db_session.flush()
    return log


def _update_log(
    db_session: Session,
    log: NotificationLog,
    error: Optional[str],
    max_retries: int,
) -> None:
    """Update log status and retry_count after a send attempt."""
    if error is None:
        log.status = NotificationLogStatus.SENT
        log.error_message = None
    else:
        log.retry_count += 1
        log.error_message = error
        if log.retry_count >= max_retries:
            log.status = NotificationLogStatus.PERMANENTLY_FAILED
            logger.error(
                "Notification log %s permanently failed after %d retries: %s",
                log.id,
                log.retry_count,
                error,
            )
        else:
            log.status = NotificationLogStatus.FAILED
    log.sent_at = datetime.now(timezone.utc)
    db_session.flush()


def _get_log_status(
    db_session: Session, event_id: str, subscription_id: str
) -> Optional[str]:
    log = (
        db_session.query(NotificationLog.status)
        .filter_by(
            notification_event_id=event_id,
            subscription_id=subscription_id,
            channel="email",
        )
        .scalar()
    )
    return log


# ---------------------------------------------------------------------------
# admin.event_summary
# ---------------------------------------------------------------------------


def emit_admin_summary(
    *,
    db_session: Session,
    stats: Dict[str, int],
    cadence: str,
) -> None:
    """Create an admin.event_summary notification_event with dispatch statistics."""
    event = NotificationEvent(
        id=str(uuid.uuid4()),
        notification_type_id=NotificationTypeId.ADMIN_EVENT_SUMMARY,
        event_subtype=AdminEventUpdateType.DISPATCH_SUMMARY,
        source=NotificationSource.DISPATCHER,
        payload={**stats, "cadence": cadence},
    )
    db_session.add(event)
    db_session.flush()
    logger.info("admin.event_summary created: id=%s stats=%s", event.id, stats)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        logger.warning("Could not parse datetime %r; ignoring", value)
        return None
