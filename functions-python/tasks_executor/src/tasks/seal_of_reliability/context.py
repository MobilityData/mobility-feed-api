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
"""Seal eligibility (query + Python predicate) and bulk loading of evaluator inputs.

The evaluators are pure functions over a `FeedSealContext`, so every DB read for a batch of
feeds happens here, in a fixed number of queries regardless of batch size.

A criterion's inputs reach it one of two ways, and the split is deliberate:

* Day-invariant feed facts — `official`, `seasonal`, `is_producer_url_unstable`,
  `created_at` — are fields on `FeedSealContext`, read straight off the feed row the caller
  has already loaded. They cost no query and they have no history to read: the same value
  answers every day of a backfill. Official and Stable need nothing else.
* Anything that varies by day is loaded by the criterion itself, through
  `CriterionEvaluator.load_inputs`. Only the criterion knows what its own inputs look like,
  and keeping that knowledge there is what stops this module from having to grow a field
  and a query for every criterion added. Fresh (future coverage) is the first of these — the
  feed's latest dataset is a different row on each day a march evaluates — and the day's
  availability rows for Available, the latest validation report for Compliant and the full
  coverage history for Fresh continuous coverage all belong there too.

Official, Stable and Fresh (future coverage) are implemented; Available and Compliant are
the rest of #1784, and Fresh / continuous coverage is tracked by #1782.
"""

import itertools
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from shared.common.seal_criteria import SealCriterionName
from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed, SealCriterion


@dataclass
class FeedSealContext:
    """Everything the evaluators need for one feed on one day.

    Built by `build_contexts`. Evaluators read from this and never query.
    """

    feed_id: str
    # The evaluation timestamp. Passed in rather than read from the clock so evaluators
    # stay pure and a run can be replayed for any point in time.
    now: datetime
    stable_id: Optional[str] = None

    # Feed-level flags
    official: Optional[bool] = None
    is_producer_url_unstable: Optional[bool] = None
    seasonal: Optional[bool] = None

    # Stable: when the feed was first added to the database.
    feed_created_at: Optional[datetime] = None

    # Each criterion's own bulk-loaded inputs, keyed by criterion name — see
    # `collect_inputs`. Opaque here: this module never looks inside a criterion's payload,
    # and an evaluator reaches only its own through `inputs_for(self.name)`.
    #
    # The whole batch's inputs are shared by reference across every context, rather than
    # sliced per feed and per day. Slicing would force every criterion into one storage
    # shape, and it would copy a year of history once per (feed, day) during a backfill.
    inputs: Mapping[SealCriterionName, Any] = field(default_factory=dict)

    def inputs_for(self, criterion: SealCriterionName) -> Any:
        """This criterion's loaded inputs, or None if its loader returned nothing.

        None is the normal answer for a criterion whose inputs are day-invariant fields on
        this context, so it means "nothing to load", not "the load failed".
        """
        return self.inputs.get(criterion)


# Feeds in these statuses, or not published, are never eligible for the seal.
# `inactive` and `future` feeds are deliberately kept eligible.
INELIGIBLE_STATUSES = ("deprecated", "development")
ELIGIBLE_OPERATIONAL_STATUS = "published"


def is_seal_eligible(feed) -> bool:
    """Whether an already-loaded feed row is eligible for the seal.

    Same predicate as the DB-level filter in `_eligible_stable_ids_query`, applied in
    Python to a row already loaded by id. Used by `update_seals`, which is always given
    explicit ids and needs to tell a feed that does not exist apart from one that exists
    but is no longer eligible, without a second query.
    """
    return (
        feed.status not in INELIGIBLE_STATUSES
        and feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS
    )


def _eligible_stable_ids_query(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[str]] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[str]] = None,
):
    """Base query: `stable_id` of every seal-eligible GTFS feed.

    `stable_feed_ids`, if given, narrows the candidate set without changing the
    predicate. Left as `None`, every eligible feed in the catalog is returned; this is
    what the seal orchestrator (issue #1800) uses to enumerate the full batch to fan out.

    `exclude_backfilled` drops feeds that already have seal state, which is the backfill
    producer's candidate set (#1763): a feed the nightly job already owns has real history
    to carry forward and must not have a march written over it. It lives here rather
    than in the producer so both the count and the stream apply one predicate.

    `required_criteria` makes that "done" test complete rather than merely present: a feed
    is excluded only once it holds a row for **every** criterion the run evaluates. A feed
    holding some of them was left half-done — by a crash between two feeds' commits, or by
    an earlier run filtered to fewer criteria — and marching it again is the point. Left
    `None`, any row excludes the feed, which is the older behaviour and what a caller that
    does not know the run's criteria still gets.
    """
    query = db_session.query(Gtfsfeed.stable_id).filter(
        Feed.status.notin_(INELIGIBLE_STATUSES),
        Feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS,
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(list(stable_feed_ids)))
    if exclude_backfilled:
        criterion_rows = SealCriterion.__table__
        if required_criteria:
            wanted = sorted(set(required_criteria))
            # Correlated count rather than EXISTS: "holds all of them" is not a row-level
            # predicate. Indexed by the (feed_id, criterion) primary key.
            complete = (
                select(func.count(distinct(criterion_rows.c.criterion)))
                .where(
                    criterion_rows.c.feed_id == Feed.id,
                    criterion_rows.c.criterion.in_(wanted),
                )
                .scalar_subquery()
            )
            query = query.filter(complete < len(wanted))
        else:
            has_state = select(criterion_rows.c.feed_id).where(
                criterion_rows.c.feed_id == Feed.id
            )
            query = query.filter(~has_state.exists())
    return query


def count_eligible_feeds(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[str]] = None,
) -> int:
    """Cheap `COUNT(*)` of eligible feeds — no rows loaded."""
    query = _eligible_stable_ids_query(
        db_session,
        stable_feed_ids=stable_feed_ids,
        exclude_backfilled=exclude_backfilled,
        required_criteria=required_criteria,
    )
    if limit is not None:
        query = query.limit(limit)
    return query.count()


def iter_eligible_stable_ids(
    db_session: Session,
    batch_size: int,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[str]] = None,
) -> Iterator[List[str]]:
    """Stream eligible feeds' `stable_id`s in chunks of at most `batch_size`.

    Selects only `stable_id` and uses a server-side cursor (`stream_results=True`) so
    rows are pulled from Postgres as each chunk is consumed, instead of materializing the
    whole eligible-id list up front.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    query = (
        _eligible_stable_ids_query(
            db_session,
            stable_feed_ids=stable_feed_ids,
            exclude_backfilled=exclude_backfilled,
            required_criteria=required_criteria,
        )
        .order_by(Gtfsfeed.stable_id)
        .execution_options(stream_results=True)
    )
    if limit is not None:
        query = query.limit(limit)
    rows = iter(query.yield_per(batch_size))
    while True:
        chunk = [row.stable_id for row in itertools.islice(rows, batch_size)]
        if not chunk:
            return
        yield chunk


def snapshot_date_of(now: datetime) -> date:
    """The UTC day a run evaluating at `now` belongs to.

    The day a run's snapshots are keyed under, and the day its criteria are evaluated
    against. Naive values are read as UTC rather than rejected: the task entry points
    normalize what an operator passes, but `update_seals` is also called directly.
    """
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(timezone.utc).date()


def collect_inputs(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    days: Sequence[date],
    evaluators: Sequence,
) -> Dict[SealCriterionName, Any]:
    """Ask each evaluator to bulk-load its own day-varying inputs for the whole batch.

    Called once per batch whatever the number of days: a criterion loads its full history
    for `days` in one go and answers each day from memory afterwards. That is what holds the
    query count proportional to the number of criteria rather than to feeds x days — the
    difference between a handful of queries and several thousand once a backfill marches a
    year (#1763).

    Args:
        db_session: SQLAlchemy session.
        feeds: The batch of feeds, already loaded and eligibility-checked by the caller.
        days: Every UTC day that will be evaluated, ascending. One entry for a nightly run.
        evaluators: The `CriterionEvaluator` instances this run will apply. Not annotated as
            such because `evaluators.base` imports this module for `FeedSealContext`.

    Returns:
        criterion name -> whatever that criterion's loader returned. Opaque to this module;
        an evaluator reaches its own with `ctx.inputs_for(self.name)`.
    """
    return {
        evaluator.name: evaluator.load_inputs(db_session, feeds, days)
        for evaluator in evaluators
    }


def build_contexts(
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    now: datetime,
    evaluators: Sequence,
) -> Dict[str, FeedSealContext]:
    """Build one context per feed for a single day — the nightly run's case.

    This is `collect_inputs` over a one-day range, plus the day-invariant feed fields. A
    backfill marching a year calls `collect_inputs` once for the whole range and then builds
    its contexts per day from that same result, so both paths load a criterion's inputs
    through the criterion itself and there is only ever one place they come from.

    Args:
        db_session: SQLAlchemy session, passed on to the evaluators' loaders.
        feeds: The batch of feeds to build for, already loaded (and eligibility-checked via
            `is_seal_eligible`) by the caller — `update_seals`.
        now: The evaluation timestamp.
        evaluators: The evaluators this run will apply. Required rather than defaulted: an
            omitted list would leave every criterion with no inputs and quietly turn its
            verdicts into UNKNOWN.

    Returns:
        feed_id -> FeedSealContext.

    Adding a criterion's data. Two kinds:

    1. Already on the selected feed row (`official`, `created_at`, `seasonal`,
       `is_producer_url_unstable`). Add the field to `FeedSealContext` and read it off `feed`
       below. No query, no cost, and it answers for any day.

    2. Varies by day. Nothing changes here: override `load_inputs` on the criterion's own
       evaluator and read it back in `_evaluate` with `ctx.inputs_for(self.name)`.
    """
    inputs = collect_inputs(db_session, feeds, [snapshot_date_of(now)], evaluators)
    return {
        feed.id: FeedSealContext(
            feed_id=feed.id,
            now=now,
            stable_id=feed.stable_id,
            official=feed.official,
            is_producer_url_unstable=feed.is_producer_url_unstable,
            seasonal=feed.seasonal,
            feed_created_at=feed.created_at,
            inputs=inputs,
        )
        for feed in feeds
    }


def batched(items: Sequence, size: int):
    """Yield successive slices of `items` of at most `size` elements."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
