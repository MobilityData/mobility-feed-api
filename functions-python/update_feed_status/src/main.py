import logging
import os
import functions_framework
from datetime import date
from shared.helpers.logger import Logger
from shared.helpers.database import Database
from typing import TYPE_CHECKING
from sqlalchemy import text
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)


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

    status_conditions = [
        (
            latest_dataset_subq.c.service_date_range_end < today,
            "inactive",
        ),
        (
            latest_dataset_subq.c.service_date_range_start > today,
            "future",
        ),
        (
            (latest_dataset_subq.c.service_date_range_start <= today)
            & (latest_dataset_subq.c.service_date_range_end >= today),
            "active",
        ),
    ]

    try:
        diff_counts: dict[str, int] = {}

        for service_date_conditions, status in status_conditions:
            diff_counts[status] = (
                session.query(Feed)
                .filter(
                    Feed.id == latest_dataset_subq.c.feed_id,
                    Feed.status != text("'deprecated'::status"),
                    Feed.status != text("'development'::status"),
                    # We filter out feeds that already have the status so that the
                    # update count reflects the number of feeds that actually
                    # changed status.
                    Feed.status != text("'%s'::status" % status),
                    service_date_conditions,
                )
                .update({Feed.status: status}, synchronize_session=False)
            )
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
