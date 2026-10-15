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
"""Official criterion: the feed is flagged official."""

from typing import Tuple

from shared.common.seal_criteria import CriterionStatus, SealCriterionName
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class OfficialEvaluator(CriterionEvaluator):
    """`feed.official IS TRUE`.

    A point-in-time state check: official at the time of reviewing the dataset, with no
    6-month check. The policy maps give it neither a grace period nor a probation period, so
    the criterion fails the same day the flag is lost and clears the same day it comes back,
    taking the seal with it in both directions.
    """

    name = SealCriterionName.OFFICIAL

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        # `is True` rather than a truthiness test: NULL is not an endorsement. It is a FAIL
        # rather than an UNKNOWN because the column is always readable — absence of the flag
        # is the answer, not a missing input.
        status = CriterionStatus.PASS if ctx.official is True else CriterionStatus.FAIL
        return status, f"feed.official is {ctx.official!r}"
