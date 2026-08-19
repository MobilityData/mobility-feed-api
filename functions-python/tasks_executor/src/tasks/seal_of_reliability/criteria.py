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
"""Seal of Reliability policy values and domain enums.

The policy values here are the published definition of the seal, so they live in code
rather than in DB config: changing any of them changes which feeds qualify, and that should
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


class CriterionStatus(str, Enum):
    """A criterion's status. Values match the seal_criterion_status DB enum.

    Only PASS and FAIL are verdicts. The other three say why there is no verdict, and they
    are not interchangeable — the roll-up in `seal_updater` sends them in three different
    directions:

    * UNKNOWN — we could not look; the inputs the check needs were not there. A property of
      the run, not of the feed. The criterion keeps its last confirmed verdict and stays in
      the roll-up, so an upstream outage freezes a criterion rather than waiving it.
    * NOT_APPLICABLE — there is no question to ask; the criterion is deliberately excluded
      for this feed (Fresh / future coverage on a seasonal feed). A property of the feed.
      The criterion leaves the roll-up entirely.
    * NEVER_EVALUATED — never had a verdict, since the feed first appeared. The initial value,
      and the only one the job never writes back once a criterion has left it.

    UNKNOWN is never written to `confirmed_status`: a run that could not look does not
    change the answer, it leaves the previous one standing.
    """

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NEVER_EVALUATED = "never_evaluated"
    NOT_APPLICABLE = "not_applicable"

    @property
    def is_verdict(self) -> bool:
        """True for PASS and FAIL — the two values that mean the check actually answered."""
        return self in (CriterionStatus.PASS, CriterionStatus.FAIL)


class CriterionPhase(str, Enum):
    """Which of the two debouncing mechanisms is currently acting on a criterion.

    Derived from the stored row rather than stored itself (see `state_machine.phase`): it is
    a pure function of `probation_start`, `confirmed_status` and `first_observed_failure_at`,
    all of which are already on the row, so a stored copy would be a second thing to keep in
    step for no gain.

    The three values are mutually exclusive: probation suspends the grace period, so a
    criterion can never be serving a penalty and holding a failure under grace at once.
    """

    STEADY = "steady"
    IN_GRACE_PERIOD = "in_grace_period"
    ON_PROBATION = "on_probation"


# A criterion that recovers from a confirmed failure is put on probation: it must then go
# this long with no observed failure before it can contribute to the seal again. It is the
# default for new evaluators; Official is exempt because it is a point-in-time state check
# (see OfficialEvaluator).
#
# Probation is opened only by a recovery. A first evaluation that passes is not a recovery,
# so a feed that has never had a confirmed failure never serves probation at all and can
# hold the seal from its very first evaluation.
PROBATION_PERIOD: Final[timedelta] = timedelta(days=180)
