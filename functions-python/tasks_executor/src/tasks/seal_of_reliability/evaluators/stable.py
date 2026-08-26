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
"""Stable criterion: the feed is old enough in the database, from a stable producer URL."""

from typing import Tuple

from shared.common.seal_criteria import (
    TRACKING_PERIOD,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class StableEvaluator(CriterionEvaluator):
    """`feed.created_at <= now - 180 days` and the producer URL is not flagged unstable.

    The clock is the feed's own `created_at`, when it was added to the Mobility Database, so
    the criterion asks whether we hold at least six months of history for this feed. Reading
    the feed row rather than anything the seal job writes has two consequences worth naming:
    a feed that has been in the catalog for years qualifies on the very first seal run, and a
    replay at a historical `now` evaluates Stable as correctly as any other criterion,
    because the input does not move when the job runs.

    A producer URL change creates a new feed in our data model, with its own `created_at`, so
    the six months restart with it. That is the point: the new URL has no history yet.

    TRACKING_PERIOD is inside the check rather than in the state machine, so the criterion is
    a point-in-time state check like Official: the policy maps give it no grace period and no
    probation. There is nothing for a grace period to absorb, since neither input flickers -
    one changes when a reviewer changes it, the other only ever crosses its threshold once -
    and probation on a criterion that moves from fail to pass a single time would never be
    served.

    Note the check conflates two things: an observed failure means either "the producer URL
    is flagged unstable" or "the feed is younger than 180 days", and the stored state cannot
    say which. That is a deliberate, accepted loss of detail (see #1761); the `reason` on the
    observation says which, for the run that produced it.
    """

    name = SealCriterionName.STABLE

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        # Never UNKNOWN: both inputs are columns on the feed row and always readable.
        #
        # `is True` rather than a truthiness test, to match the SQL predicate
        # `is_producer_url_unstable IS NOT TRUE`: NULL is not a claim of instability.
        if ctx.is_producer_url_unstable is True:
            return CriterionStatus.FAIL, "feed.is_producer_url_unstable is True"

        if ctx.feed_created_at is None:
            # feed.created_at is NOT NULL, so this is unreachable from the database and means
            # a context was built without it. Still a verdict rather than an UNKNOWN: an
            # UNKNOWN would freeze the criterion at whatever it last said, and reporting a
            # feed as not yet stable beats holding a seal on a value nobody supplied.
            return CriterionStatus.FAIL, "feed.created_at is missing"

        age = ctx.now - ctx.feed_created_at
        if age < TRACKING_PERIOD:
            return (
                CriterionStatus.FAIL,
                f"in the database for {age.days} day(s), needs {TRACKING_PERIOD.days}",
            )
        return (
            CriterionStatus.PASS,
            f"in the database for {age.days} day(s) with a stable producer URL",
        )
