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
from typing import Dict, Final, Optional


class SealCriterionName(str, Enum):
    """The six seal criteria. Values match the `seal_criterion_name` DB enum."""

    OFFICIAL = "official"
    STABLE = "stable"
    AVAILABLE = "available"
    COMPLIANT = "compliant"
    FRESH_COVERAGE = "fresh_coverage"
    FRESH_CONTINUOUS = "fresh_continuous"


# How long a criterion may keep failing its own check before the failure is confirmed and
# the seal is withdrawn. None means the status flips on the first failing day.
#
# `official` and `stable` have no grace period: they are point-in-time state checks on data
# we already hold, not observations of a fetched artifact, so there is no transient failure
# to debounce.
GRACE_PERIODS: Final[Dict[SealCriterionName, Optional[timedelta]]] = {
    SealCriterionName.OFFICIAL: None,
    SealCriterionName.STABLE: None,
    SealCriterionName.AVAILABLE: timedelta(days=14),
    SealCriterionName.COMPLIANT: timedelta(days=30),
    SealCriterionName.FRESH_COVERAGE: timedelta(days=7),
    SealCriterionName.FRESH_CONTINUOUS: timedelta(days=7),
}

# A criterion that recovers from a confirmed failure is put on probation: it must then go
# this long with no observed failure before it can contribute to the seal again. This is the
# "six clean months" rule - losing the seal is not undone by a single good day.
PROBATION_PERIOD: Final[timedelta] = timedelta(days=180)

# `official` and `stable` are exempt for the same reason they have no grace period. A feed
# that is marked official again is official again; there is no track record to rebuild.
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


def resolve_criterion(criterion: str | SealCriterionName) -> Optional[SealCriterionName]:
    """Coerce a stored criterion value to a `SealCriterionName`, or None if unknown.

    The DB enum and this enum are kept in step, so an unknown value means the DB has a
    criterion this build does not know about. Returning None lets callers skip it rather
    than fail the whole response.
    """
    if isinstance(criterion, SealCriterionName):
        return criterion
    try:
        return SealCriterionName(criterion)
    except ValueError:
        return None


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
