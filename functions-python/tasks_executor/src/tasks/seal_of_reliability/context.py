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
"""Seal eligibility (query + Python predicate) and bulk loading of evaluator inputs.

The evaluators are pure functions over a `FeedSealContext`, so every DB read for a batch of
feeds happens here, in a fixed number of queries regardless of batch size.

All six criteria are implemented. Official and Stable read the feed row alone; Available needs
the run window's availability rows and Compliant the closest dataset's validation report. The two
Fresh criteria share `_load_recent_datasets`. Each new criterion adds the fields it needs here
plus, where they are not already on the feed row, one bulk query to populate them.

Every query here is bounded by the run's `now` rather than reading a "current" pointer column,
so a run replayed for a past date sees the state as it was then. That is what lets a backfill
(#1782) reconstruct history with the same evaluators.
"""

import datetime as datetime_module
import itertools
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Final, Iterator, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared.common.continuous_coverage import CALENDAR_FILES
from shared.common.seal_criteria import AVAILABILITY_LOOKBACK
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedinfo,
    GtfsFeedAvailabilityCheck,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsfile,
    Validationreport,
    t_validationreportgtfsdataset,
)

# How far back down a feed's dataset history the contexts reach: `fresh_continuous` judges one
# boundary, so it needs the closest dataset and the one before it.
DATASET_HISTORY_DEPTH: Final[int] = 2


@dataclass(frozen=True)
class AvailabilityCheck:
    """The latest availability check for a feed within the run's window."""

    checked_at: datetime
    success: bool


@dataclass(frozen=True)
class ValidationReport:
    """The latest validation report of the feed's closest dataset, as of the run's `now`."""

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


@dataclass
class FeedSealContext:
    """Everything the evaluators need for one feed.

    Built by `build_contexts`. Evaluators read from this and never query.
    """

    feed_id: str
    # The evaluation timestamp. Passed in rather than read from the clock so evaluators
    # stay pure and a run can be replayed for any point in time.
    now: datetime
    stable_id: Optional[str] = None

    # Feed-level flags
    official: Optional[bool] = None
    is_producer_url_unstable: Optional[bool] = None
    seasonal: Optional[bool] = None

    # Stable: when the feed was first added to the database.
    feed_created_at: Optional[datetime] = None

    # The feed's closest dataset as of `now` - resolved by `downloaded_at` vs `now`
    closest_dataset: Optional[DatasetCoverage] = None

    # Fresh / continuous coverage: the dataset downloaded immediately before `closest_dataset`,
    # whose coverage the closest one has to meet. None when the feed had only one as of `now`.
    previous_dataset: Optional[DatasetCoverage] = None

    # Available: the latest availability check in the window this run covers.
    availability_check: Optional[AvailabilityCheck] = None

    # Compliant: the latest validation report of the dataset in `closest_dataset`.
    latest_validation_report: Optional[ValidationReport] = None


# Feeds in these statuses, or not published, are never eligible for the seal.
# `inactive` and `future` feeds are deliberately kept eligible.
INELIGIBLE_STATUSES = ("deprecated", "development")
ELIGIBLE_OPERATIONAL_STATUS = "published"


def is_seal_eligible(feed) -> bool:
    """Whether an already-loaded feed row is eligible for the seal.

    Same predicate as the DB-level filter in `_eligible_stable_ids_query`, applied in
    Python to a row already loaded by id. Used by `update_seals`, which is always given
    explicit ids and needs to tell a feed that does not exist apart from one that exists
    but is no longer eligible, without a second query.
    """
    return (
        feed.status not in INELIGIBLE_STATUSES
        and feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS
    )


def _eligible_stable_ids_query(
    db_session: Session, stable_feed_ids: Optional[Sequence[str]] = None
):
    """Base query: `stable_id` of every seal-eligible GTFS feed.

    `stable_feed_ids`, if given, narrows the candidate set without changing the
    predicate. Left as `None`, every eligible feed in the catalog is returned; this is
    what the seal orchestrator (issue #1800) uses to enumerate the full batch to fan out.
    """
    query = db_session.query(Gtfsfeed.stable_id).filter(
        Feed.status.notin_(INELIGIBLE_STATUSES),
        Feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS,
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(list(stable_feed_ids)))
    return query


def count_eligible_feeds(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> int:
    """Cheap `COUNT(*)` of eligible feeds — no rows loaded."""
    query = _eligible_stable_ids_query(db_session, stable_feed_ids=stable_feed_ids)
    if limit is not None:
        query = query.limit(limit)
    return query.count()


def iter_eligible_stable_ids(
    db_session: Session,
    batch_size: int,
    stable_feed_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> Iterator[List[str]]:
    """Stream eligible feeds' `stable_id`s in chunks of at most `batch_size`.

    Selects only `stable_id` and uses a server-side cursor (`stream_results=True`) so
    rows are pulled from Postgres as each chunk is consumed, instead of materializing the
    whole eligible-id list up front.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    query = (
        _eligible_stable_ids_query(db_session, stable_feed_ids=stable_feed_ids)
        .order_by(Gtfsfeed.stable_id)
        .execution_options(stream_results=True)
    )
    if limit is not None:
        query = query.limit(limit)
    rows = iter(query.yield_per(batch_size))
    while True:
        chunk = [row.stable_id for row in itertools.islice(rows, batch_size)]
        if not chunk:
            return
        yield chunk


def _load_recent_datasets(
    db_session: Session, feed_ids: Sequence[str], now: datetime
) -> Dict[str, List[DatasetCoverage]]:
    """feed_id -> its `DATASET_HISTORY_DEPTH` most recent datasets as of `now`, newest first.

    Ordered by `downloaded_at` among the datasets with `downloaded_at <= now` - looking
    backwards only, so a run for a past date cannot see a dataset downloaded after it.

    A feed missing from the result had no dataset at all as of `now`, which stays distinct
    from a `DatasetCoverage` whose windows are None: that one exists but was never processed.

    One query for the whole batch, `ROW_NUMBER()` rather than a per-feed `LIMIT`.
    """
    if not feed_ids:
        return {}

    # Correlated, so the flag comes back with the row rather than needing a second query.
    has_calendar_data = (
        select(1)
        .where(
            Gtfsfile.gtfs_dataset_id == Gtfsdataset.id,
            Gtfsfile.file_name.in_(CALENDAR_FILES),
        )
        .exists()
    )
    ranked = (
        select(
            Gtfsdataset.feed_id,
            Gtfsdataset.id,
            Gtfsdataset.downloaded_at,
            Gtfsdataset.service_date_range_start,
            Gtfsdataset.service_date_range_end,
            Feedinfo.feed_start_date,
            Feedinfo.feed_end_date,
            has_calendar_data.label("has_calendar_data"),
            func.row_number()
            .over(
                partition_by=Gtfsdataset.feed_id,
                order_by=(Gtfsdataset.downloaded_at.desc(), Gtfsdataset.id.desc()),
            )
            .label("recency"),
        )
        .select_from(Gtfsdataset)
        # Outer: a dataset with no `feed_info.txt` still comes back, with no declared window.
        .outerjoin(Feedinfo, Feedinfo.id == Gtfsdataset.feed_info_id)
        .where(
            Gtfsdataset.feed_id.in_(list(feed_ids)),
            Gtfsdataset.downloaded_at.is_not(None),
            Gtfsdataset.downloaded_at <= now,
        )
        .subquery()
    )
    rows = db_session.execute(
        select(ranked)
        .where(ranked.c.recency <= DATASET_HISTORY_DEPTH)
        .order_by(ranked.c.feed_id, ranked.c.recency)
    ).all()

    recent: Dict[str, List[DatasetCoverage]] = {}
    for row in rows:
        recent.setdefault(row.feed_id, []).append(
            DatasetCoverage(
                dataset_id=row.id,
                downloaded_at=row.downloaded_at,
                service_date_range_start=row.service_date_range_start,
                service_date_range_end=row.service_date_range_end,
                feed_info_start=row.feed_start_date,
                feed_info_end=row.feed_end_date,
                has_calendar_data=bool(row.has_calendar_data),
            )
        )
    return recent


def _load_validation_reports(
    db_session: Session,
    closest_datasets: Dict[str, DatasetCoverage],
    now: datetime,
) -> Dict[str, ValidationReport]:
    """feed_id -> the latest validation report of that feed's closest dataset, as of `now`.

    Scoped to the closest dataset, not the feed: a verdict on a superseded dataset does not describe
    what is being served. A feed whose closest dataset is not validated yet is left out, which the
    evaluator reads as UNKNOWN. One dataset can have several reports (a re-validation); the most
    recently validated wins, and ones with no `validated_at` are excluded.
    """
    if not closest_datasets:
        return {}
    feed_id_by_dataset = {
        dataset.dataset_id: feed_id for feed_id, dataset in closest_datasets.items()
    }
    join_table = t_validationreportgtfsdataset
    rows = db_session.execute(
        select(
            join_table.c.dataset_id,
            Validationreport.id,
            Validationreport.validated_at,
            Validationreport.total_error,
        )
        .select_from(join_table)
        .join(
            Validationreport,
            Validationreport.id == join_table.c.validation_report_id,
        )
        .where(
            join_table.c.dataset_id.in_(list(feed_id_by_dataset)),
            Validationreport.validated_at.is_not(None),
            Validationreport.validated_at <= now,
        )
        .distinct(join_table.c.dataset_id)
        .order_by(
            join_table.c.dataset_id,
            Validationreport.validated_at.desc(),
            Validationreport.id.desc(),
        )
    ).all()
    return {
        feed_id_by_dataset[row.dataset_id]: ValidationReport(
            report_id=row.id,
            dataset_id=row.dataset_id,
            validated_at=row.validated_at,
            total_error=row.total_error,
        )
        for row in rows
    }


def _load_availability(
    db_session: Session, feed_ids: Sequence[str], now: datetime
) -> Dict[str, AvailabilityCheck]:
    """feed_id -> its latest availability check in the 24 hours up to `now`.

    A rolling window rather than the UTC day of `now`, so a check still counts when the
    availability job (02:00 UTC) and the seal run (04:00 UTC) drift apart or one of them runs
    late.
    """
    if not feed_ids:
        return {}
    rows = db_session.execute(
        select(
            GtfsFeedAvailabilityCheck.feed_id,
            GtfsFeedAvailabilityCheck.checked_at,
            GtfsFeedAvailabilityCheck.success,
        )
        .where(
            GtfsFeedAvailabilityCheck.feed_id.in_(list(feed_ids)),
            GtfsFeedAvailabilityCheck.checked_at > now - AVAILABILITY_LOOKBACK,
            GtfsFeedAvailabilityCheck.checked_at <= now,
        )
        .distinct(GtfsFeedAvailabilityCheck.feed_id)
        .order_by(
            GtfsFeedAvailabilityCheck.feed_id,
            GtfsFeedAvailabilityCheck.checked_at.desc(),
            GtfsFeedAvailabilityCheck.id.desc(),
        )
    ).all()
    return {
        row.feed_id: AvailabilityCheck(checked_at=row.checked_at, success=row.success)
        for row in rows
    }


def build_contexts(
    db_session: Session, feeds: Sequence[Gtfsfeed], now: datetime
) -> Dict[str, FeedSealContext]:
    """Load everything the evaluators need for `feeds`, in a fixed number of queries.

    Args:
        db_session: SQLAlchemy session.
        feeds: The batch of feeds to load, already loaded (and eligibility-checked via
            `is_seal_eligible`) by the caller — `update_seals`.
        now: The evaluation timestamp.

    Returns:
        feed_id -> FeedSealContext.

    How to add a criterion's data. Two kinds:

    1. Already on the selected feed row (`official`, `created_at`, `seasonal`,
       `is_producer_url_unstable`). Add the field to FeedSealContext and read it off `feed`
       below. No query, no cost.

    2. Needs its own query. Add the field, then a module-level `_load_*` helper that takes
       the whole batch and returns a dict keyed by feed_id, and call it once here, as
       `_load_recent_datasets`, `_load_availability` and `_load_validation_reports` do.
       Keeping the query per batch rather than per feed is what holds the query count
       proportional to the number of criteria instead of the number of feeds. Bound the
       helper by `now` so the criterion stays replayable, and leave feeds with no row out of
       the returned dict rather than defaulting them: absent means "we did not look", which
       the evaluators read as UNKNOWN rather than as a failure.
    """
    feed_ids = [feed.id for feed in feeds]
    recent_datasets = _load_recent_datasets(db_session, feed_ids, now)
    closest_datasets = {
        feed_id: datasets[0]
        for feed_id, datasets in recent_datasets.items()
        if len(datasets) > 0
    }
    previous_datasets = {
        feed_id: datasets[1]
        for feed_id, datasets in recent_datasets.items()
        if len(datasets) > 1
    }
    availability = _load_availability(db_session, feed_ids, now)
    validation_reports = _load_validation_reports(db_session, closest_datasets, now)

    return {
        feed.id: FeedSealContext(
            feed_id=feed.id,
            now=now,
            stable_id=feed.stable_id,
            official=feed.official,
            is_producer_url_unstable=feed.is_producer_url_unstable,
            seasonal=feed.seasonal,
            feed_created_at=feed.created_at,
            closest_dataset=closest_datasets.get(feed.id),
            previous_dataset=previous_datasets.get(feed.id),
            availability_check=availability.get(feed.id),
            latest_validation_report=validation_reports.get(feed.id),
        )
        for feed in feeds
    }


def batched(items: Sequence, size: int):
    """Yield successive slices of `items` of at most `size` elements."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
