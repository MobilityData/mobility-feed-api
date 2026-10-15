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
"""Fresh (future coverage) criterion: the closest dataset still covers the near future."""

from datetime import date
from typing import Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from shared.common.seal_criteria import (
    FUTURE_COVERAGE_HORIZON,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.history import (
    DatasetHistory,
    load_dataset_history,
)
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class FreshCoverageEvaluator(CriterionEvaluator):
    """`closest_dataset.service_date_range_end >= now + 7 days`.

    This is the only implemented criterion that can return NOT_APPLICABLE. A seasonal feed
    is expected to have coverage that runs out between seasons, so the question "does this
    feed cover the next week" has no meaningful answer for it.

    Its inputs also vary by day, so it loads them itself in `load_history` instead of reading
    a field on `FeedSealContext`. `ctx.closest_dataset` holds one answer, for one `now`, and a
    march needs one per day - see the `context` module docstring on the three kinds of input.
    """

    name = SealCriterionName.FRESH_COVERAGE

    def load_history(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Optional[DatasetHistory]:
        """The datasets the batch's feeds had over `days`. See `load_dataset_history`."""
        return load_dataset_history(db_session, feeds, days)

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        # Applicability is a property of the feed, so it is settled before the inputs are
        # looked at: a seasonal feed's missing dataset is not an UNKNOWN worth reporting.
        if ctx.seasonal is True:
            return (
                CriterionStatus.NOT_APPLICABLE,
                "the feed is seasonal, so future coverage is not required",
            )

        if ctx.history is None or not ctx.history.has_history_for(self.name):
            # Not a data condition: the context was built without running this criterion's
            # loader. Said out loud in the reason rather than passed off as a missing dataset,
            # because the two look identical in the stored row and only this one is a bug.
            return (
                CriterionStatus.UNKNOWN,
                "fresh_coverage history was never loaded for this run - the context was "
                "built without calling load_history",
            )

        # Two different missing inputs, kept apart so the report says which: no dataset at
        # all as of this run, or one whose coverage was never extracted.
        closest = ctx.history.get_closest_dataset_at(ctx.feed_id, ctx.now)
        if closest is None:
            return CriterionStatus.UNKNOWN, "the feed has no dataset"

        coverage_end = closest.service_date_range_end
        if coverage_end is None:
            return (
                CriterionStatus.UNKNOWN,
                "the closest dataset has no service_date_range_end",
            )

        horizon = ctx.now + FUTURE_COVERAGE_HORIZON
        if coverage_end < horizon:
            return (
                CriterionStatus.FAIL,
                f"coverage ends {coverage_end.isoformat()}, before the "
                f"{FUTURE_COVERAGE_HORIZON.days}-day horizon {horizon.isoformat()}",
            )
        return (
            CriterionStatus.PASS,
            f"coverage ends {coverage_end.isoformat()}, at or beyond the "
            f"{FUTURE_COVERAGE_HORIZON.days}-day horizon {horizon.isoformat()}",
        )
