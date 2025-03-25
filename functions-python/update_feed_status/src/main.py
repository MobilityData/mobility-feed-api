import logging
import os
import functions_framework
from datetime import datetime, timezone
from shared.helpers.logger import Logger
from shared.helpers.database import Database
from typing import TYPE_CHECKING
from sqlalchemy import case, text
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed, t_feedsearch
from shared.helpers.database import refresh_materialized_view

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)


#  query to update the status of the feeds based on the service date range of the latest dataset
def update_feed_statuses_query(session: "Session"):
    today_utc = datetime.now(timezone.utc).date()

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
            latest_dataset_subq.c.service_date_range_end < today_utc,
            text("'inactive'::status"),
        ),
        (
            latest_dataset_subq.c.service_date_range_start > today_utc,
            text("'future'::status"),
        ),
        (
            (latest_dataset_subq.c.service_date_range_start <= today_utc)
            & (latest_dataset_subq.c.service_date_range_end >= today_utc),
            text("'active'::status"),
        ),
    )

    try:
        updated_count = (
            session.query(Feed)
            .filter(
                Feed.status != text("'deprecated'::status"),
                Feed.status != text("'development'::status"),
                Feed.id == latest_dataset_subq.c.feed_id,
            )
            .update({Feed.status: new_status}, synchronize_session=False)
        )
    except Exception as e:
        logging.error(f"Error updating feed statuses: {e}")
        raise Exception(f"Error updating feed statuses: {e}")

    try:
        session.commit()
        refresh_materialized_view(session, t_feedsearch.name)
        logging.info("Feed Database changes committed.")
        session.close()
        return updated_count
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
    update_count = 0
    try:
        with db.start_db_session() as session:
            logging.info("Database session started.")
            update_count = update_feed_statuses_query(session)

    except Exception as error:
        logging.error(f"Error updating the feed statuses: {error}")
        return f"Error updating the feed statuses: {error}", 500

    return f"Script executed successfully. {update_count} feeds updated", 200
