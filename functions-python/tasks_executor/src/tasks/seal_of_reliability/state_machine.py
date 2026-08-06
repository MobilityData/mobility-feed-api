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
"""Generic per-criterion state machine for the Seal of Reliability.

Steps 2 and 3 of the nightly job: failure tracking and `grace_failing`. This is the only
place that knows about grace periods and the reliability window, and it is
criterion-agnostic — the caller passes the values from the evaluator. `now` is a parameter
rather than a call to `datetime.now()` so runs are replayable and idempotent.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Optional

from tasks.seal_of_reliability.criteria import SealCriterionName
from tasks.seal_of_reliability.evaluators.base import RawEvaluation


@dataclass(frozen=True)
class SealCriterionState:
    """One row of the sealcriterion table.

    raw_* fields describe the instantaneous state at the last evaluation, with no grace
    applied. grace_failing is the debounced state that drives the seal outcome.
    """

    feed_id: str
    criterion: SealCriterionName
    raw_failing: Optional[bool] = None
    grace_failing: Optional[bool] = None
    evaluated_at: Optional[datetime] = None
    first_raw_failure_at: Optional[datetime] = None
    last_raw_failure_at: Optional[datetime] = None
    last_grace_failure_at: Optional[datetime] = None


def transition(
    prev: Optional[SealCriterionState],
    raw: RawEvaluation,
    grace_period: Optional[timedelta],
    reliability_window: Optional[timedelta],
    now: datetime,
    feed_id: Optional[str] = None,
) -> Optional[SealCriterionState]:
    """Apply one evaluation to a criterion's stored state.

    Returns the new state, or `prev` unchanged when the criterion was not evaluable
    (`raw.failing is None`) — a missing input must never be read as a failure, otherwise an
    upstream outage would revoke seals across the catalogue.

    Args:
        prev: The stored state, or None if this criterion has never been evaluated.
        raw: The evaluator's verdict for this run.
        grace_period: How long a failure streak may last before it is confirmed.
            None means a failure is confirmed immediately.
        reliability_window: How long a confirmed failure keeps the criterion failing.
            None means the criterion reflects the current state only, with no memory.
        now: The evaluation timestamp.
        feed_id: Required when `prev` is None, to build the first state.
    """
    if raw.failing is None:
        return prev

    resolved_feed_id = prev.feed_id if prev is not None else feed_id
    if resolved_feed_id is None:
        raise ValueError("feed_id is required when there is no previous state")

    base = prev or SealCriterionState(feed_id=resolved_feed_id, criterion=raw.criterion)

    if raw.failing:
        # first_raw_failure_at marks the start of the current streak. It is cleared on
        # recovery, so it is only None here at the start of a new streak.
        first_raw_failure_at = base.first_raw_failure_at or now
        last_raw_failure_at = now
        last_grace_failure_at = base.last_grace_failure_at
        if grace_period is None or now - first_raw_failure_at >= grace_period:
            last_grace_failure_at = now
    else:
        # The streak ended, so the grace period resets. last_raw_failure_at and
        # last_grace_failure_at are history and are never cleared.
        first_raw_failure_at = None
        last_raw_failure_at = base.last_raw_failure_at
        last_grace_failure_at = base.last_grace_failure_at

    if reliability_window is None:
        # No memory: the criterion tracks the current state and clears on recovery.
        grace_failing = raw.failing
    else:
        grace_failing = (
            last_grace_failure_at is not None
            and last_grace_failure_at >= now - reliability_window
        )

    return replace(
        base,
        raw_failing=raw.failing,
        grace_failing=grace_failing,
        evaluated_at=now,
        first_raw_failure_at=first_raw_failure_at,
        last_raw_failure_at=last_raw_failure_at,
        last_grace_failure_at=last_grace_failure_at,
    )
