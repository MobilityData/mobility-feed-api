from datetime import datetime, timezone
from typing import Any, Optional

from feeds_gen.models.feed_reliability_summary import FeedReliabilitySummary
from shared.common.seal_criteria import PROBATION_PERIOD, window_end


class FeedReliabilitySummaryImpl(FeedReliabilitySummary):
    """Implementation of the `FeedReliabilitySummary` model.

    Converts one row of the Seal of Reliability roll-up - either from
    `shared.common.db_utils.get_reliability_seals` or from the `feedsearch` materialized view,
    which exposes the same column names - to a Pydantic model.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def from_orm(cls, seal_row: Any | None, now: Optional[datetime] = None) -> FeedReliabilitySummary | None:
        """Create a model instance from a seal roll-up row.

        Returns None when there is no row, or when the row carries no seal at all: both mean the
        feed has never been evaluated, and the badge has nothing to show. `now` is a parameter so
        the future-clamping below is testable.
        """
        if seal_row is None or getattr(seal_row, "has_seal", None) is None:
            return None

        now = now or datetime.now(timezone.utc)
        probation_start = seal_row.seal_latest_probation_start
        return cls(
            has_seal=bool(seal_row.has_seal),
            earned_at=seal_row.seal_earned_at,
            lost_at=seal_row.seal_lost_at,
            evaluated_at=seal_row.seal_evaluated_at,
            on_probation=probation_start is not None,
            probation_ends_at=window_end(probation_start, PROBATION_PERIOD, now),
        )
