import logging
import os
import functions_framework
from collections import defaultdict
from datetime import date
from shared.helpers.logger import Logger
from shared.helpers.database import Database
from typing import TYPE_CHECKING, Iterator, NamedTuple
from sqlalchemy import case, text
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)


FEED_FILTERS = [
    Feed.status != text("'deprecated'::status"),
    Feed.status != text("'development'::status"),
]


class PartialFeed(NamedTuple):
    """
    Subset of the Feed entity with only the fields queried in `fetch_feeds`.
    """

    id: int
    status: str


def fetch_feeds(session: "Session") -> Iterator[PartialFeed]:
    query = (
        session
        # When adding or removing fields here, `PartialFeed` should be updated to
        # match, for type safety.
        .query(Feed.id, Feed.status)
        .filter(**FEED_FILTERS)
        .yield_per(500)
    )
    for feed in query:
        yield PartialFeed(id=feed.id, status=feed.status)


def get_diff_counts(
    feed_ids_by_before_status: defaultdict[str, set[int]],
    session: "Session",
) -> defaultdict[str, int]:
    """
    Get the number of feeds that have transitioned to each status. If a status
    doesn't have new feeds, it's excluded from the response.
    """
    count_per_new_status: defaultdict[str, int] = defaultdict(int)
    for feed in fetch_feeds(session):
        if feed.id not in feed_ids_by_before_status[feed.status]:
            count_per_new_status[feed.status] += 1
    return count_per_new_status


#  query to update the status of the feeds based on the service date range of the latest dataset
def update_feed_statuses_query(session: "Session"):
    today = date.today()

    latest_dataset_subq = (
        session.query(
            Gtfsdataset.feed_id,
            Gtfsdataset.service_date_range_start,
            Gtfsdataset.service_date_range_end,
        )
        .filter(
            Gtfsdataset.latest.is_(True),
            Gtfsdataset.service_date_range_start.isnot(None),
            Gtfsdataset.service_date_range_end.isnot(None),
        )
        .subquery()
    )

    new_status = case(
        (
            latest_dataset_subq.c.service_date_range_end < today,
            text("'inactive'::status"),
        ),
        (
            latest_dataset_subq.c.service_date_range_start > today,
            text("'future'::status"),
        ),
        (
            (latest_dataset_subq.c.service_date_range_start <= today)
            & (latest_dataset_subq.c.service_date_range_end >= today),
            text("'active'::status"),
        ),
    )

    try:
        feed_ids_by_before_status: defaultdict[str, set[int]] = defaultdict(set[int])
        for feed in fetch_feeds(session):
            feed_ids_by_before_status[feed.status].add(feed.id)

        _ = (
            session.query(Feed)
            .filter(
                Feed.id == latest_dataset_subq.c.feed_id,
                **FEED_FILTERS,
            )
            .update({Feed.status: new_status}, synchronize_session=False)
        )

        diff_counts = get_diff_counts(feed_ids_by_before_status, session)
    except Exception as e:
        logging.error(f"Error updating feed statuses: {e}")
        raise Exception(f"Error updating feed statuses: {e}")

    try:
        session.commit()
        logging.info("Feed Database changes committed.")
        session.close()
        return diff_counts
    except Exception as e:
        logging.error("Error committing changes:", e)
        session.rollback()
        session.close()
        raise Exception(f"Error creating dataset: {e}")


@functions_framework.http
def update_feed_status(_):
    """Updates the Feed status based on the latets dataset service date range."""
    Logger.init_logger()
    db = Database(database_url=os.getenv("FEEDS_DATABASE_URL"))
    try:
        with db.start_db_session() as session:
            logging.info("Database session started.")
            diff_counts = update_feed_statuses_query(session)
            return diff_counts, 200

    except Exception as error:
        logging.error(f"Error updating the feed statuses: {error}")
        return f"Error updating the feed statuses: {error}", 500
