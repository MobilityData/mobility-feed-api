import logging
import functions_framework
from shared.helpers.logger import init_logger
from shared.helpers.feed_status import update_feed_statuses_query
from shared.database.database import with_db_session

init_logger()


@with_db_session
@functions_framework.http
def update_feed_status(_, db_session):
    """Updates the Feed status based on the latets dataset service date range."""
    try:
        logging.info("Database session started.")
        diff_counts = update_feed_statuses_query(db_session, [])
        return diff_counts, 200

    except Exception as error:
        logging.error(f"Error updating the feed statuses: {error}")
        return f"Error updating the feed statuses: {error}", 500
