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
"""Feed eligibility query and bulk loading of everything the evaluators need.

The evaluators are pure functions over a `FeedSealContext`, so every DB read for a batch of
feeds happens here, in a fixed number of queries regardless of batch size.

Only Official is implemented, so the context currently carries just the feed row. Each new
criterion adds the fields it needs here plus one bulk query to populate them: the latest
dataset for Compliant and Fresh, the day's availability rows for Available, the full
dataset coverage history for Fresh continuous coverage.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Sequence

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


def get_seal_feeds_query(
    db_session: Session, stable_feed_ids: Optional[Sequence[str]] = None
):
    """Return a query for the feeds the seal applies to.

    Eligibility is defined here and nowhere else, so a full run and a one-feed run exercise
    the same predicate. `inactive` and `future` feeds are deliberately included: skipping a
    feed does not make it neutral, it freezes its stored rows, and once Fresh (future
    coverage) exists an inactive feed should fail it rather than keep displaying a seal.
    """
    query = db_session.query(Gtfsfeed).filter(
        Feed.data_type == "gtfs",
        Feed.status.notin_(["deprecated", "development"]),
        Feed.operational_status == "published",
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(list(stable_feed_ids)))
    return query


def build_contexts(
    db_session: Session, feeds: Sequence[Gtfsfeed], now: datetime
) -> Dict[str, FeedSealContext]:
    """Load everything the evaluators need for `feeds`, in a fixed number of queries.

    Args:
        db_session: SQLAlchemy session. Unused while Official is the only criterion, since
            everything it needs is already on the feed row, but kept in the signature
            because every further criterion needs it.
        feeds: The batch of feeds to load, from `get_seal_feeds_query`.
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
