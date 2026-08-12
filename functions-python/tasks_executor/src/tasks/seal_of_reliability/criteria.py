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
"""Seal of Reliability policy values.

Everything here is the published definition of the seal, so it lives in code rather than
in DB config: changing any of these values changes which feeds qualify, and that should
go through code review, tests and a deploy.

Each criterion's grace period belongs with the criterion, as a class attribute on its
evaluator. Only Official is implemented so far and it has none.
"""

from datetime import timedelta
from enum import Enum
from typing import Final


class SealCriterionName(str, Enum):
    """The six seal criteria. Values match the seal_criterion_name DB enum.

    All six are listed even though only Official has an evaluator (see #1784 and #1782),
    so that the enum stays a faithful mirror of the database type.
    """

    OFFICIAL = "official"
    STABLE = "stable"
    AVAILABLE = "available"
    COMPLIANT = "compliant"
    FRESH_COVERAGE = "fresh_coverage"
    FRESH_CONTINUOUS = "fresh_continuous"


# A criterion that recovers from a confirmed failure is put on probation: it must then go
# this long with no observed failure before it can contribute to the seal again. It is the
# default for new evaluators; Official is exempt because it is a point-in-time state check
# (see OfficialEvaluator).
#
# Probation is opened only by a recovery. A first evaluation that passes is not a recovery,
# so a feed that has never had a confirmed failure never serves probation at all and can
# hold the seal from its very first evaluation.
PROBATION_PERIOD: Final[timedelta] = timedelta(days=180)
