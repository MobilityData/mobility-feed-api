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

from typing import Optional, Tuple

from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.criteria import SealCriterionName
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class OfficialEvaluator(CriterionEvaluator):
    """`feed.official IS TRUE`.

    A point-in-time state check: official at the time of reviewing the dataset, with no
    6-month check. Both the grace period and the probation period are None, so the criterion
    fails the same day the flag is lost and clears the same day it comes back, taking the
    seal with it in both directions.
    """

    name = SealCriterionName.OFFICIAL
    grace_period = None
    probation_period = None

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[Optional[bool], str]:
        # `is True` rather than a truthiness test: NULL is not an endorsement, and it is a
        # verdict of "not official" rather than "not evaluable".
        return ctx.official is True, f"feed.official is {ctx.official!r}"
