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
"""Fresh (future coverage) criterion: the latest dataset still covers the near future."""

from typing import Tuple

from shared.common.seal_criteria import (
    FUTURE_COVERAGE_HORIZON,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class FreshCoverageEvaluator(CriterionEvaluator):
    """`latest dataset.service_date_range_end >= now + 7 days`.

    This is the only implemented criterion that can return NOT_APPLICABLE. A seasonal feed
    is expected to have coverage that runs out between seasons, so the question "does this
    feed cover the next week" has no meaningful answer for it.
    """

    name = SealCriterionName.FRESH_COVERAGE

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        # Applicability is a property of the feed, so it is settled before the inputs are
        # looked at: a seasonal feed's missing dataset is not an UNKNOWN worth reporting.
        if ctx.seasonal is True:
            return (
                CriterionStatus.NOT_APPLICABLE,
                "the feed is seasonal, so future coverage is not required",
            )

        # Two different missing inputs, kept apart so the report says which: no dataset at
        # all as of this run, or one whose coverage was never extracted.
        if ctx.latest_dataset is None:
            return CriterionStatus.UNKNOWN, "the feed has no latest dataset"

        coverage_end = ctx.latest_dataset.service_date_range_end
        if coverage_end is None:
            return (
                CriterionStatus.UNKNOWN,
                "the latest dataset has no service_date_range_end",
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
