from datetime import datetime, timezone

from feeds_gen.models.reliability_criterion import ReliabilityCriterion
from shared.common.seal_criteria import (
    CriterionStatus,
    SealCriterionName,
    grace_period_for,
    probation_period_for,
    resolve_criterion,
    window_end,
)
from shared.database_gen.sqlacodegen_models import SealCriterion as SealCriterionOrm

# The API `status` values are the `seal_criterion_status` DB enum verbatim, so a stored status is
# served as-is with no translation - `CriterionStatus` is a `str` enum over exactly those values,
# shared with the nightly job so the two cannot drift apart.


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
    def never_evaluated(cls, criterion: SealCriterionName) -> ReliabilityCriterion:
        """The entry for a criterion the nightly job has never produced a verdict for.

        The job skips such a criterion when deciding the seal rather than counting it as a failure,
        so it is reported as neither passing nor failing.
        """
        return cls(
            criterion=criterion.value,
            status=CriterionStatus.NEVER_EVALUATED.value,
            in_grace_period=False,
            on_probation=False,
        )

    @classmethod
    def from_orm(cls, criterion_row: SealCriterionOrm | None) -> ReliabilityCriterion | None:
        """Convert a `seal_criterion` row to a Pydantic model.

        Returns None when there is no row; callers that need an entry for a criterion with no row
        use `never_evaluated` instead - that is how the report always returns all six. A stored
        criterion this build does not know about raises (see `resolve_criterion`).
        """
        if criterion_row is None:
            return None

        criterion = resolve_criterion(criterion_row.criterion)
        now = datetime.now(timezone.utc)
        status = criterion_row.observed_status

        # `not_applicable` (withdrawn for this feed) and `never_evaluated` (no verdict ever) do not
        # participate in the seal, so they carry no grace period, no probation and no windows - just
        # the flat status, mirroring the row-less `never_evaluated` entry.
        if status in (CriterionStatus.NEVER_EVALUATED, CriterionStatus.NOT_APPLICABLE):
            return cls(
                criterion=criterion.value,
                status=status,
                in_grace_period=False,
                on_probation=False,
            )

        # Criteria exempt from a window (`official` and `stable` from both, `fresh_continuous` from
        # grace) have their stored values ignored rather than trusted - the policy maps are the
        # authority on which criteria serve them.
        grace_period = grace_period_for(criterion)
        probation_period = probation_period_for(criterion)
        probation_start = criterion_row.probation_start if probation_period else None
        on_probation = probation_start is not None

        # A failing check still inside its grace period is not yet counting against the seal: the
        # daily check reads `fail` but the debounced status is still `pass`. Grace does not apply
        # during probation: a failure then restarts the probation clock outright, so there is
        # nothing left for grace to protect.
        in_grace_period = (
            grace_period is not None
            and status == CriterionStatus.FAIL
            and criterion_row.confirmed_status == CriterionStatus.PASS
            and not on_probation
        )

        return cls(
            criterion=criterion.value,
            status=status,
            in_grace_period=in_grace_period,
            grace_period_ends_at=(
                window_end(criterion_row.first_observed_failure_at, grace_period, now) if in_grace_period else None
            ),
            on_probation=on_probation,
            probation_ends_at=window_end(probation_start, probation_period, now),
            evaluated_at=criterion_row.evaluated_at,
            first_failure_at=criterion_row.first_observed_failure_at,
            last_failure_at=criterion_row.last_observed_failure_at,
        )
