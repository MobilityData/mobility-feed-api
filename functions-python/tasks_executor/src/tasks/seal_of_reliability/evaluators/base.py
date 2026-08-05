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
from tasks.seal_of_reliability.criteria import RELIABILITY_WINDOW, SealCriterionName


@dataclass(frozen=True)
class RawEvaluation:
    """One criterion's verdict for one feed, with no grace applied.

    `failing` is tri-state: True and False are verdicts, None means the criterion could not
    be evaluated this run (a missing availability check, a criterion that does not apply to
    this feed) and the stored state must be left alone.
    """

    criterion: SealCriterionName
    failing: Optional[bool]
    reason: str


class CriterionEvaluator:
    """Evaluates one criterion against a pre-loaded feed context.

    Subclasses set `name` and, where they differ from the defaults, `grace_period` and
    `reliability_window`, then implement `_evaluate`. They never touch the database: all
    the data they need is on the context, loaded in bulk by `context.build_contexts`.
    """

    name: SealCriterionName = None
    grace_period: Optional[timedelta] = None
    reliability_window: Optional[timedelta] = RELIABILITY_WINDOW

    def evaluate(self, ctx: FeedSealContext) -> RawEvaluation:
        """Evaluate the criterion and label the result with this evaluator's name.

        Labelling happens here rather than in the subclasses so an evaluator cannot
        disagree with its own `name`.
        """
        failing, reason = self._evaluate(ctx)
        return RawEvaluation(criterion=self.name, failing=failing, reason=reason)

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[Optional[bool], str]:
        """Return (failing, reason) for this feed. Implemented by subclasses."""
        raise NotImplementedError("Subclasses should implement this method.")
