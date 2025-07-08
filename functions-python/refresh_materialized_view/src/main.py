import logging
import functions_framework
from flask import Request
from shared.helpers.logger import init_logger
from shared.database.database import with_db_session, refresh_materialized_view

init_logger()


@with_db_session
@functions_framework.http
def refresh_materialized_view_function(request: Request, db_session):
    """
    Refreshes a materialized view using the CONCURRENTLY command to avoid
    table locks.

    Returns:
        tuple: (response_message, status_code)
    """
    try:
        logging.info("Starting materialized view refresh function.")

        view_name = "my_materialized_view"
        logging.info(f"Refreshing materialized view: {view_name}")

        # Call the refresh function
        success = refresh_materialized_view(db_session, view_name)

        if success:
            success_msg = f"Successfully refreshed materialized view: {view_name}"
            logging.info(success_msg)
            return {"message": success_msg}, 200
        else:
            error_msg = f"Failed to refresh materialized view: {view_name}"
            logging.error(error_msg)
            return {"error": error_msg}, 500

    except Exception as error:
        error_msg = f"Error refreshing materialized view: {error}"
        logging.error(error_msg)
        return {"error": error_msg}, 500
