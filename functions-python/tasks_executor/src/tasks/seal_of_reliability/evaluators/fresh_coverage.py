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
"""Fresh (future coverage) criterion: the closest dataset still covers the near future."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.common.seal_criteria import (
    FUTURE_COVERAGE_HORIZON,
    CriterionStatus,
    SealCriterionName,
)
from shared.database_gen.sqlacodegen_models import Gtfsdataset
from tasks.seal_of_reliability.context import FeedSealContext
from tasks.seal_of_reliability.history import ClosestDataset, DatasetHistory
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


class FreshCoverageEvaluator(CriterionEvaluator):
    """`closest_dataset.service_date_range_end >= now + 7 days`.

    This is the only implemented criterion that can return NOT_APPLICABLE. A seasonal feed
    is expected to have coverage that runs out between seasons, so the question "does this
    feed cover the next week" has no meaningful answer for it.

    Its inputs also vary by day, so it loads them itself in `load_history` instead of reading
    a field on `FeedSealContext`. `ctx.closest_dataset` holds one answer, for one `now`, and a
    march needs one per day - see the `context` module docstring on the three kinds of input.
    """

    name = SealCriterionName.FRESH_COVERAGE

    def load_history(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Optional[DatasetHistory]:
        """Every dataset the batch's feeds had over `days`, plus the one each carried in.

        Two queries for the whole batch and the whole range, never one per day:

        1. The starting state - one row per feed, the closest dataset from strictly before the range
           opens. Without it, the first day of a march would find no dataset at all for a feed
           whose most recent one predates the range, and Fresh would answer UNKNOWN.
        2. Everything downloaded inside the range, which is what makes later days differ from
           earlier ones.

        Bounding query 2 by the range rather than loading a feed's whole history is what keeps
        the row count proportional to the days actually being evaluated.
        """
        if not feeds or not days:
            return DatasetHistory({})

        feed_ids = [feed.id for feed in feeds]
        # The march evaluates at each day's start, while a nightly run evaluates part-way
        # through its day, so the window closes at the end of the last day either way.
        range_start = datetime.combine(min(days), time.min, tzinfo=timezone.utc)
        range_end = datetime.combine(
            max(days), time.min, tzinfo=timezone.utc
        ) + timedelta(days=1)

        datasets_by_feed: Dict[str, List[ClosestDataset]] = {}
        for feed_id, dataset in self._datasets_at_range_start(
            db_session, feed_ids, range_start
        ) + self._datasets_in_range(db_session, feed_ids, range_start, range_end):
            datasets_by_feed.setdefault(feed_id, []).append(dataset)
        return DatasetHistory(datasets_by_feed)

    @staticmethod
    def _columns():
        return (
            Gtfsdataset.feed_id,
            Gtfsdataset.id,
            Gtfsdataset.downloaded_at,
            Gtfsdataset.service_date_range_end,
        )

    @classmethod
    def _rows_to_datasets(cls, rows) -> List[Tuple[str, ClosestDataset]]:
        return [
            (
                row.feed_id,
                ClosestDataset(
                    dataset_id=row.id,
                    downloaded_at=row.downloaded_at,
                    service_date_range_end=row.service_date_range_end,
                ),
            )
            for row in rows
        ]

    @classmethod
    def _datasets_at_range_start(
        cls, db_session: Session, feed_ids: Sequence[str], range_start: datetime
    ) -> List[Tuple[str, ClosestDataset]]:
        """One row per feed: the dataset it already had when the range opened.

        Strictly before `range_start`, so it is the state each feed carries into the first
        marched day. Without it, a feed whose most recent download predates the range would
        find no dataset at all on day 0 and Fresh would answer UNKNOWN.
        """
        rows = db_session.execute(
            select(*cls._columns())
            .where(
                Gtfsdataset.feed_id.in_(list(feed_ids)),
                Gtfsdataset.downloaded_at.is_not(None),
                Gtfsdataset.downloaded_at < range_start,
            )
            .distinct(Gtfsdataset.feed_id)
            .order_by(
                Gtfsdataset.feed_id,
                Gtfsdataset.downloaded_at.desc(),
                Gtfsdataset.id.desc(),
            )
        ).all()
        return cls._rows_to_datasets(rows)

    @classmethod
    def _datasets_in_range(
        cls,
        db_session: Session,
        feed_ids: Sequence[str],
        range_start: datetime,
        range_end: datetime,
    ) -> List[Tuple[str, ClosestDataset]]:
        """Every dataset downloaded while the range was open."""
        rows = db_session.execute(
            select(*cls._columns())
            .where(
                Gtfsdataset.feed_id.in_(list(feed_ids)),
                Gtfsdataset.downloaded_at.is_not(None),
                Gtfsdataset.downloaded_at >= range_start,
                Gtfsdataset.downloaded_at < range_end,
            )
            .order_by(Gtfsdataset.feed_id, Gtfsdataset.downloaded_at, Gtfsdataset.id)
        ).all()
        return cls._rows_to_datasets(rows)

    def _evaluate(self, ctx: FeedSealContext) -> Tuple[CriterionStatus, str]:
        # Applicability is a property of the feed, so it is settled before the inputs are
        # looked at: a seasonal feed's missing dataset is not an UNKNOWN worth reporting.
        if ctx.seasonal is True:
            return (
                CriterionStatus.NOT_APPLICABLE,
                "the feed is seasonal, so future coverage is not required",
            )

        if ctx.history is None or not ctx.history.has_history_for(self.name):
            # Not a data condition: the context was built without running this criterion's
            # loader. Said out loud in the reason rather than passed off as a missing dataset,
            # because the two look identical in the stored row and only this one is a bug.
            return (
                CriterionStatus.UNKNOWN,
                "fresh_coverage history was never loaded for this run - the context was "
                "built without calling load_history",
            )

        # Two different missing inputs, kept apart so the report says which: no dataset at
        # all as of this run, or one whose coverage was never extracted.
        closest = ctx.history.get_closest_dataset_at(ctx.feed_id, ctx.now)
        if closest is None:
            return CriterionStatus.UNKNOWN, "the feed has no dataset"

        coverage_end = closest.service_date_range_end
        if coverage_end is None:
            return (
                CriterionStatus.UNKNOWN,
                "the closest dataset has no service_date_range_end",
            )

        horizon = ctx.now + FUTURE_COVERAGE_HORIZON
        if coverage_end < horizon:
            return (
                CriterionStatus.FAIL,
                f"coverage ends {coverage_end.isoformat()}, before the "
                f"{FUTURE_COVERAGE_HORIZON.days}-day horizon {horizon.isoformat()}",
            )
        return (
            CriterionStatus.PASS,
            f"coverage ends {coverage_end.isoformat()}, at or beyond the "
            f"{FUTURE_COVERAGE_HORIZON.days}-day horizon {horizon.isoformat()}",
        )
