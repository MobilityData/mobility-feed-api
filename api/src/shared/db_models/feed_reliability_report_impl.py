from feeds_gen.models.feed_reliability_report import FeedReliabilityReport
from shared.common.seal_criteria import SealCriterionName, resolve_criterion
from shared.database_gen.sqlacodegen_models import Gtfsfeed as GtfsfeedOrm
from shared.db_models.reliability_criterion_impl import ReliabilityCriterionImpl


class FeedReliabilityReportImpl(FeedReliabilityReport):
    """Implementation of the `FeedReliabilityReport` model.

    Assembles the full Seal of Reliability breakdown for one feed from its `feed_reliability_seal`
    and `seal_criteria` relationships.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, feed: GtfsfeedOrm | None) -> FeedReliabilityReport | None:
        """Convert a feed's Seal of Reliability relationships to a Pydantic model.

        All six criteria are always returned, in enum order, with any the job has not reached filled
        in as `never_evaluated` - so a client can render six cards without checking which are present.
        A feed with no seal row at all is reported as simply not holding the seal, rather than as an
        error: the nightly job has not gotten to it yet.
        """
        if feed is None:
            return None

        seal = feed.feed_reliability_seal
        criterion_rows = list(feed.seal_criteria)

        # `resolve_criterion` raises on a stored criterion this build does not know about, so a
        # seal_criterion_name/SealCriterionName mismatch surfaces as an error instead of a report
        # that quietly omits a criterion.
        rows_by_criterion = {resolve_criterion(row.criterion): row for row in criterion_rows}

        # Every criterion gets an entry: the stored row when there is one, `never_evaluated`
        # otherwise - so a client can render six cards without checking which are present.
        criteria = [
            ReliabilityCriterionImpl.from_orm(rows_by_criterion.get(criterion))
            or ReliabilityCriterionImpl.never_evaluated(criterion)
            for criterion in SealCriterionName
        ]

        # The feed-level probation roll-up is derived from the criteria that were actually returned,
        # so it cannot disagree with them - unlike reading the roll-up row separately.
        probation_ends = [
            criterion.probation_ends_at for criterion in criteria if criterion.probation_ends_at is not None
        ]

        # `evaluated_at` is the most recent evaluation across the feed's criteria: the seal row
        # stores no evaluation time of its own.
        evaluated_ats = [row.evaluated_at for row in criterion_rows if row.evaluated_at is not None]

        return cls(
            feed_id=feed.stable_id,
            has_seal=bool(seal.has_seal) if seal is not None else False,
            earned_at=seal.seal_earned_at if seal is not None else None,
            lost_at=seal.seal_lost_at if seal is not None else None,
            evaluated_at=max(evaluated_ats) if evaluated_ats else None,
            on_probation=any(criterion.on_probation for criterion in criteria),
            probation_ends_at=max(probation_ends) if probation_ends else None,
            criteria=criteria,
        )
