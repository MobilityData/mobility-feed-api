import logging
from datetime import datetime, timezone
from sqlalchemy import text
from shared.database_gen.sqlacodegen_models import Gtfsdataset, Feed, Gtfsfeed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from shared.common.gcp_utils import create_refresh_materialized_view_task


#  query to update the status of the feeds based on the service date range of the latest dataset
def update_feed_statuses_query(session: "Session", stable_feed_ids: list[str]):
    today_utc = datetime.now(timezone.utc).date()

    latest_dataset_subq = (
        session.query(
            Gtfsdataset.feed_id,
            Gtfsdataset.service_date_range_start,
            Gtfsdataset.service_date_range_end,
        )
        .join(Gtfsfeed, Gtfsfeed.latest_dataset_id == Gtfsdataset.id)
        .filter(
            Gtfsdataset.service_date_range_start.isnot(None),
            Gtfsdataset.service_date_range_end.isnot(None),
        )
        .subquery()
    )

    status_conditions = [
        (
            latest_dataset_subq.c.service_date_range_end < today_utc,
            "inactive",
        ),
        (
            latest_dataset_subq.c.service_date_range_start > today_utc,
            "future",
        ),
        (
            (latest_dataset_subq.c.service_date_range_start <= today_utc)
            & (latest_dataset_subq.c.service_date_range_end >= today_utc),
            "active",
        ),
    ]

    try:
        diff_counts: dict[str, int] = {}

        def get_filters(status: str):
            filters = [
                Feed.id == latest_dataset_subq.c.feed_id,
                Feed.status != text("'deprecated'::status"),
                Feed.status != text("'development'::status"),
                # We filter out feeds that already have the status so that the
                # update count reflects the number of feeds that actually
                # changed status.
                Feed.status != text("'%s'::status" % status),
                service_date_conditions,
            ]

            if len(stable_feed_ids) > 0:
                filters.insert(0, Feed.stable_id.in_(stable_feed_ids))

            return filters

        for service_date_conditions, status in status_conditions:
            diff_counts[status] = (
                session.query(Feed)
                .filter(*get_filters(status))
                .update({Feed.status: status}, synchronize_session=False)
            )
    except Exception as e:
        logging.error("Error updating feed statuses: %s", e)
        raise Exception(f"Error updating feed statuses: {e}")

    try:
        create_refresh_materialized_view_task()
        logging.info("Feed Database changes for status committed.")
        logging.info("Status Changes: %s", diff_counts)
        return diff_counts
    except Exception as e:
        logging.error("Error committing changes:", e)
        raise Exception(f"Error creating dataset: {e}")
