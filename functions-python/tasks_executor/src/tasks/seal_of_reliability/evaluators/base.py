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
"""Base class for the per-criterion evaluators."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Tuple

from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.criteria import (
    PROBATION_PERIOD,
    CriterionStatus,
    SealCriterionName,
)


@dataclass(frozen=True)
class CriterionObservation:
    """One criterion's own check for one feed, with no debouncing.

    `observed_status` is one of four values. PASS and FAIL are verdicts. UNKNOWN means the
    inputs the check needs were not there this run, and NOT_APPLICABLE means the criterion is
    deliberately excluded for this feed — the two are handled differently by `transition`, so
    an evaluator must not use one for the other. NEVER_EVALUATED is a stored state only and is
    never an evaluator's answer.

    Stated positively, so an evaluator returns the same sense as the check it reads
    (`success = TRUE`, `total_error = 0`) with no inversion in between.
    """

    criterion: SealCriterionName
    observed_status: CriterionStatus
    reason: str


class CriterionEvaluator:
    """Evaluates one criterion against a pre-loaded feed context.

    Subclasses set `name` and, where they differ from the defaults, `grace_period` and
    `probation_period`, then implement `_evaluate`. They never touch the database: all the
    data they need is on the context, loaded in bulk by `context.build_contexts`.

    `grace_period` holds a passing status while an observed failure is still young.
    `probation_period` is how long the criterion must go with no observed failure after
    recovering from a confirmed failure. None on either means the criterion does not use it.
    """

    name: SealCriterionName = None
    grace_period: Optional[timedelta] = None
    probation_period: Optional[timedelta] = PROBATION_PERIOD

    def evaluate(self, ctx: FeedSealContext) -> CriterionObservation:
        """Evaluate the criterion and label the result with this evaluator's name.

        Labelling happens here rather than in the subclasses so an evaluator cannot
        disagree with its own `name`.
        """
        observed_status, reason = self._evaluate(ctx)
        if observed_status is CriterionStatus.NEVER_EVALUATED:
            # NEVER_EVALUATED is a stored DB value, not a verdict an evaluator may return.
            raise ValueError(
                f"{type(self).__name__} returned NEVER_EVALUATED; use UNKNOWN when the "
                "inputs are missing or NOT_APPLICABLE when the criterion does not apply"
            )
        return CriterionObservation(
            criterion=self.name, observed_status=observed_status, reason=reason
        )

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        """Return (observed_status, reason) for this feed. Implemented by subclasses.

        Returns PASS or FAIL for a verdict, UNKNOWN when the inputs needed are missing, or
        NOT_APPLICABLE when the criterion is deliberately excluded for this feed.
        """
        raise NotImplementedError("Subclasses should implement this method.")
