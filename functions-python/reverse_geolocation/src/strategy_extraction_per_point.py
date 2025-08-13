import logging
from typing import Dict

import pandas as pd
from sqlalchemy.orm import Session

from location_group_utils import GeopolygonAggregate, extract_location_aggregate, get_or_create_feed_osm_location_group, \
    get_or_create_location
from shared.database.database import with_db_session
from shared.helpers.runtime_metrics import track_metrics


@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def extract_location_aggregates_per_point(
    feed_id: str,
    stops_df: pd.DataFrame,
    location_aggregates: Dict[str, GeopolygonAggregate],
    logger: logging.Logger,
    db_session: Session,
) -> None:
    """Extract the location aggregates for the stops. The location_aggregates dictionary will be updated with the new
    location groups, keeping track of the stop count for each aggregate."""
    i = 0
    total_stop_count = len(stops_df)
    batch_size = 1000
    for _, stop in stops_df.iterrows():
        if i % batch_size == 0:
            logger.info("Processing stop %s/%s", i, total_stop_count)
        i += 1
        location_aggregate = extract_location_aggregate(
            feed_id, stop["geometry"], logger, db_session
        )
        if not location_aggregate:
            continue

        if location_aggregate.group_id in location_aggregates:
            location_aggregates[location_aggregate.group_id].merge(location_aggregate)
        else:
            location_aggregates[location_aggregate.group_id] = location_aggregate
        if (
            i % batch_size == 0
        ):  # Commit every batch stops to avoid reprocessing all stops in case of failure
            db_session.commit()