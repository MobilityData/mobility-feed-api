from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from feeds_gen.models.feed_reliability_report import FeedReliabilityReport
from shared.common.seal_criteria import SealCriterionName, resolve_criterion
from shared.database_gen.sqlacodegen_models import Sealcriterion as SealcriterionOrm
from shared.db_models.reliability_criterion_impl import ReliabilityCriterionImpl


class FeedReliabilityReportImpl(FeedReliabilityReport):
    """Implementation of the `FeedReliabilityReport` model.

    Assembles the full Seal of Reliability breakdown for one feed from its seal roll-up row and its
    `sealcriterion` rows.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(
        cls,
        feed_stable_id: str,
        seal_row: Any | None,
        criterion_rows: Iterable[SealcriterionOrm],
        now: Optional[datetime] = None,
    ) -> FeedReliabilityReport:
        """Create a model instance for one feed.

        All six criteria are always returned, in enum order, with any the job has not reached filled
        in as `not_evaluated` - so a client can render six cards without checking which are present.
        A feed with no seal row at all is reported as simply not holding the seal, rather than as an
        error: the nightly job has not gotten to it yet.
        """
        now = now or datetime.now(timezone.utc)

        rows_by_criterion = {}
        for row in criterion_rows:
            criterion = resolve_criterion(row.criterion)
            # An unrecognised criterion means the DB enum has grown past this build. Skipping it
            # degrades the report to "not evaluated" for that entry instead of failing the request.
            if criterion is not None:
                rows_by_criterion[criterion] = row

        criteria = [
            ReliabilityCriterionImpl.from_orm(rows_by_criterion.get(criterion), criterion, now)
            for criterion in SealCriterionName
        ]

        # The feed-level probation roll-up is derived from the criteria that were actually returned,
        # so it cannot disagree with them - unlike reading the roll-up row separately.
        probation_ends = [criterion.probation_ends_at for criterion in criteria if criterion.probation_ends_at]

        return cls(
            feed_id=feed_stable_id,
            has_seal=bool(seal_row.has_seal) if seal_row is not None else False,
            earned_at=seal_row.seal_earned_at if seal_row is not None else None,
            lost_at=seal_row.seal_lost_at if seal_row is not None else None,
            evaluated_at=seal_row.seal_evaluated_at if seal_row is not None else None,
            on_probation=any(criterion.on_probation for criterion in criteria),
            probation_ends_at=max(probation_ends) if probation_ends else None,
            criteria=criteria,
        )
