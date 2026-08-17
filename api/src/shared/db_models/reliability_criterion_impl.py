from datetime import datetime, timezone
from typing import Optional

from feeds_gen.models.reliability_criterion import ReliabilityCriterion
from shared.common.seal_criteria import (
    GRACE_PERIODS,
    PROBATION_PERIODS,
    SealCriterionName,
    window_end,
)
from shared.database_gen.sqlacodegen_models import Sealcriterion as SealcriterionOrm

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_NOT_EVALUATED = "not_evaluated"


class ReliabilityCriterionImpl(ReliabilityCriterion):
    """Implementation of the `ReliabilityCriterion` model.

    Converts one `sealcriterion` row to a Pydantic model, deriving the two countdowns the nightly
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
        criterion_row: SealcriterionOrm | None,
        criterion: SealCriterionName,
        now: Optional[datetime] = None,
    ) -> ReliabilityCriterion:
        """Create a model instance from a `sealcriterion` row.

        `criterion` is passed in rather than read off the row so a caller can ask for an entry for a
        criterion that has no row yet - which is how the report always returns all six.
        `now` is a parameter so the future-clamping is testable.
        """
        if criterion_row is None or criterion_row.observed_pass is None:
            return cls.not_evaluated(criterion)

        now = now or datetime.now(timezone.utc)
        observed_pass = bool(criterion_row.observed_pass)

        # `official` and `stable` are exempt from both windows, so their stored values are ignored
        # rather than trusted - the policy maps are the authority on which criteria serve them.
        probation_period = PROBATION_PERIODS.get(criterion)
        probation_start = criterion_row.probation_start if probation_period else None
        on_probation = probation_start is not None

        # A failing check still inside its grace period is not yet counting against the seal. Grace
        # does not apply during probation: a failure then restarts the probation clock outright, so
        # there is nothing left for grace to protect.
        in_grace_period = not observed_pass and criterion_row.confirmed_pass is True and not on_probation

        return cls(
            criterion=criterion.value,
            status=STATUS_PASS if observed_pass else STATUS_FAIL,
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
