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
"""The seal criterion evaluators.

`EVALUATORS` is the registry the job iterates. Only Official is implemented so far
(issue #1783); the remaining criteria are tracked by #1784 and #1782. Adding one means a
new subclass, an entry here, and whatever fields it needs on `FeedSealContext`.

`seal_criterion_name` in the database already declares all six values, so a criterion can
be added without a schema change.
"""

from typing import Final, List

from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator, RawEvaluation
from tasks.seal_of_reliability.evaluators.official import OfficialEvaluator

EVALUATORS: Final[List[CriterionEvaluator]] = [
    OfficialEvaluator(),
]

__all__ = [
    "EVALUATORS",
    "CriterionEvaluator",
    "OfficialEvaluator",
    "RawEvaluation",
]
