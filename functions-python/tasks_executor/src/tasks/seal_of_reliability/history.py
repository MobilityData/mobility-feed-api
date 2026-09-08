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
"""The history the criteria read, and the one object they read it through.

`PreloadedHistory` is fetched once per batch of feeds, covering every day the run will
evaluate, and answers every point-in-time question the criteria ask. An evaluator calls a
`get_*_at` method on it and never touches a query or another criterion's history.

"""

from bisect import bisect_right
from dataclasses import dataclass
import datetime as datetime_module
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, TypeAlias

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Gtfsdataset

from shared.common.seal_criteria import SealCriterionName

# A feed's internal `feed.id`, not its `stable_id`.
FeedIdStr: TypeAlias = str

# A feed's public `mdb-1210` form. Not interchangeable with `FeedIdStr`: the loaders and
# lookups here are keyed by `feed.id`, while the task payloads name feeds this way.
FeedStableIdStr: TypeAlias = str


@dataclass(frozen=True)
class AvailabilityCheck:
    """One recorded attempt to fetch a feed's producer URL."""

    checked_at: datetime
    success: bool


@dataclass(frozen=True)
class ValidationReport:
    """The most recent validation report of one feed's closest dataset."""

    report_id: str
    dataset_id: str
    validated_at: datetime
    total_error: Optional[int] = None


@dataclass(frozen=True)
class DatasetCoverage:
    """One dataset in a feed's history, and the coverage fields the Fresh criteria read off it.

    The declared and validated windows are kept separate rather than resolved to one here: the
    criteria disagree about which to prefer, and a missing one of each means something
    different. `has_calendar_data` is what tells a dataset that published no calendar apart
    from one whose window we simply have not derived yet.
    """

    dataset_id: str
    downloaded_at: datetime
    service_date_range_start: Optional[datetime] = None
    service_date_range_end: Optional[datetime] = None

    # The producer's declared window, from the `feedinfo` row this dataset points at.
    feed_info_start: Optional[datetime_module.date] = None
    feed_info_end: Optional[datetime_module.date] = None

    # Whether the dataset carries `calendar.txt` or `calendar_dates.txt`.
    has_calendar_data: bool = False


class DatasetHistory:
    """Every feed's datasets over a run's day range, ready for point-in-time lookups.

    The per-feed lists are sorted by `downloaded_at` with the keys kept alongside, so a lookup
    is a binary search rather than a scan: a year's march asks once per feed per day.
    """

    def __init__(self, datasets_by_feed: Dict[FeedIdStr, List[DatasetCoverage]]):
        self._downloaded_at: Dict[FeedIdStr, List[datetime]] = {}
        self._datasets: Dict[FeedIdStr, List[DatasetCoverage]] = {}
        for feed_id, datasets in datasets_by_feed.items():
            # `dataset_id` breaks ties the same way the loader orders them, so two datasets
            # stamped at the same instant resolve to one answer rather than an arbitrary one.
            datasets.sort(
                key=lambda dataset: (dataset.downloaded_at, dataset.dataset_id)
            )
            self._datasets[feed_id] = datasets
            self._downloaded_at[feed_id] = [
                dataset.downloaded_at for dataset in datasets
            ]

    def closest_at(
        self, feed_id: FeedIdStr, moment: datetime
    ) -> Optional[DatasetCoverage]:
        keys = self._downloaded_at.get(feed_id)
        if not keys:
            return None
        index = bisect_right(keys, moment)
        if index == 0:
            return None
        return self._datasets[feed_id][index - 1]


class AvailabilityHistory:
    """Every feed's availability checks over a run's day range, sorted by `checked_at`."""

    def __init__(self, checks_by_feed: Dict[FeedIdStr, List[AvailabilityCheck]]):
        self._checked_at: Dict[FeedIdStr, List[datetime]] = {}
        self._checks: Dict[FeedIdStr, List[AvailabilityCheck]] = {}
        for feed_id, checks in checks_by_feed.items():
            checks.sort(key=lambda check: check.checked_at)
            self._checks[feed_id] = checks
            self._checked_at[feed_id] = [check.checked_at for check in checks]

    def latest_in_window(
        self, feed_id: FeedIdStr, moment: datetime, lookback: timedelta
    ) -> Optional[AvailabilityCheck]:
        keys = self._checked_at.get(feed_id)
        if not keys:
            return None
        index = bisect_right(keys, moment)
        if index == 0:
            return None
        check = self._checks[feed_id][index - 1]
        return check if check.checked_at > moment - lookback else None


class ValidationReportHistory:
    """Every validation report of the batch's datasets over a run's day range.

    Keyed by dataset rather than by feed: which dataset a feed is serving changes as a march
    proceeds, so the report wanted on one day belongs to a different dataset than the report
    wanted on another. The caller resolves the dataset first, then asks for its report.
    """

    def __init__(self, reports_by_dataset: Dict[str, List[ValidationReport]]):
        self._validated_at: Dict[str, List[datetime]] = {}
        self._reports: Dict[str, List[ValidationReport]] = {}
        for dataset_id, reports in reports_by_dataset.items():
            # `report_id` breaks ties, so two reports validated at the same instant resolve to
            # one answer rather than an arbitrary one.
            reports.sort(key=lambda report: (report.validated_at, report.report_id))
            self._reports[dataset_id] = reports
            self._validated_at[dataset_id] = [report.validated_at for report in reports]

    def latest_at(
        self, dataset_id: str, moment: datetime
    ) -> Optional[ValidationReport]:
        keys = self._validated_at.get(dataset_id)
        if not keys:
            return None
        index = bisect_right(keys, moment)
        if index == 0:
            return None
        return self._reports[dataset_id][index - 1]


class CompliantHistory:
    """What compliant loads: the datasets, and the validation reports of those datasets.

    It needs both because the report it wants on a given day is the report of *that day's*
    closest dataset. Holding them together keeps the pair loaded or absent as one.
    """

    def __init__(self, datasets: DatasetHistory, reports: ValidationReportHistory):
        self.datasets = datasets
        self.reports = reports


class PreloadedHistory:
    """Every criterion's data for every day of a run, fetched before any day is evaluated.

    Constructing one loads it: each evaluator is asked for its history once, covering the
    whole batch of feeds and the whole range of days, so the query count follows the number
    of criteria rather than feeds times days.

    Criteria then ask this object rather than each other's histories, which is what lets two
    criteria reading the same table share one load.
    """

    def __init__(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
        evaluators: Sequence,
    ):
        self._history_by_criterion: Dict[SealCriterionName, Any] = {}
        self.load(db_session, feeds, days, evaluators)

    def load(
        self,
        db_session: Session,
        feeds: Sequence,
        days: Sequence[date],
        evaluators: Sequence,
    ) -> None:
        """Ask every evaluator for its history, once, for the whole batch and range.

        Args:
            db_session: SQLAlchemy session.
            feeds: The batch of feeds, already loaded and eligibility-checked by the caller.
            days: Every UTC day that will be evaluated, ascending. Just one for a nightly run.
            evaluators: The `CriterionEvaluator` instances this run will apply. Deliberately
                not type-annotated as such: `evaluators.base` imports `context`, which imports
                this module, so annotating it would be a circular import.
        """
        self._history_by_criterion = {
            evaluator.name: evaluator.load_history(db_session, feeds, days)
            for evaluator in evaluators
        }

    def _history_for(self, criterion: SealCriterionName) -> Any:
        """What that criterion's `load_history` returned, or None if it has no loader."""
        return self._history_by_criterion.get(criterion)

    def get_closest_dataset_at(
        self, feed_id: FeedIdStr, moment: datetime
    ) -> Optional[DatasetCoverage]:
        """The feed's most recently downloaded dataset at `moment`, or None if it had none.

        None means the feed had no dataset at all by then.
        """
        # Both criteria load the datasets, so either store can answer. Whichever ran is fine:
        # they cover the same feeds and the same range.
        fresh = self._history_for(SealCriterionName.FRESH_COVERAGE)
        if fresh is not None:
            return fresh.closest_at(feed_id, moment)
        compliant = self._history_for(SealCriterionName.COMPLIANT)
        if compliant is not None:
            return compliant.datasets.closest_at(feed_id, moment)
        return None

    def get_latest_availability_check_at(
        self, feed_id: FeedIdStr, moment: datetime, lookback: timedelta
    ) -> Optional[AvailabilityCheck]:
        """The feed's latest availability check in `(moment - lookback, moment]`.

        None means no check was recorded in that window, which a criterion reads as UNKNOWN
        rather than as a failure.
        """
        history = self._history_for(SealCriterionName.AVAILABLE)
        return history.latest_in_window(feed_id, moment, lookback) if history else None

    def get_validation_report_at(
        self, dataset_id: str, moment: datetime
    ) -> Optional[ValidationReport]:
        """That dataset's latest validation report validated at or before `moment`.

        None means the dataset had not been validated by then, which compliant reads as
        UNKNOWN: an unvalidated dataset is not a clean bill of health.
        """
        history = self._history_for(SealCriterionName.COMPLIANT)
        return history.reports.latest_at(dataset_id, moment) if history else None

    def has_history_for(self, criterion: SealCriterionName) -> bool:
        """Whether that criterion's loader actually ran for this history.

        Lets an evaluator tell "the load ran and found nothing" apart from "the load never
        ran", which is a bug rather than a data condition.
        """
        return self._history_by_criterion.get(criterion) is not None


def _dataset_columns():
    return (
        Gtfsdataset.feed_id,
        Gtfsdataset.id,
        Gtfsdataset.downloaded_at,
        Gtfsdataset.service_date_range_end,
    )


def _rows_to_datasets(rows) -> List[Tuple[FeedIdStr, DatasetCoverage]]:
    return [
        (
            row.feed_id,
            DatasetCoverage(
                dataset_id=row.id,
                downloaded_at=row.downloaded_at,
                service_date_range_end=row.service_date_range_end,
            ),
        )
        for row in rows
    ]


def _datasets_at_range_start(
    db_session: Session, feed_ids: Sequence[FeedIdStr], range_start: datetime
) -> List[Tuple[FeedIdStr, DatasetCoverage]]:
    """One row per feed: the dataset it already had when the range opened.

    Strictly before `range_start`, so it is the state each feed carries into the first
    marched day. Without it, a feed whose most recent download predates the range would find
    no dataset at all on day 0 and the criteria would answer UNKNOWN.
    """
    rows = db_session.execute(
        select(*_dataset_columns())
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
    return _rows_to_datasets(rows)


def _datasets_in_range(
    db_session: Session,
    feed_ids: Sequence[FeedIdStr],
    range_start: datetime,
    range_end: datetime,
) -> List[Tuple[FeedIdStr, DatasetCoverage]]:
    """Every dataset downloaded while the range was open."""
    rows = db_session.execute(
        select(*_dataset_columns())
        .where(
            Gtfsdataset.feed_id.in_(list(feed_ids)),
            Gtfsdataset.downloaded_at.is_not(None),
            Gtfsdataset.downloaded_at >= range_start,
            Gtfsdataset.downloaded_at < range_end,
        )
        .order_by(Gtfsdataset.feed_id, Gtfsdataset.downloaded_at, Gtfsdataset.id)
    ).all()
    return _rows_to_datasets(rows)


def range_bounds(days: Sequence[date]) -> Tuple[datetime, datetime]:
    """The half-open instant range covering `days`.

    A march evaluates at each day's start while a nightly run evaluates part-way through its
    day, so the range closes at the end of the last day either way.
    """
    range_start = datetime.combine(min(days), time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(max(days), time.min, tzinfo=timezone.utc) + timedelta(
        days=1
    )
    return range_start, range_end


def load_dataset_history(
    db_session: Session, feeds: Sequence, days: Sequence[date]
) -> DatasetHistory:
    """Every dataset the batch's feeds had over `days`, plus the one each carried in.

    Two queries for the whole batch and the whole range, never one per day. Shared by
    fresh_coverage and compliant, which both resolve the dataset current on each day.
    """
    if not feeds or not days:
        return DatasetHistory({})

    feed_ids = [feed.id for feed in feeds]
    range_start, range_end = range_bounds(days)
    datasets_by_feed: Dict[FeedIdStr, List[DatasetCoverage]] = {}
    for feed_id, dataset in _datasets_at_range_start(
        db_session, feed_ids, range_start
    ) + _datasets_in_range(db_session, feed_ids, range_start, range_end):
        datasets_by_feed.setdefault(feed_id, []).append(dataset)
    return DatasetHistory(datasets_by_feed)
