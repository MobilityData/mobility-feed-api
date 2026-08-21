from datetime import datetime, timezone
from typing import Any, Optional

from feeds_gen.models.feed_reliability_summary import FeedReliabilitySummary
from shared.common.seal_criteria import PROBATION_EXEMPT_CRITERIA, PROBATION_PERIOD, window_end
from shared.database_gen.sqlacodegen_models import Feed as FeedOrm


class FeedReliabilitySummaryImpl(FeedReliabilitySummary):
    """Implementation of the `FeedReliabilitySummary` model.

    Converts a feed's Seal of Reliability roll-up to a Pydantic model. `from_orm` reads it off the
    feed's `feed_reliability_seal` / `seal_criteria` relationships; `from_orm_search_row` reads the
    equivalent precomputed columns from the `feedsearch` materialized view.
    """

    class Config:
        """Pydantic configuration.
        Enabling `from_attributes` method to create a model instance from a SQLAlchemy row object."""

        from_attributes = True

    @classmethod
    def _build(
        cls,
        has_seal: bool,
        earned_at: Optional[datetime],
        lost_at: Optional[datetime],
        evaluated_at: Optional[datetime],
        latest_probation_start: Optional[datetime],
        now: Optional[datetime] = None,
    ) -> FeedReliabilitySummary:
        """Assemble the model from the flat roll-up values, deriving the probation countdown.

        `now` is a parameter so the future-clamping in `window_end` is testable.
        """
        now = now or datetime.now(timezone.utc)
        return cls(
            has_seal=bool(has_seal),
            earned_at=earned_at,
            lost_at=lost_at,
            evaluated_at=evaluated_at,
            on_probation=latest_probation_start is not None,
            probation_ends_at=window_end(latest_probation_start, PROBATION_PERIOD, now),
        )

    @classmethod
    def from_orm(cls, feed: FeedOrm | None, now: Optional[datetime] = None) -> FeedReliabilitySummary | None:
        """Convert a feed's Seal of Reliability relationships to a Pydantic model.

        Returns None when the feed has no seal row: it has never been evaluated and the badge has
        nothing to show. Reads `feed.feed_reliability_seal` and `feed.seal_criteria`, which callers
        are expected to have eager-loaded (see `db_utils.get_selectinload_options`), so this stays a
        pure in-memory reduction - no query per feed, no N+1 across a page.

        Probation rolls up only over the criteria that actually serve it (`official` and `stable`
        are point-in-time state checks and exempt), matching the equivalent roll-up in
        `liquibase/materialized_views/feed_search.sql` that search reads instead.
        """
        seal = feed.feed_reliability_seal if feed is not None else None
        if seal is None:
            return None

        evaluated_ats = [c.evaluated_at for c in feed.seal_criteria if c.evaluated_at is not None]
        probation_starts = [
            c.probation_start
            for c in feed.seal_criteria
            if c.probation_start is not None and c.criterion not in PROBATION_EXEMPT_CRITERIA
        ]
        return cls._build(
            has_seal=seal.has_seal,
            earned_at=seal.seal_earned_at,
            lost_at=seal.seal_lost_at,
            evaluated_at=max(evaluated_ats) if evaluated_ats else None,
            latest_probation_start=max(probation_starts) if probation_starts else None,
            now=now,
        )

    @classmethod
    def from_orm_search_row(cls, seal_row: Any | None, now: Optional[datetime] = None) -> FeedReliabilitySummary | None:
        """Convert a `feedsearch` materialized-view row to a Pydantic model.

        The view exposes the roll-up as flat columns (`has_seal`, `seal_earned_at`, ...), already
        aggregated, so search results carry the badge without touching the seal tables. Returns None
        when there is no row, or when the row carries no seal at all: both mean the feed has never
        been evaluated.
        """
        if seal_row is None or getattr(seal_row, "has_seal", None) is None:
            return None

        return cls._build(
            has_seal=seal_row.has_seal,
            earned_at=seal_row.seal_earned_at,
            lost_at=seal_row.seal_lost_at,
            evaluated_at=seal_row.seal_evaluated_at,
            latest_probation_start=seal_row.seal_latest_probation_start,
            now=now,
        )
