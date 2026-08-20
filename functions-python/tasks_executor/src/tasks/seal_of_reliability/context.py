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

Only Official is implemented, so the context currently carries just the feed row. Each new
criterion adds the fields it needs here plus one bulk query to populate them: the latest
dataset for Compliant and Fresh, the day's availability rows for Available, the full
dataset coverage history for Fresh continuous coverage.
"""

import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterator, List, Optional, Sequence

from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Feed, Gtfsfeed


@dataclass
class FeedSealContext:
    """Everything the evaluators need for one feed.

    Built by `build_contexts`. Evaluators read from this and never query.
    """

    feed_id: str
    # The evaluation timestamp. Passed in rather than read from the clock so evaluators
    # stay pure and a run can be replayed for any point in time.
    now: datetime
    stable_id: Optional[str] = None

    # Feed-level flags
    official: Optional[bool] = None


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
    db_session: Session, stable_feed_ids: Optional[Sequence[str]] = None
):
    """Base query: `stable_id` of every seal-eligible GTFS feed.

    `stable_feed_ids`, if given, narrows the candidate set without changing the
    predicate. Left as `None`, every eligible feed in the catalog is returned; this is
    what the seal orchestrator (issue #1800) uses to enumerate the full batch to fan out.
    """
    query = db_session.query(Gtfsfeed.stable_id).filter(
        Feed.status.notin_(INELIGIBLE_STATUSES),
        Feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS,
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(list(stable_feed_ids)))
    return query


def count_eligible_feeds(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> int:
    """Cheap `COUNT(*)` of eligible feeds — no rows loaded."""
    query = _eligible_stable_ids_query(db_session, stable_feed_ids=stable_feed_ids)
    if limit is not None:
        query = query.limit(limit)
    return query.count()


def iter_eligible_stable_ids(
    db_session: Session,
    batch_size: int,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> Iterator[List[str]]:
    """Stream eligible feeds' `stable_id`s in chunks of at most `batch_size`.

    Selects only `stable_id` and uses a server-side cursor (`stream_results=True`) so
    rows are pulled from Postgres as each chunk is consumed, instead of materializing the
    whole eligible-id list up front.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    query = (
        _eligible_stable_ids_query(db_session, stable_feed_ids=stable_feed_ids)
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


def build_contexts(
    db_session: Session, feeds: Sequence[Gtfsfeed], now: datetime
) -> Dict[str, FeedSealContext]:
    """Load everything the evaluators need for `feeds`, in a fixed number of queries.

    Args:
        db_session: SQLAlchemy session. Unused while Official is the only criterion, since
            everything it needs is already on the feed row, but kept in the signature
            because every further criterion needs it.
        feeds: The batch of feeds to load, already loaded (and eligibility-checked via
            `is_seal_eligible`) by the caller — `update_seals`.
        now: The evaluation timestamp.

    Returns:
        feed_id -> FeedSealContext.

    How to add a criterion's data. Two kinds:

    1. Already on the selected feed row (`official`, `created_at`, `seasonal`,
       `is_producer_url_unstable`). Add the field to FeedSealContext and read it off `feed`
       below. No query, no cost.

    2. Needs its own query. Add the field, then a module-level `_load_*` helper that takes
       the whole batch and returns a dict keyed by feed_id, and call it once here. Keeping
       the query per batch rather than per feed is what holds the query count proportional
       to the number of criteria instead of the number of feeds. For example, Available
       (issue #1784) would add:

           def _load_availability_today(db_session, feed_ids, day_start) -> Dict[str, bool]:
               '''feed_id -> whether any availability check succeeded since day_start.
               Feeds absent from the result had no check at all, which the criterion reads
               as "not evaluable" rather than "failing".'''

       called once as `availability = _load_availability_today(...)` and consumed per feed
       as `availability_success_today=availability.get(feed.id, False)`.
    """
    return {
        feed.id: FeedSealContext(
            feed_id=feed.id,
            now=now,
            stable_id=feed.stable_id,
            official=feed.official,
        )
        for feed in feeds
    }


def batched(items: Sequence, size: int):
    """Yield successive slices of `items` of at most `size` elements."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
