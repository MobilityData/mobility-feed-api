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
"""Available criterion: the feed's producer URL answered today."""

from typing import Tuple

from shared.common.seal_criteria import (
    AVAILABILITY_LOOKBACK,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class AvailableEvaluator(CriterionEvaluator):
    """The latest `gtfs_feed_availability_check` since the previous run has `success = TRUE`.

    The window runs from the last time this criterion was evaluated for the feed up to
    `now`. A window with no check at all is UNKNOWN, not a failure: it means we
    did not look, not that the feed was down.
    """

    name = SealCriterionName.AVAILABLE

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        check = ctx.availability_check
        if check is None:
            since = (ctx.now - AVAILABILITY_LOOKBACK).isoformat()
            return CriterionStatus.UNKNOWN, f"no availability check since {since}"

        status = CriterionStatus.PASS if check.success else CriterionStatus.FAIL
        outcome = "succeeded" if check.success else "failed"
        return status, f"the check at {check.checked_at.isoformat()} {outcome}"
