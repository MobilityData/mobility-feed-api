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
    dry_run = get_parameters(payload)

    return refresh_materialized_view_task(dry_run)


# The feed search read model, and the location directory's feed counts, which change with the same events: feeds
# processed, reverse-geolocated or edited.
VIEW_NAMES = ("feedsearch", "locationfeedcount")


@with_db_session
def refresh_materialized_view_task(dry_run, db_session):
    """
    Refreshes the materialized views using the CONCURRENTLY command to avoid
    table locks. This function is triggered by a Cloud Task.

    Returns:
        dict: Response message and status code.
    """
    try:
        logging.info("Materialized view refresh task initiated.")

        view_names = ", ".join(VIEW_NAMES)
        if dry_run:
            msg = f"Dry run: {view_names} not refreshed."
            logging.info(msg)
            return {"message": msg, "dry_run": True}, 200
        failed = [
            view_name
            for view_name in VIEW_NAMES
            if not refresh_materialized_view(db_session, view_name)
        ]
        if failed:
            error_msg = f"Failed to refresh materialized view: {', '.join(failed)}"
            logging.error(error_msg)
            return {"error": error_msg}, 500
        success_msg = f"Successfully refreshed materialized views: {view_names}"
        logging.info(success_msg)
        return {"message": success_msg}, 200

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
