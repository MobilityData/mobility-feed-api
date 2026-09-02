"""Seal of Reliability policy values.

These are the published definition of the seal, so they live in code rather than in DB
config: changing any of them changes which feeds qualify, and that should go through code
review, tests and a deploy.

This module is under `shared/` so the nightly evaluation job
(`functions-python/tasks_executor`, which symlinks `api/src/shared/*`) and the read API
share one definition. The job owns the writing of `seal_criterion`; the API only reads it
back and derives the two countdowns from these windows.

See #1761 for the algorithm and #1760 for the tables.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Final, Iterable, Optional, Tuple

from shared.common.error_handling import raise_internal_http_error, unknown_seal_criterion


class SealCriterionName(str, Enum):
    """The six seal criteria. Values match the `seal_criterion_name` DB enum."""

    OFFICIAL = "official"
    STABLE = "stable"
    AVAILABLE = "available"
    COMPLIANT = "compliant"
    FRESH_COVERAGE = "fresh_coverage"
    FRESH_CONTINUOUS = "fresh_continuous"


class CriterionStatus(str, Enum):
    """A criterion's status. Values match the `seal_criterion_status` DB enum.

    Only PASS and FAIL are verdicts. The other three say why there is no verdict, and they
    are not interchangeable - the job's roll-up sends them in three different directions:

    * UNKNOWN - we could not look; the inputs the check needs were not there. A property of
      the run, not of the feed. The criterion keeps its last confirmed verdict and stays in
      the roll-up, so an upstream outage freezes a criterion rather than waiving it.
    * NOT_APPLICABLE - there is no question to ask; the criterion is deliberately excluded
      for this feed (Fresh / future coverage on a seasonal feed). A property of the feed.
      The criterion leaves the roll-up entirely.
    * NEVER_EVALUATED - never had a verdict, since the feed first appeared. The initial
      value, and the only one the job never writes back once a criterion has left it.

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
        """True for PASS and FAIL - the two values that mean the check actually answered."""
        return self in (CriterionStatus.PASS, CriterionStatus.FAIL)


class SealStatus(str, Enum):
    """The feed-level seal outcome."""

    GRANTED = "granted"
    NOT_GRANTED = "not_granted"
    UNKNOWN = "unknown"
    NEVER_EVALUATED = "never_evaluated"

    @property
    def is_answer(self) -> bool:
        """True for GRANTED and NOT_GRANTED - the two values that actually decide the seal."""
        return self in (SealStatus.GRANTED, SealStatus.NOT_GRANTED)


class CriterionPhase(str, Enum):
    """Which of the two debouncing mechanisms is currently acting on a criterion.

    Derived from the stored row rather than stored itself (see the job's
    `state_machine.phase`): it is a pure function of `probation_start`, `confirmed_status`
    and `first_observed_failure_at`, all of which are already on the row, so a stored copy
    would be a second thing to keep in step for no gain.

    The three values are mutually exclusive: probation suspends the grace period, so a
    criterion can never be serving a penalty and holding a failure under grace at once.
    """

    STEADY = "steady"
    IN_GRACE_PERIOD = "in_grace_period"
    ON_PROBATION = "on_probation"


# How long a criterion may keep failing its own check before the failure is confirmed and
# the seal is withdrawn. None means the status flips on the first failing day.
GRACE_PERIODS: Final[Dict[SealCriterionName, Optional[timedelta]]] = {
    SealCriterionName.OFFICIAL: None,
    SealCriterionName.STABLE: None,
    SealCriterionName.AVAILABLE: timedelta(days=14),
    SealCriterionName.COMPLIANT: timedelta(days=30),
    SealCriterionName.FRESH_COVERAGE: timedelta(days=14),
    SealCriterionName.FRESH_CONTINUOUS: None,
}

# A criterion that recovers from a confirmed failure is put on probation: it must then go
# this long with no observed failure before it can contribute to the seal again. This is the
# "six clean months" rule - losing the seal is not undone by a single good day.
PROBATION_PERIOD: Final[timedelta] = timedelta(days=180)

# `official` and `stable` are exempt
PROBATION_PERIODS: Final[Dict[SealCriterionName, Optional[timedelta]]] = {
    SealCriterionName.OFFICIAL: None,
    SealCriterionName.STABLE: None,
    SealCriterionName.AVAILABLE: PROBATION_PERIOD,
    SealCriterionName.COMPLIANT: PROBATION_PERIOD,
    SealCriterionName.FRESH_COVERAGE: PROBATION_PERIOD,
    SealCriterionName.FRESH_CONTINUOUS: PROBATION_PERIOD,
}

# The criteria that never serve probation, as the raw values stored in `seal_criterion.criterion`.
# A stray `probation_start` on one of these must not roll up into the feed-level probation.
PROBATION_EXEMPT_CRITERIA: Final[frozenset] = frozenset(
    name.value for name, period in PROBATION_PERIODS.items() if period is None
)


def roll_up_seal_status(
    criteria: Iterable[Tuple[CriterionStatus, bool]],
) -> SealStatus:
    """The feed-level seal outcome from its criteria.
    * every criterion NEVER_EVALUATED or NOT_APPLICABLE -> seal NEVER_EVALUATED.
    * any criterion failing or on probation -> seal NOT_GRANTED, whatever the rest say.
    * any remaining criterion NEVER_EVALUATED -> seal UNKNOWN.
    * otherwise every criterion is a confirmed pass and none is on probation -> seal GRANTED.
    """
    in_scope = [
        (confirmed_status, on_probation)
        for confirmed_status, on_probation in criteria
        if confirmed_status is not CriterionStatus.NOT_APPLICABLE
    ]
    if not in_scope:
        # Every criterion is NOT_APPLICABLE, so there is nothing left to judge the feed by.
        return SealStatus.NEVER_EVALUATED

    unjudged = sum(1 for confirmed_status, _ in in_scope if confirmed_status is CriterionStatus.NEVER_EVALUATED)
    if unjudged == len(in_scope):
        # All criteria are either NOT_APPLICABLE or NEVER_EVALUATED: nothing to judge the feed by.
        return SealStatus.NEVER_EVALUATED

    # One criterion is enough to deny the seal, so this is decidable even with the rest unjudged.
    # A pass on probation denies it too: probation withholds the criterion whatever its status.
    denied = any(
        confirmed_status is CriterionStatus.FAIL or (confirmed_status is CriterionStatus.PASS and on_probation)
        for confirmed_status, on_probation in in_scope
    )
    if denied:
        return SealStatus.NOT_GRANTED
    if unjudged:
        # Nothing denies the seal, but not everything has been judged: it cannot be granted yet.
        return SealStatus.UNKNOWN

    return SealStatus.GRANTED


# Stable: how long we must have been tracking a feed - measured from its
# `feed.created_at` - before it can be called stable.
TRACKING_PERIOD: Final[timedelta] = timedelta(days=180)

# Available: how far back to look for an availability check
AVAILABILITY_LOOKBACK: Final[timedelta] = timedelta(hours=24)

# Fresh / future coverage: how far ahead the closest dataset's service coverage must reach
FUTURE_COVERAGE_HORIZON: Final[timedelta] = timedelta(days=7)


def grace_period_for(criterion: str | SealCriterionName) -> Optional[timedelta]:
    """How long an observed failure of `criterion` may run before it is confirmed.

    None means the criterion has no grace period and its status flips on the first failing
    day. Callers ask for the window rather than declaring their own, so `GRACE_PERIODS`
    stays the only place a value can change.
    """
    return GRACE_PERIODS[resolve_criterion(criterion)]


def probation_period_for(criterion: str | SealCriterionName) -> Optional[timedelta]:
    """How long `criterion` must go with no observed failure after a confirmed failure.

    None means the criterion never serves probation (`official` and `stable`, which are
    point-in-time state checks).
    """
    return PROBATION_PERIODS[resolve_criterion(criterion)]


def resolve_criterion(criterion: str | SealCriterionName) -> SealCriterionName:
    """Coerce a stored criterion value to a `SealCriterionName`.

    The DB enum and this enum are kept in step, so an unknown value means `seal_criterion_name`
    has grown past this build. That is a schema/code mismatch we want to hear about rather than
    paper over, so it raises instead of silently dropping the criterion: serving a report that
    quietly omits a criterion would hide the incompatibility until someone noticed the gap.
    """
    if isinstance(criterion, SealCriterionName):
        return criterion
    try:
        return SealCriterionName(criterion)
    except ValueError:
        raise_internal_http_error(500, unknown_seal_criterion.format(criterion))


def window_end(start: Optional[datetime], window: Optional[timedelta], now: datetime) -> Optional[datetime]:
    """The end of a window that started at `start`, but only while it is still open.

    Returns None when the window does not apply (no start, or the criterion has no such
    window) and also when the end is not strictly in the future. Both windows are closed by
    the nightly job, so an end date in the past means the job has not run or did not clear
    the row: serving a stale countdown would be worse than serving none.
    """
    if start is None or window is None:
        return None
    end = start + window
    return end if end > now else None
