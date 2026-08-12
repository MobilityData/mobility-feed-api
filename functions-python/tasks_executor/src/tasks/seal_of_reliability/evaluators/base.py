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
from tasks.seal_of_reliability.criteria import PROBATION_PERIOD, SealCriterionName


@dataclass(frozen=True)
class CriterionObservation:
    """One criterion's own check for one feed, with no debouncing.

    `observed_pass` is tri-state: True and False are verdicts, None means the criterion
    could not be evaluated this run (a missing availability check, a criterion that does not
    apply to this feed) and the stored state must be left alone.

    Stated positively, so an evaluator returns the same sense as the check it reads
    (`success = TRUE`, `total_error = 0`) with no inversion in between.
    """

    criterion: SealCriterionName
    observed_pass: Optional[bool]
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
        observed_pass, reason = self._evaluate(ctx)
        return CriterionObservation(
            criterion=self.name, observed_pass=observed_pass, reason=reason
        )

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[Optional[bool], str]:
        """Return (observed_pass, reason) for this feed. Implemented by subclasses."""
        raise NotImplementedError("Subclasses should implement this method.")
