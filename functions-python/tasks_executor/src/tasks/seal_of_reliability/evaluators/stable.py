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

    Note the check conflates two things: an observed failure means either "the producer URL
    is flagged unstable" or "the feed is younger than 180 days", and the stored state cannot
    say which. That is a deliberate.
    """

    name = SealCriterionName.STABLE

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        if ctx.is_producer_url_unstable:
            return CriterionStatus.FAIL, "feed.is_producer_url_unstable is True"

        if ctx.feed_created_at is None:
            # feed.created_at is NOT NULL, so this is unreachable from the database and means
            # a context was built without it. Still a verdict rather than an UNKNOWN.
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
