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
from datetime import date, timedelta
from typing import Any, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from shared.common.seal_criteria import (
    CriterionStatus,
    SealCriterionName,
    grace_period_for,
    probation_period_for,
)
from tasks.seal_of_reliability.context import FeedSealContext


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

    A subclass sets `name` and implements `_evaluate`. It does not declare its own windows:
    both are resolved from `name` against the policy maps in `shared.common.seal_criteria`,
    which the read API reads too, so a criterion cannot debounce one way for the job and
    another way for the API. To change a window, change the map.

    Evaluators never touch the database at evaluation time: everything they need is already
    on the context, either as a day-invariant feed field or as the inputs their own
    `load_history` bulk-loaded.

    A criterion that has to look backwards owns that lookup itself, rather than the context
    builder growing a field and a query per criterion. `load_history` is where it goes.
    """

    name: SealCriterionName = None

    @property
    def grace_period(self) -> Optional[timedelta]:
        """How long an observed failure may run before it is confirmed, per the policy map.

        None means the criterion has no grace period and its status flips on the first
        failing day.
        """
        return grace_period_for(self.name)

    @property
    def probation_period(self) -> Optional[timedelta]:
        """How long this criterion serves after recovering, per the policy map.

        None means it never serves probation.
        """
        return probation_period_for(self.name)

    def load_history(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Any:
        """Bulk-load this criterion's day-varying inputs for a whole batch of feeds, at once.

        Returns an object of the criterion's own choosing — nothing outside the criterion
        looks inside it. The caller stashes it on every context in the batch, and `_evaluate`
        reads it back with `ctx.history_for(self.name)`, indexing by `ctx.feed_id` and the
        day of `ctx.now`.

        The default returns None, which is the right answer for a criterion whose inputs are
        day-invariant fields already on the context — Official and Stable read the feed row
        and have nothing of their own to load.

        Override it for any criterion that does, and load the whole of `days` in one query
        rather than one query per day: a nightly run passes a single day, but a backfill
        (#1763) passes a year, and a per-day query there turns a handful of queries into
        several thousand.

        Args:
            db_session: SQLAlchemy session.
            feeds: The batch of feeds to load for, already loaded by the caller.
            days: Every UTC day that will be evaluated, ascending.
        """
        return None

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
