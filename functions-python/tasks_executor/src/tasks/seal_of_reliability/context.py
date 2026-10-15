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

Evaluators never touch the database. They read a `FeedSealContext`, which this module builds,
and all the loading for a batch of feeds happens here in a fixed number of queries however
many feeds there are.

Data reaches a criterion in one of three shapes, named here and referred to by name and
number in the rest of the code. `FeedSealContext` groups its fields by them:

1. **Feed field** - a column on the feed row, the same on every day evaluated.
2. **Fixed day** - one value, resolved for one day when it is loaded.
3. **History (day range)** - the whole range, asked per day.

A backfill fills 1 and 3 but never 2, so a criterion that reads a fixed-day field returns
UNKNOWN for every day it marches. Give a new criterion a history if it has to work there.
"""

import itertools
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Final, Iterator, List, Optional, Sequence

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from shared.common.continuous_coverage import CALENDAR_FILES
from shared.common.seal_criteria import AVAILABILITY_LOOKBACK, CriterionNameStr
from tasks.seal_of_reliability.history import (
    AvailabilityCheck,
    DatasetCoverage,
    FeedIdStr,
    FeedStableIdStr,
    PreloadedHistory,
    ValidationReport,
)
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedinfo,
    GtfsFeedAvailabilityCheck,
    Gtfsdataset,
    Gtfsfeed,
    Gtfsfile,
    SealCriterion,
    Validationreport,
    t_validationreportgtfsdataset,
)

# How far back down a feed's dataset history the contexts reach: `fresh_continuous` judges one
# boundary, so it needs the closest dataset and the one before it.
DATASET_HISTORY_DEPTH: Final[int] = 2


@dataclass
class FeedSealContext:
    """Everything the evaluators need for one feed on one day.

    Built by `build_contexts` for a nightly run, and by the backfill's `_march` for each day
    it marches. Evaluators read from this and never query.
    """

    feed_id: FeedIdStr
    # The moment being evaluated. Passed in rather than read from the clock, so evaluators
    # are pure functions and a run can be replayed for any date.
    now: datetime
    stable_id: Optional[FeedStableIdStr] = None

    # 1. Feed field. Read by official and stable.
    official: Optional[bool] = None
    is_producer_url_unstable: Optional[bool] = None
    seasonal: Optional[bool] = None

    # 1. Feed field as well: when the feed was first added to the database. Stable counts
    # its 180 days from here.
    feed_created_at: Optional[datetime] = None

    # 2. Fixed day, loaded by the `_load_*` helpers below. Only `build_contexts` fills these,
    # so they are None throughout a backfill and compliant and fresh_continuous cannot answer
    # a marched day. An evaluator finding its field None must return UNKNOWN, never a verdict.
    closest_dataset: Optional[DatasetCoverage] = None
    # The dataset downloaded immediately before `closest_dataset`, whose coverage the closest
    # one has to meet. None when the feed had only one as of `now`.
    previous_dataset: Optional[DatasetCoverage] = None

    availability_check: Optional[AvailabilityCheck] = None
    latest_validation_report: Optional[ValidationReport] = None

    # 3. History, see `PreloadedHistory`. Read by available and fresh_coverage, and filled by
    # both runs - the nightly one asks for a single day.
    #
    # One instance is shared by reference across every context of the batch, rather than
    # sliced per feed and per day: slicing would force every criterion into the same storage
    # shape, and during a backfill it would copy a year of history once per feed per day.
    history: Optional[PreloadedHistory] = None


# Feeds in these statuses, or not published, are never eligible for the seal.
# `inactive` and `future` feeds are deliberately kept eligible.
INELIGIBLE_STATUSES = ("deprecated", "development")
ELIGIBLE_OPERATIONAL_STATUS = "published"


def is_seal_eligible(feed) -> bool:
    """Whether an already-loaded feed row is eligible for the seal.

    The same test as the SQL filter in `_eligible_stable_ids_query`, but applied in Python to
    a row that has already been loaded by id. `update_seals` uses this one: it is always given
    explicit ids, and it needs to tell "this feed does not exist" apart from "it exists but is
    not eligible" without running a second query.
    """
    return (
        feed.status not in INELIGIBLE_STATUSES
        and feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS
    )


def _eligible_stable_ids_query(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[FeedStableIdStr]] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[CriterionNameStr]] = None,
):
    """Base query: the `stable_id` of every seal-eligible GTFS feed.

    Three optional narrowings, all off by default:

    `stable_feed_ids` restricts the result to those ids. Left as None, every eligible feed in
    the catalog comes back, which is what the seal orchestrator uses to enumerate the whole
    catalog before fanning it out.

    `exclude_backfilled` drops feeds that already have seal state. This is the backfill
    producer's candidate set: a feed the nightly job already owns has real history, and a
    backfill would write a reconstruction over it. It lives here rather than in the producer
    so that the count and the stream cannot apply different rules.

    `required_criteria` decides what "already has seal state" means. Given a list of criteria,
    a feed is only excluded once it has a `seal_criterion` row for **every** one of them.
    A feed with only some of them is not finished - that happens when an earlier run was
    narrowed to fewer criteria, or was run by a build that had fewer evaluators registered -
    and it should be marched again. Left as None, a single row is enough to exclude the feed,
    which is what a caller that does not know the run's criteria gets.
    """
    query = db_session.query(Gtfsfeed.stable_id).filter(
        Feed.status.notin_(INELIGIBLE_STATUSES),
        Feed.operational_status == ELIGIBLE_OPERATIONAL_STATUS,
    )
    if stable_feed_ids is not None:
        query = query.filter(Feed.stable_id.in_(list(stable_feed_ids)))
    if exclude_backfilled:
        criterion_rows = SealCriterion.__table__
        if required_criteria:
            wanted = sorted(set(required_criteria))
            # "Has a row for all of them" cannot be expressed as EXISTS, which only asks
            # whether some row matches. So count the distinct criteria this feed has out of
            # the ones we want, and keep the feed when that count is short. The count uses the
            # (feed_id, criterion) primary key, so it is cheap.
            complete = (
                select(func.count(distinct(criterion_rows.c.criterion)))
                .where(
                    criterion_rows.c.feed_id == Feed.id,
                    criterion_rows.c.criterion.in_(wanted),
                )
                .scalar_subquery()
            )
            query = query.filter(complete < len(wanted))
        else:
            has_state = select(criterion_rows.c.feed_id).where(
                criterion_rows.c.feed_id == Feed.id
            )
            query = query.filter(~has_state.exists())
    return query


def count_eligible_feeds(
    db_session: Session,
    stable_feed_ids: Optional[Sequence[FeedStableIdStr]] = None,
    limit: Optional[int] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[CriterionNameStr]] = None,
) -> int:
    """How many eligible feeds there are. A plain COUNT(*), no rows loaded."""
    query = _eligible_stable_ids_query(
        db_session,
        stable_feed_ids=stable_feed_ids,
        exclude_backfilled=exclude_backfilled,
        required_criteria=required_criteria,
    )
    if limit is not None:
        query = query.limit(limit)
    return query.count()


def iter_eligible_stable_ids(
    db_session: Session,
    batch_size: int,
    stable_feed_ids: Optional[Sequence[FeedStableIdStr]] = None,
    limit: Optional[int] = None,
    exclude_backfilled: bool = False,
    required_criteria: Optional[Sequence[CriterionNameStr]] = None,
) -> Iterator[List[FeedStableIdStr]]:
    """Yield eligible feeds' `stable_id`s in chunks of at most `batch_size`.

    Only `stable_id` is selected, and `stream_results=True` asks Postgres for a server-side
    cursor, so rows arrive as each chunk is consumed instead of the whole id list being built
    in memory first.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")
    query = (
        _eligible_stable_ids_query(
            db_session,
            stable_feed_ids=stable_feed_ids,
            exclude_backfilled=exclude_backfilled,
            required_criteria=required_criteria,
        )
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


def snapshot_date_of(now: datetime) -> date:
    """The UTC day that a run evaluating at `now` belongs to.

    Used for two things: the day a run's snapshot rows are keyed under, and the day its
    criteria are evaluated against. A value with no timezone is read as UTC rather than
    rejected, because the task entry points normalize whatever an operator types but
    `update_seals` can also be called directly from code.
    """
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(timezone.utc).date()


def _load_recent_datasets(
    db_session: Session, feed_ids: Sequence[FeedIdStr], now: datetime
) -> Dict[FeedIdStr, List[DatasetCoverage]]:
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

    recent: Dict[FeedIdStr, List[DatasetCoverage]] = {}
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
    closest_datasets: Dict[FeedIdStr, DatasetCoverage],
    now: datetime,
) -> Dict[FeedIdStr, ValidationReport]:
    """feed_id -> the latest validation report of that feed's closest dataset, as of `now`.

    Scoped to the closest dataset rather than to the feed on purpose: a verdict on a dataset
    that has since been replaced says nothing about what is being served now. A feed whose
    closest dataset has not been validated yet is simply absent from the result, and Compliant
    reads that as UNKNOWN.

    One dataset can have several reports, because it can be re-validated. The most recently
    validated one wins, and reports with no `validated_at` are ignored since they cannot be
    placed in time.
    """
    if not closest_datasets:
        return {}
    # Reports are keyed by dataset, but the caller wants them keyed by feed, so keep the
    # mapping back from dataset to feed while querying.
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
    db_session: Session, feed_ids: Sequence[FeedIdStr], now: datetime
) -> Dict[FeedIdStr, AvailabilityCheck]:
    """feed_id -> its latest availability check in the 24 hours up to `now`.

    A rolling 24-hour window rather than "the UTC day of `now`", so a check still counts when
    the availability job (02:00 UTC) and the seal run (04:00 UTC) drift apart, or when one of
    them runs late.
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
    db_session: Session,
    feeds: Sequence[Gtfsfeed],
    now: datetime,
    evaluators: Sequence,
) -> Dict[FeedIdStr, FeedSealContext]:
    """Build one context per feed, for a single day. This is the nightly run's path.

    It loads all three kinds of input: the kind-2 fields through the `_load_*` helpers above,
    and the kind-3 history through `PreloadedHistory.load` over a one-day range. Kind 1 is read off
    the feed rows the caller already has.

    The backfill does not call this. It calls `PreloadedHistory.load` once for its whole window and
    then builds a context per day itself, so kind-3 inputs are loaded through the evaluator in
    both paths and there is only ever one place they come from.

    Args:
        db_session: SQLAlchemy session, passed on to the evaluators' loaders.
        feeds: The batch of feeds, already loaded and eligibility-checked by the caller,
            which is `update_seals`.
        now: The moment to evaluate at.
        evaluators: The evaluators this run will apply. Required, not defaulted: an empty list
            would leave every criterion with no inputs and quietly turn its verdicts into
            UNKNOWN.

    Returns:
        feed_id -> FeedSealContext.

    Adding data for a new criterion. Pick the cheapest kind that works:

    1. It is already on the feed row (like `official` or `seasonal`). Add a field to
       `FeedSealContext` and read it off `feed` below. No query, and it is correct for any
       day.
    2. It needs a query, and one answer per run is enough. Add a field, write a module-level
       `_load_*` helper that takes the whole batch and returns a dict keyed by feed_id, and
       call it once here - `_load_recent_datasets`, `_load_availability` and
       `_load_validation_reports` are the examples. Filter the helper by `now` so the
       criterion stays replayable, and leave feeds with no row out of the dict instead of
       giving them a default: absent means "we did not look", which evaluators read as UNKNOWN
       rather than as a failure. Be aware that a backfill leaves these fields empty.
    3. The answer differs per day. Nothing changes in this file: override `load_history` on the
       evaluator and read it back in `_evaluate` with `ctx.history_for(self.name)`. This is the
       only kind a backfill can reconstruct.
    """
    feed_ids = [feed.id for feed in feeds]
    # Each feed's two most recent datasets as of `now`, newest first.
    recent_datasets = _load_recent_datasets(db_session, feed_ids, now)
    # The dataset each feed was serving at `now`.
    closest_datasets = {
        feed_id: datasets[0]
        for feed_id, datasets in recent_datasets.items()
        if len(datasets) > 0
    }
    # The one before it, for feeds that had two: `fresh_continuous` judges that boundary.
    previous_datasets = {
        feed_id: datasets[1]
        for feed_id, datasets in recent_datasets.items()
        if len(datasets) > 1
    }
    availability = _load_availability(db_session, feed_ids, now)
    # Runs after the datasets query because it needs to know which dataset to scope to.
    validation_reports = _load_validation_reports(db_session, closest_datasets, now)
    history = PreloadedHistory(db_session, feeds, [snapshot_date_of(now)], evaluators)

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
            history=history,
        )
        for feed in feeds
    }


def batched(items: Sequence, size: int):
    """Yield successive slices of `items`, each holding at most `size` elements."""
    for start in range(0, len(items), size):
        yield items[start : start + size]
