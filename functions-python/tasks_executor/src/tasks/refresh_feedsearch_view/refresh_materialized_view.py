import logging
from shared.database.database import refresh_materialized_view, with_db_session


def refresh_materialized_view_handler(payload):
    """
    Handler for refreshing the materialized view.

    Args:
        payload (dict): Incoming payload data.

    Returns:
        dict: Response message and status code.
    """
    (dry_run) = get_parameters(payload)

    return refresh_materialized_view_task(dry_run)


@with_db_session
def refresh_materialized_view_task(dry_run, db_session):
    """
    Refreshes the materialized view using the CONCURRENTLY command to avoid
    table locks. This function is triggered by a Cloud Task.

    Returns:
        dict: Response message and status code.
    """
    try:
        logging.info("Materialized view refresh task initiated.")

        view_name = "feedsearch"
        success = refresh_materialized_view(db_session, view_name)

        if success:
            success_msg = "Successfully refreshed materialized view: " f"{view_name}"
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


def get_parameters(payload):
    """
    Get parameters from the payload and environment variables.

    Args:
        payload (dict): dictionary containing the payload data.
    Returns:
        tuple: (dry_run, after_date)
    """
    dry_run = payload.get("dry_run", False)
    return dry_run
