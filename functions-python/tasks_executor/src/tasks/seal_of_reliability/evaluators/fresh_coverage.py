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
"""Fresh (future coverage) criterion: the latest dataset still covers the near future."""

from bisect import bisect_right
from dataclasses import dataclass
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
from tasks.seal_of_reliability.evaluators.base import CriterionEvaluator


@dataclass(frozen=True)
class LatestDataset:
    """One dataset row, reduced to the fields Fresh reads off it."""

    dataset_id: str
    downloaded_at: datetime
    service_date_range_end: Optional[datetime] = None


class FreshCoverageInputs:
    """Every feed's dataset history over a run's day range, ready for as-of lookups.

    Holds the whole batch's history rather than one dataset per feed, because "the latest
    dataset" is a different row on each day a backfill marches. Built once per batch by
    `FreshCoverageEvaluator.load_inputs` and shared by reference across every context.

    The per-feed lists are sorted by `downloaded_at` and the keys are kept alongside them, so
    `as_of` is a binary search rather than a scan: a year's march asks this once per feed per
    day, which is where a linear lookup would start to cost real time.
    """

    def __init__(self, history: Dict[str, List[LatestDataset]]):
        self._downloaded_at: Dict[str, List[datetime]] = {}
        self._datasets: Dict[str, List[LatestDataset]] = {}
        for feed_id, datasets in history.items():
            # `dataset_id` breaks ties the same way `_load` orders them, so two datasets
            # stamped at the same instant resolve to one answer rather than an arbitrary one.
            datasets.sort(
                key=lambda dataset: (dataset.downloaded_at, dataset.dataset_id)
            )
            self._datasets[feed_id] = datasets
            self._downloaded_at[feed_id] = [
                dataset.downloaded_at for dataset in datasets
            ]

    def as_of(self, feed_id: str, moment: datetime) -> Optional[LatestDataset]:
        """The feed's most recently downloaded dataset at `moment`, or None if it had none.

        None means the feed had no dataset at all by then - deliberately distinct from a
        `LatestDataset` whose `service_date_range_end` is None, which had one whose coverage
        was never extracted. The criterion reads both as UNKNOWN but reports which.
        """
        keys = self._downloaded_at.get(feed_id)
        if not keys:
            return None
        index = bisect_right(keys, moment)
        if index == 0:
            return None
        return self._datasets[feed_id][index - 1]


class FreshCoverageEvaluator(CriterionEvaluator):
    """`latest dataset.service_date_range_end >= now + 7 days`.

    This is the only implemented criterion that can return NOT_APPLICABLE. A seasonal feed
    is expected to have coverage that runs out between seasons, so the question "does this
    feed cover the next week" has no meaningful answer for it.

    It is also the first criterion whose inputs vary by day, so it loads them itself through
    `load_inputs` rather than through a field on `FeedSealContext`: which dataset is "the
    latest" changes on every day a backfill marches (#1763).
    """

    name = SealCriterionName.FRESH_COVERAGE

    def load_inputs(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
    ) -> Optional[FreshCoverageInputs]:
        """Every dataset the batch's feeds had over `days`, plus the one each carried in.

        Two queries for the whole batch and the whole range, never one per day:

        1. The carry-in - one row per feed, the latest dataset downloaded strictly before the
           range opens. Without it the first day of a march would see no dataset at all for a
           feed whose most recent one predates the range, and Fresh would read that as UNKNOWN.
        2. Everything downloaded inside the range, which is what makes later days differ from
           earlier ones.

        Bounding query 2 by the range rather than loading a feed's whole history is what keeps
        the row count proportional to the days actually being evaluated.
        """
        if not feeds or not days:
            return FreshCoverageInputs({})

        feed_ids = [feed.id for feed in feeds]
        # The march evaluates at each day's start, while a nightly run evaluates part-way
        # through its day, so the window closes at the end of the last day either way.
        range_start = datetime.combine(min(days), time.min, tzinfo=timezone.utc)
        range_end = datetime.combine(
            max(days), time.min, tzinfo=timezone.utc
        ) + timedelta(days=1)

        history: Dict[str, List[LatestDataset]] = {}
        for feed_id, dataset in self._carry_in(
            db_session, feed_ids, range_start
        ) + self._in_range(db_session, feed_ids, range_start, range_end):
            history.setdefault(feed_id, []).append(dataset)
        return FreshCoverageInputs(history)

    @staticmethod
    def _columns():
        return (
            Gtfsdataset.feed_id,
            Gtfsdataset.id,
            Gtfsdataset.downloaded_at,
            Gtfsdataset.service_date_range_end,
        )

    @classmethod
    def _rows_to_datasets(cls, rows) -> List[Tuple[str, LatestDataset]]:
        return [
            (
                row.feed_id,
                LatestDataset(
                    dataset_id=row.id,
                    downloaded_at=row.downloaded_at,
                    service_date_range_end=row.service_date_range_end,
                ),
            )
            for row in rows
        ]

    @classmethod
    def _carry_in(
        cls, db_session: Session, feed_ids: Sequence[str], range_start: datetime
    ) -> List[Tuple[str, LatestDataset]]:
        """One row per feed: its latest dataset from before the range opened."""
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
    def _in_range(
        cls,
        db_session: Session,
        feed_ids: Sequence[str],
        range_start: datetime,
        range_end: datetime,
    ) -> List[Tuple[str, LatestDataset]]:
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

        inputs = ctx.inputs_for(self.name)
        if inputs is None:
            # Not a data condition: the context was built without running this criterion's
            # loader. Said out loud in the reason rather than passed off as a missing dataset,
            # because the two look identical in the stored row and only this one is a bug.
            return (
                CriterionStatus.UNKNOWN,
                "fresh_coverage inputs were never loaded for this run - the context was "
                "built without calling load_inputs",
            )

        # Two different missing inputs, kept apart so the report says which: no dataset at
        # all as of this run, or one whose coverage was never extracted.
        latest = inputs.as_of(ctx.feed_id, ctx.now)
        if latest is None:
            return CriterionStatus.UNKNOWN, "the feed has no latest dataset"

        coverage_end = latest.service_date_range_end
        if coverage_end is None:
            return (
                CriterionStatus.UNKNOWN,
                "the latest dataset has no service_date_range_end",
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
