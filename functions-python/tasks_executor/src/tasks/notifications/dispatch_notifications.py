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
from typing import Dict, List, Optional

from sqlalchemy import and_, not_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
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
DEFAULT_MAX_RETRIES = 5
_IN_RUN_RETRY_DELAYS = (1, 2, 4)  # seconds between in-run attempts

# TaskExecutionTracker task_name for a distributed dispatch run (fan-out workers
# + monitor all key off this plus a per-run run_id).
DISPATCH_TASK_NAME = "notifications_dispatch_run"

# A notification_log row left in 'pending' (claimed but not completed) for longer
# than this is treated as a crashed/abandoned claim and may be re-claimed by a
# later worker. Should comfortably exceed a single worker task's max runtime.
DEFAULT_STALE_CLAIM_SECONDS = 1800  # 30 minutes

# Cadence directive used by the single daily Cloud Scheduler job. When passed,
# the dispatcher always processes daily-cadence subscriptions and additionally
# processes weekly-cadence subscriptions only on ``weekly_weekday`` (so a single
# daily-running scheduler covers both cadences).
SCHEDULED_CADENCE = "scheduled"


# ---------------------------------------------------------------------------
# Cadence scheduling
# ---------------------------------------------------------------------------


def _resolve_scheduled_cadences(
    cadence: str,
    weekly_weekday: int,
    now: Optional[datetime] = None,
) -> List[str]:
    """Resolve the cadence directive into the concrete cadences to process.

    ``SCHEDULED_CADENCE`` lets a single daily-running scheduler cover both
    cadences: daily-cadence subscriptions run every day, while weekly-cadence
    subscriptions run only when today matches ``weekly_weekday`` (Monday=0).
    Any other value (``'daily'``/``'weekly'``/``'all'``/...) is passed through
    unchanged for backward compatibility and manual triggers.
    """
    if cadence != SCHEDULED_CADENCE:
        return [cadence]
    now = now or datetime.now(timezone.utc)
    cadences = [NotificationCadence.DAILY]
    if now.weekday() == weekly_weekday:
        cadences.append(NotificationCadence.WEEKLY)
    return cadences


def _commit_delivery_logs(db_session, subscription) -> None:
    """Durably persist the notification_log rows written for ``subscription``.

    Called after every email send so that an already-delivered email is always
    logged before the dispatcher continues. On failure the partial transaction
    is rolled back and the run continues (best-effort).
    """
    try:
        db_session.commit()
    except Exception:
        logger.exception(
            "Failed to commit notification logs for subscription %s; rolling back",
            subscription.id,
        )
        db_session.rollback()


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
    max_retries: int,
    stale_claim_seconds: int = DEFAULT_STALE_CLAIM_SECONDS,
) -> List[NotificationEvent]:
    """Return events that need to be (re-)sent for this subscription.

    The eligibility lower bound is always ``subscription.active_since`` (see
    ``_find_new_events``); there is no upper bound — events cannot be created in
    the future, and Cloud Tasks fan-out removes the need for window narrowing.

    Parameters
    ----------
    stale_claim_seconds:
        Age past which a ``pending`` (claimed-but-not-completed) log is treated
        as abandoned by a crashed worker and the event becomes re-claimable.
    """
    events: List[NotificationEvent] = []

    if status_filter in ("new", "all"):
        events += _find_new_events(
            db_session=db_session,
            subscription=subscription,
        )

    # Stale claims (pending logs from a crashed worker) are always recoverable,
    # independent of status_filter, so an interrupted send is never lost.
    events += _find_stale_pending_events(
        db_session=db_session,
        subscription=subscription,
        max_retries=max_retries,
        stale_claim_seconds=stale_claim_seconds,
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
) -> List[NotificationEvent]:
    """Events with no log row for this subscription, created on or after active_since.

    Lower-bound logic
    -----------------
    The lower bound is ``subscription.active_since`` — the moment the
    subscription last became active.  This ensures:

    * Events emitted **before the subscription was created** are never sent.
    * Events emitted **while the subscription was disabled** (the dead zone
      between deactivation and re-activation) are never sent.
    * Events that previously had no log row due to a mid-run crash are **always
      retried** on subsequent runs, regardless of how long ago they occurred.
    """
    # active_since is the eligibility gate: only events created after this
    # subscription last became active are eligible.  Fall back to created_at for
    # the transition period before the DB migration is applied and the model
    # regenerated — this is safe because created_at is the original
    # "subscription exists since" boundary.
    lower_bound: datetime = subscription.active_since or subscription.created_at
    # Normalize to UTC if the value is timezone-naive (e.g. SQLite in tests).
    if lower_bound.tzinfo is None:
        lower_bound = lower_bound.replace(tzinfo=timezone.utc)

    # IMPORTANT: exclude NULL notification_event_id rows. Legacy notification_log
    # rows (created before this column existed) have NULL here, and SQL
    # ``x NOT IN (<set containing NULL>)`` evaluates to NULL (never TRUE) for every
    # row — which would silently suppress ALL new events for the subscription.
    already_logged = select(NotificationLog.notification_event_id).where(
        NotificationLog.subscription_id == subscription.id,
        NotificationLog.notification_event_id.isnot(None),
    )
    q = (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.notification_type_id == subscription.notification_type_id,
            NotificationEvent.created_at >= lower_bound,
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


def _find_stale_pending_events(
    *,
    db_session: Session,
    subscription: NotificationSubscription,
    max_retries: int,
    stale_claim_seconds: int,
) -> List[NotificationEvent]:
    """Events with a 'pending' log older than the stale-claim lease.

    A 'pending' row is a claim written by a worker that then crashed before
    recording the terminal outcome.  Past the lease it is safe to re-claim and
    re-send (accepting a rare duplicate if the crash happened *after* Brevo
    accepted the email — the standard at-least-once trade-off).
    """
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=stale_claim_seconds)
    stale_logs = (
        db_session.query(NotificationLog)
        .filter(
            NotificationLog.subscription_id == subscription.id,
            NotificationLog.status == NotificationLogStatus.PENDING,
            NotificationLog.retry_count < max_retries,
            NotificationLog.notification_event_id.isnot(None),
            NotificationLog.sent_at < stale_before,
        )
        .all()
    )
    if not stale_logs:
        return []
    event_ids = [log.notification_event_id for log in stale_logs]
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

    # Count each event exactly once across the sent / failed / skipped / permanently
    # buckets so the admin.event_summary stats stay accurate.
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
            stats["emails_failed"] += 1
            if log.status == NotificationLogStatus.PERMANENTLY_FAILED:
                stats["permanently_failed"] += 1
        else:
            stats["emails_sent"] += 1


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


# ---------------------------------------------------------------------------
# Worker core: claim-then-send for a single subscription
# ---------------------------------------------------------------------------


def _claim_event(
    db_session: Session,
    event_id: str,
    subscription_id: str,
    channel: str,
    max_retries: int,
    stale_claim_seconds: int,
) -> Optional[NotificationLog]:
    """Atomically claim ``(event, subscription, channel)`` for sending.

    Returns the claimed ``NotificationLog`` if THIS worker won the claim, else
    ``None`` (another worker owns it, or it is already terminal). This is the
    lock-free concurrency guard: two workers processing the same subscription can
    never both send the same event because the claim is a single atomic write.

    A claim is won by either:
      * inserting a fresh ``pending`` row (no log existed yet), or
      * flipping an existing ``failed`` row, or a STALE ``pending`` row (crashed
        worker), to ``pending`` — guarded by status/age so only one worker wins.
    """
    now = datetime.now(timezone.utc)

    # 1) New event: insert a pending claim; ON CONFLICT DO NOTHING means a
    #    concurrent worker that already inserted wins and we fall through.
    ins = (
        insert(NotificationLog)
        .values(
            id=str(uuid.uuid4()),
            notification_event_id=event_id,
            subscription_id=subscription_id,
            channel=channel,
            status=NotificationLogStatus.PENDING,
            retry_count=0,
            sent_at=now,
        )
        .on_conflict_do_nothing(
            constraint="uq_notification_log_event_sub_channel",
        )
    )
    if db_session.execute(ins).rowcount == 1:
        db_session.flush()
        return _get_log(db_session, event_id, subscription_id, channel)

    # 2) Existing row: claim only if it is retryable (failed) or a stale pending
    #    claim. The WHERE guard makes exactly one concurrent worker succeed.
    stale_before = now - timedelta(seconds=stale_claim_seconds)
    upd = (
        update(NotificationLog)
        .where(
            NotificationLog.notification_event_id == event_id,
            NotificationLog.subscription_id == subscription_id,
            NotificationLog.channel == channel,
            NotificationLog.retry_count < max_retries,
            or_(
                NotificationLog.status == NotificationLogStatus.FAILED,
                and_(
                    NotificationLog.status == NotificationLogStatus.PENDING,
                    NotificationLog.sent_at < stale_before,
                ),
            ),
        )
        .values(status=NotificationLogStatus.PENDING, sent_at=now)
        .returning(NotificationLog.id)
    )
    claimed_id = db_session.execute(upd).scalar_one_or_none()
    db_session.flush()
    if claimed_id is None:
        return None
    return _get_log(db_session, event_id, subscription_id, channel)


def _get_log(
    db_session: Session, event_id: str, subscription_id: str, channel: str
) -> NotificationLog:
    return (
        db_session.query(NotificationLog)
        .filter_by(
            notification_event_id=event_id,
            subscription_id=subscription_id,
            channel=channel,
        )
        .one()
    )


def _new_stats() -> Dict[str, int]:
    return {
        "events_found": 0,
        "events_claimed": 0,
        "emails_sent": 0,
        "emails_failed": 0,
        "permanently_failed": 0,
        "skipped_max_retries": 0,
        "skipped_not_claimed": 0,
    }


@with_users_db_session
def process_subscription(
    *,
    subscription_id: str,
    status_filter: str = "new",
    max_retries: int = DEFAULT_MAX_RETRIES,
    stale_claim_seconds: int = DEFAULT_STALE_CLAIM_SECONDS,
    db_session: Session = None,
) -> Dict[str, int]:
    """Process a single subscription's pending notifications (Cloud Tasks worker).

    Finds candidate events, atomically claims each (claim-then-send, so concurrent
    workers never duplicate an email), sends via Brevo, and commits the log after
    every send so an already-delivered email can never be rolled back.
    """
    stats = _new_stats()

    subscription = (
        db_session.query(NotificationSubscription)
        .filter(NotificationSubscription.id == subscription_id)
        .one_or_none()
    )
    if subscription is None or not subscription.active:
        logger.info(
            "process_subscription: %s missing or inactive; nothing to do",
            subscription_id,
        )
        return stats

    user = subscription.user
    if user is None or not user.email:
        logger.warning(
            "process_subscription: subscription %s has no usable user/email",
            subscription_id,
        )
        return stats

    events = find_events_for_subscription(
        db_session=db_session,
        subscription=subscription,
        status_filter=status_filter,
        max_retries=max_retries,
        stale_claim_seconds=stale_claim_seconds,
    )
    stats["events_found"] = len(events)
    if not events:
        return stats

    # Claim every candidate atomically; only the events this worker wins proceed.
    claimed: List[NotificationEvent] = []
    for event in events:
        log = _claim_event(
            db_session,
            event.id,
            subscription.id,
            "email",
            max_retries,
            stale_claim_seconds,
        )
        if log is None:
            stats["skipped_not_claimed"] += 1
            continue
        claimed.append(event)
    # Persist the claims before sending so a crash can't lose them.
    _commit_delivery_logs(db_session, subscription)
    stats["events_claimed"] = len(claimed)
    if not claimed:
        return stats

    recipient = EmailRecipient(email=user.email, name=user.full_name)

    if subscription.digest:
        _send_and_log_digest(
            db_session=db_session,
            recipient=recipient,
            events=claimed,
            subscription=subscription,
            stats=stats,
            max_retries=max_retries,
        )
        _commit_delivery_logs(db_session, subscription)
    else:
        for event in claimed:
            _send_and_log_single(
                db_session=db_session,
                recipient=recipient,
                event=event,
                subscription=subscription,
                stats=stats,
                max_retries=max_retries,
            )
            _commit_delivery_logs(db_session, subscription)

    logger.info(
        "process_subscription %s: found=%d claimed=%d sent=%d failed=%d",
        subscription_id,
        stats["events_found"],
        stats["events_claimed"],
        stats["emails_sent"],
        stats["emails_failed"],
    )
    return stats


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
