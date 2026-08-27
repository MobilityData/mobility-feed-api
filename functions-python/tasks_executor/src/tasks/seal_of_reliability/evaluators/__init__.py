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

`EVALUATORS` is the registry the job iterates. All criteria are implemented except Fresh / continuous
coverage, which is tracked by #1782. Adding one means a new subclass,
an entry here, and whatever fields it needs on `FeedSealContext`. Its windows are not declared
on the subclass: they come from the policy maps in `shared.common.seal_criteria`, which the
read API reads too.

`seal_criterion_name` in the database already declares all six values, so a criterion can
be added without a schema change.
"""

from typing import Final, List

from tasks.seal_of_reliability.evaluators.base import (
    CriterionEvaluator,
    CriterionObservation,
)
from tasks.seal_of_reliability.evaluators.available import AvailableEvaluator
from tasks.seal_of_reliability.evaluators.compliant import CompliantEvaluator
from tasks.seal_of_reliability.evaluators.fresh_coverage import FreshCoverageEvaluator
from tasks.seal_of_reliability.evaluators.official import OfficialEvaluator
from tasks.seal_of_reliability.evaluators.stable import StableEvaluator

EVALUATORS: Final[List[CriterionEvaluator]] = [
    OfficialEvaluator(),
    StableEvaluator(),
    AvailableEvaluator(),
    CompliantEvaluator(),
    FreshCoverageEvaluator(),
]

__all__ = [
    "EVALUATORS",
    "AvailableEvaluator",
    "CompliantEvaluator",
    "CriterionEvaluator",
    "CriterionObservation",
    "FreshCoverageEvaluator",
    "OfficialEvaluator",
    "StableEvaluator",
]
