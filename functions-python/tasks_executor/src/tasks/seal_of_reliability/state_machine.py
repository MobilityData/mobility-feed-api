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

Steps 2 to 4 of the nightly job: observed failure tracking, the confirmed status, and
probation. This is the only place that knows about grace periods and probation, and it is
criterion-agnostic — the caller passes both from the evaluator. `now` is a parameter rather
than a call to `datetime.now()` so runs are replayable and idempotent.

Two pieces of state are tracked per feed per criterion and they are independent:

* `confirmed_pass` — does the criterion pass right now, debounced by its grace period.
* `probation_start` — the stretch it must serve after recovering from a confirmed failure.

The seal (step 5, in seal_updater) requires every criterion in service to be a confirmed
pass and not on probation.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

from tasks.seal_of_reliability.criteria import SealCriterionName
from tasks.seal_of_reliability.evaluators.base import CriterionObservation


@dataclass(frozen=True)
class SealCriterionState:
    """One row of the sealcriterion table.

    Both booleans are stored positively: TRUE means the criterion passed. `observed_pass`
    is the instantaneous check, `confirmed_pass` the debounced status that drives the seal.
    NULL on either means the criterion has never produced a verdict for this feed, and the
    job never writes NULL back — see `transition`.

    The failure timestamps stay negative on purpose: they record events that really are
    failures. Booleans describe state, timestamps record events.
    """

    feed_id: str
    criterion: SealCriterionName
    observed_pass: Optional[bool] = None
    confirmed_pass: Optional[bool] = None
    evaluated_at: Optional[datetime] = None
    first_observed_failure_at: Optional[datetime] = None
    last_observed_failure_at: Optional[datetime] = None
    last_confirmed_failure_at: Optional[datetime] = None
    probation_start: Optional[datetime] = None


def _next_day_start(moment: datetime) -> datetime:
    """The start of the day after `moment`, in UTC.

    Probation is stamped at day granularity for two reasons: two runs on the same day
    produce the same start, and stamping *tomorrow* on every failing day leaves the start on
    the day the criterion was repaired once the streak ends.
    """
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _probation_start(
    base: SealCriterionState,
    observed_pass: bool,
    confirmed_pass: bool,
    probation_period: Optional[timedelta],
    now: datetime,
) -> Optional[datetime]:
    """Step 4: probation is only ever opened by a recovery.

    Two rules put a criterion on probation, and both are recoveries:

    * recovery from a confirmed failure, in all circumstances;
    * recovery from an observed failure while already on probation.

    A first evaluation that passes is not a recovery, so it opens nothing. An observed
    failure absorbed by the grace period costs a criterion that is not on probation nothing,
    while the same failure during probation restarts the whole count.
    """
    if probation_period is None:
        return None

    if not observed_pass:
        if base.probation_start is not None or not confirmed_pass:
            return _next_day_start(now)
        # Not on probation and this failure is still inside its grace period: the track
        # record survives the blip.
        return base.probation_start

    # The check passed today. If the criterion was serving probation and the whole stretch
    # has now gone by since it started, it has served it: clear it. Otherwise leave the start
    # exactly where it is — a passing day never moves it, it only brings the end closer.
    if (
        base.probation_start is not None
        and now >= base.probation_start + probation_period
    ):
        return None
    return base.probation_start


def transition(
    prev: Optional[SealCriterionState],
    observation: CriterionObservation,
    grace_period: Optional[timedelta],
    probation_period: Optional[timedelta],
    now: datetime,
    feed_id: Optional[str] = None,
) -> Optional[SealCriterionState]:
    """Apply one observation to a criterion's stored state.

    Returns the new state, or `prev` unchanged when the criterion was not evaluable
    (`observation.observed_pass is None`) — a missing input must never be read as a failure,
    otherwise an upstream outage would withdraw seals across the catalogue. That is also
    what keeps `observed_pass IS NULL` meaning "never evaluated" rather than "not evaluable
    last night", which step 5 relies on to decide what is in service.

    Args:
        prev: The stored state, or None if this criterion has never been evaluated.
        observation: The evaluator's verdict for this run.
        grace_period: How long an observed failure streak may last before the status flips.
            None means the status flips on the first failing day.
        probation_period: How long the criterion must go with no observed failure after
            recovering from a confirmed failure. None means the criterion has no probation.
        now: The evaluation timestamp.
        feed_id: Required when `prev` is None, to build the first state.
    """
    if observation.observed_pass is None:
        return prev

    resolved_feed_id = prev.feed_id if prev is not None else feed_id
    if resolved_feed_id is None:
        raise ValueError("feed_id is required when there is no previous state")

    base = prev or SealCriterionState(
        feed_id=resolved_feed_id, criterion=observation.criterion
    )

    # A criterion that has never produced a verdict gets no grace period. The grace period
    # holds a pass the criterion has actually earned, and one we have never seen pass has
    # nothing to hold — otherwise a feed that is broken the first time we look at it would
    # be reported as passing for up to a month on evidence we do not have.
    first_evaluation = base.observed_pass is None

    if observation.observed_pass:
        # The streak is over, so the grace period resets. The two `last_*` timestamps are
        # history and are never cleared.
        first_observed_failure_at = None
        last_observed_failure_at = base.last_observed_failure_at
        last_confirmed_failure_at = base.last_confirmed_failure_at
        confirmed_pass = True
    else:
        # first_observed_failure_at marks the start of the current streak. It is cleared on
        # recovery, so it is only None here at the start of a new streak.
        first_observed_failure_at = base.first_observed_failure_at or now
        last_observed_failure_at = now
        confirmed_pass = (
            grace_period is not None
            and not first_evaluation
            and now - first_observed_failure_at < grace_period
        )
        last_confirmed_failure_at = (
            base.last_confirmed_failure_at if confirmed_pass else now
        )

    return replace(
        base,
        observed_pass=observation.observed_pass,
        confirmed_pass=confirmed_pass,
        evaluated_at=now,
        first_observed_failure_at=first_observed_failure_at,
        last_observed_failure_at=last_observed_failure_at,
        last_confirmed_failure_at=last_confirmed_failure_at,
        probation_start=_probation_start(
            base=base,
            observed_pass=observation.observed_pass,
            confirmed_pass=confirmed_pass,
            probation_period=probation_period,
            now=now,
        ),
    )
