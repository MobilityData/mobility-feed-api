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

Steps 1 to 4 of the nightly job: the two no-verdict paths, observed failure tracking, the
confirmed status, and probation. This is the only place that knows about grace periods and
probation, and it is criterion-agnostic — the caller passes both from the evaluator. `now` is
a parameter rather than a call to `datetime.now()` so runs are idempotent within a day.

Two pieces of state are tracked per feed per criterion, and they are coupled in both
directions:

* `confirmed_status` — does the criterion pass right now, debounced by its grace period.
* `probation_start` — the stretch it must serve after recovering from a confirmed failure.

A confirmed failure starts probation, and probation suspends the grace period: it is a
privilege, and a criterion serving a penalty for an earlier confirmed failure has forfeited
it. That coupling is what makes IN_GRACE_PERIOD and ON_PROBATION mutually exclusive.

The seal (step 5, in seal_updater) requires every criterion in service to be a confirmed
pass and not on probation.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

from shared.common.seal_criteria import (
    CriterionPhase,
    CriterionStatus,
    SealCriterionName,
)
from tasks.seal_of_reliability.evaluators.base import CriterionObservation


@dataclass(frozen=True)
class SealCriterionState:
    """One row of the seal_criterion table.

    Both statuses are stated positively: PASS means the criterion passed. `observed_status`
    is the instantaneous check, `confirmed_status` the debounced status that drives the seal.
    Both default to NEVER_EVALUATED, which is the only value the job never writes back once a
    criterion has left it.

    `evaluated_at` and `last_verdict_at` are deliberately separate. The first records that
    the check ran at all, including runs that produced UNKNOWN or NOT_APPLICABLE; the second
    records the last PASS or FAIL. Only the second answers "has this criterion ever produced
    a verdict", which is what denies a first evaluation its grace period — testing
    `observed_status` instead would misread a criterion whose every run so far was UNKNOWN as
    already evaluated. The gap between the two is how long a criterion has been stuck.

    The failure timestamps stay negative on purpose: they record events that really are
    failures. Statuses describe state, timestamps record events.
    """

    feed_id: str
    criterion: SealCriterionName
    observed_status: CriterionStatus = CriterionStatus.NEVER_EVALUATED
    confirmed_status: CriterionStatus = CriterionStatus.NEVER_EVALUATED
    evaluated_at: Optional[datetime] = None
    last_verdict_at: Optional[datetime] = None
    first_observed_failure_at: Optional[datetime] = None
    last_observed_failure_at: Optional[datetime] = None
    last_confirmed_failure_at: Optional[datetime] = None
    probation_start: Optional[datetime] = None


def phase(state: Optional[SealCriterionState]) -> CriterionPhase:
    """Which debouncing mechanism is acting on this criterion, per the stored row.

    Derived rather than stored: a pure function of `probation_start`, `confirmed_status` and
    `first_observed_failure_at`, with no clock in it. It reports what the last run
    established, which is what keeps it consistent with the `confirmed_status` sitting beside
    it rather than answering "is the criterion in grace *right now*".

    The branches are mutually exclusive, so their order carries no meaning: ON_PROBATION
    suspends the grace period, so a criterion on probation can never also be holding a
    failure under grace.

    A state of None — a criterion with no row — has no history, so it is STEADY: not on
    probation, and no failure streak running.
    """
    if state is None:
        return CriterionPhase.STEADY
    if state.probation_start is not None:
        return CriterionPhase.ON_PROBATION
    if (
        state.confirmed_status is CriterionStatus.PASS
        and state.first_observed_failure_at is not None
    ):
        return CriterionPhase.IN_GRACE_PERIOD
    return CriterionPhase.STEADY


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
    observed_status: CriterionStatus,
    confirmed_status: CriterionStatus,
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

    The `phase(base)` test is redundant given the second: probation suspends the grace
    period, so an observed failure while on probation always reaches a confirmed failure.
    It is kept because it is the only place that rule is visible.
    """
    if probation_period is None:
        return None

    if observed_status is CriterionStatus.FAIL:
        if (
            phase(base) is CriterionPhase.ON_PROBATION
            or confirmed_status is CriterionStatus.FAIL
        ):
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
) -> SealCriterionState:
    """Apply one observation to a criterion's stored state.

    Always returns a state, so `evaluated_at` records every run. The two no-verdict paths
    stop short of steps 2 to 4:

    * UNKNOWN — we could not look. Only `observed_status` and `evaluated_at` are written;
      `confirmed_status`, probation and every failure timestamp keep their stored values. A
      missing input must never be read as a failure, otherwise an upstream outage would
      withdraw seals across the catalogue, and leaving `confirmed_status` alone is what keeps
      the criterion in the roll-up with its last verdict.
    * NOT_APPLICABLE — there is no question to ask. `confirmed_status` is written too, which
      is what withdraws the criterion from the roll-up, while probation and the failure
      timestamps stay frozen in case the criterion becomes applicable again.

    Args:
        prev: The stored state, or None if this criterion has no row for this feed yet.
        observation: The evaluator's verdict for this run.
        grace_period: How long an observed failure streak may last before the status flips.
            None means the status flips on the first failing day.
        probation_period: How long the criterion must go with no observed failure after
            recovering from a confirmed failure. None means the criterion has no probation.
        now: The evaluation timestamp.
        feed_id: Required when `prev` is None, to build the first state.
    """
    resolved_feed_id = prev.feed_id if prev is not None else feed_id
    if resolved_feed_id is None:
        raise ValueError("feed_id is required when there is no previous state")

    base = prev or SealCriterionState(
        feed_id=resolved_feed_id, criterion=observation.criterion
    )
    observed_status = observation.observed_status

    if not observed_status.is_verdict:
        # UNKNOWN keeps the stored confirmed_status so the criterion stays in the roll-up
        # with its last verdict; NOT_APPLICABLE overwrites it so the criterion leaves the
        # roll-up. Neither touches probation or the failure timestamps, and neither moves
        # last_verdict_at — no verdict was produced.
        confirmed_status = (
            CriterionStatus.NOT_APPLICABLE
            if observed_status is CriterionStatus.NOT_APPLICABLE
            else base.confirmed_status
        )
        return replace(
            base,
            observed_status=observed_status,
            confirmed_status=confirmed_status,
            evaluated_at=now,
        )

    # A criterion that has never produced a verdict gets no grace period. The grace period
    # holds a pass the criterion has actually earned, and one we have never seen pass has
    # nothing to hold — otherwise a feed that is broken the first time we look at it would
    # be reported as passing for up to a month on evidence we do not have.
    first_evaluation = base.last_verdict_at is None
    was_on_probation = phase(base) is CriterionPhase.ON_PROBATION

    if observed_status is CriterionStatus.PASS:
        # The streak is over, so the grace period resets. The two `last_*` timestamps are
        # history and are never cleared.
        first_observed_failure_at = None
        last_observed_failure_at = base.last_observed_failure_at
        last_confirmed_failure_at = base.last_confirmed_failure_at
        confirmed_status = CriterionStatus.PASS
    else:
        # first_observed_failure_at marks the start of the current streak. It is cleared on
        # recovery, so it is only None here at the start of a new streak.
        first_observed_failure_at = base.first_observed_failure_at or now
        last_observed_failure_at = now
        # Three conditions have to hold for the grace period to absorb this failure: the
        # criterion has one, it has earned it, and it has not forfeited it by being on
        # probation.
        within_grace = (
            grace_period is not None
            and not first_evaluation
            and not was_on_probation
            and now - first_observed_failure_at < grace_period
        )
        confirmed_status = (
            CriterionStatus.PASS if within_grace else CriterionStatus.FAIL
        )
        last_confirmed_failure_at = (
            base.last_confirmed_failure_at
            if confirmed_status is CriterionStatus.PASS
            else now
        )

    return replace(
        base,
        observed_status=observed_status,
        confirmed_status=confirmed_status,
        evaluated_at=now,
        last_verdict_at=now,
        first_observed_failure_at=first_observed_failure_at,
        last_observed_failure_at=last_observed_failure_at,
        last_confirmed_failure_at=last_confirmed_failure_at,
        probation_start=_probation_start(
            base=base,
            observed_status=observed_status,
            confirmed_status=confirmed_status,
            probation_period=probation_period,
            now=now,
        ),
    )
