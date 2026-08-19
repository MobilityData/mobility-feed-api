from datetime import datetime, timezone
from typing import Optional

from feeds_gen.models.reliability_criterion import ReliabilityCriterion
from shared.common.seal_criteria import (
    GRACE_PERIODS,
    PROBATION_PERIODS,
    SealCriterionName,
    window_end,
)
from shared.database_gen.sqlacodegen_models import SealCriterion as SealCriterionOrm

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_EVALUATED = "not_evaluated"
STATUS_NOT_APPLICABLE = "not_applicable"

# The debounced status that means "confirmed passing", i.e. the failure has not (yet) outlasted grace.
CONFIRMED_PASS = "pass"

# Maps the `seal_criterion_status` DB enum to the API `status`. The only rename is
# `never_evaluated` -> `not_evaluated`, keeping the API's existing term for "no verdict yet"; the
# other four values pass through unchanged. An unknown DB value degrades to `not_evaluated` rather
# than failing the response, matching `resolve_criterion`.
_DB_STATUS_TO_API = {
    "pass": STATUS_PASS,
    "fail": STATUS_FAIL,
    "unknown": STATUS_UNKNOWN,
    "never_evaluated": STATUS_NOT_EVALUATED,
    "not_applicable": STATUS_NOT_APPLICABLE,
}


class ReliabilityCriterionImpl(ReliabilityCriterion):
    """Implementation of the `ReliabilityCriterion` model.

    Converts one `seal_criterion` row to a Pydantic model, deriving the two countdowns the nightly
    job does not store. All the policy that decides those countdowns lives in
    `shared.common.seal_criteria`, so this class only applies it.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def not_evaluated(cls, criterion: SealCriterionName) -> ReliabilityCriterion:
        """The entry for a criterion the nightly job has never produced a verdict for.

        The job skips such a criterion when deciding the seal rather than counting it as a failure,
        so it is reported as neither passing nor failing.
        """
        return cls(
            criterion=criterion.value,
            status=STATUS_NOT_EVALUATED,
            in_grace_period=False,
            on_probation=False,
        )

    @classmethod
    def from_orm(
        cls,
        criterion_row: SealCriterionOrm | None,
        criterion: SealCriterionName,
        now: Optional[datetime] = None,
    ) -> ReliabilityCriterion:
        """Create a model instance from a `seal_criterion` row.

        `criterion` is passed in rather than read off the row so a caller can ask for an entry for a
        criterion that has no row yet - which is how the report always returns all six.
        `now` is a parameter so the future-clamping is testable.
        """
        if criterion_row is None:
            return cls.not_evaluated(criterion)

        now = now or datetime.now(timezone.utc)
        status = _DB_STATUS_TO_API.get(criterion_row.observed_status, STATUS_NOT_EVALUATED)

        # `not_applicable` (withdrawn for this feed) and `not_evaluated` (no verdict ever) do not
        # participate in the seal, so they carry no grace period, no probation and no windows - just
        # the flat status, mirroring the row-less `not_evaluated` entry.
        if status in (STATUS_NOT_EVALUATED, STATUS_NOT_APPLICABLE):
            return cls(
                criterion=criterion.value,
                status=status,
                in_grace_period=False,
                on_probation=False,
            )

        # `official` and `stable` are exempt from both windows, so their stored values are ignored
        # rather than trusted - the policy maps are the authority on which criteria serve them.
        probation_period = PROBATION_PERIODS.get(criterion)
        probation_start = criterion_row.probation_start if probation_period else None
        on_probation = probation_start is not None

        # A failing check still inside its grace period is not yet counting against the seal: the
        # daily check reads `fail` but the debounced status is still `pass`. Grace does not apply
        # during probation: a failure then restarts the probation clock outright, so there is
        # nothing left for grace to protect.
        in_grace_period = (
            status == STATUS_FAIL and criterion_row.confirmed_status == CONFIRMED_PASS and not on_probation
        )

        return cls(
            criterion=criterion.value,
            status=status,
            in_grace_period=in_grace_period,
            grace_period_ends_at=(
                window_end(criterion_row.first_observed_failure_at, GRACE_PERIODS.get(criterion), now)
                if in_grace_period
                else None
            ),
            on_probation=on_probation,
            probation_ends_at=window_end(probation_start, probation_period, now),
            evaluated_at=criterion_row.evaluated_at,
            first_failure_at=criterion_row.first_observed_failure_at,
            last_failure_at=criterion_row.last_observed_failure_at,
        )
