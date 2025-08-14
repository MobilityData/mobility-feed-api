import json
import logging
import os
from typing import Dict

import pandas as pd
from sqlalchemy.orm import Session

from location_group_utils import (
    GeopolygonAggregate,
    extract_location_aggregate_geopolygons,
)

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Feed
from shared.helpers.locations import (
    select_highest_level_polygon,
    to_shapely,
    get_country_code_from_polygons,
    get_geopolygons_covers,
)
from shared.helpers.runtime_metrics import track_metrics

DEFAULT_LOCALITY_ADMIN_LEVEL = 7  # Default admin level for locality
# TODO: Move this to a configuration service or a config file
COUNTRY_LOCALITY_ADMIN_LEVELS = json.loads(
    os.getenv("COUNTRY_LOCALITY_ADMIN_LEVELS", '{"JP": 7, "NZ": 4}')
)


# TODO: Move this to a configuration service or a config file
def get_country_localy_admin_level(country_code: str) -> Dict[str, int]:
    """
    Get the country locality admin levels from the environment variable.
    If the variable is not set, return a default mapping.
    The default mapping is:
        {"JP": 7, "NZ": 4}
    """
    return COUNTRY_LOCALITY_ADMIN_LEVELS.get(country_code, DEFAULT_LOCALITY_ADMIN_LEVEL)


@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def extract_location_aggregates_per_polygon(
    feed: Feed,
    stops_df: pd.DataFrame,
    location_aggregates: Dict[str, GeopolygonAggregate],
    logger: logging.Logger,
    db_session: Session,
) -> None:
    """
    Batch points by their containing geopolygon and compute one location aggregate per group.
    """
    remaining_stops_df = stops_df.copy()
    processed_groups: set[str] = set()

    total_stop_count = len(remaining_stops_df)
    last_seen_count = total_stop_count
    batch_size = total_stop_count / 20  # Process 5% of the total stops in each batch
    while not remaining_stops_df.empty:
        if (last_seen_count - len(remaining_stops_df)) >= batch_size:
            logger.info(
                "Progress %.2f%% (%d/%d)",
                100 - (len(remaining_stops_df) / total_stop_count) * 100,
                len(remaining_stops_df),
                total_stop_count,
            )
            last_seen_count = len(remaining_stops_df)

        stop_point = remaining_stops_df.iloc[0][
            "geometry"
        ]  # GeoAlchemy WKT/WKB element or WKT string

        # Get all polygons containing this point (SQL, uses DB index on geopolygon.geometry)
        # geopolygons = (
        #     db_session.query(Geopolygon)
        #     .filter(Geopolygon.geometry.ST_Contains(stop_point))
        #     .all()
        # )

        geopolygons = get_geopolygons_covers(stop_point, db_session)

        highest = select_highest_level_polygon(geopolygons)
        if highest is None or highest.geometry is None:
            logger.warning("No geopolygons found for point: %s", stop_point)
            # drop just this point and continue
            remaining_stops_df = remaining_stops_df.iloc[1:]
            continue

        # TODO: review admin_level threshold per country/region
        country_code = get_country_code_from_polygons(geopolygons)
        if highest.admin_level >= get_country_localy_admin_level(country_code):
            # If admin_level >= locality_admin_level, we can filter points inside this polygon
            # Convert to Shapely geometry for spatial operations
            poly_shp = to_shapely(highest.geometry)
            in_poly_mask = remaining_stops_df["geometry"].apply(
                lambda g: poly_shp.contains(to_shapely(g))
            )
            count_before = len(remaining_stops_df)
            stops_in_polygon = remaining_stops_df.loc[in_poly_mask]
            # Remove them from the remaining pool
            remaining_stops_df = remaining_stops_df.drop(stops_in_polygon.index)
            logger.debug(
                "Points clustered in polygon %s: %d",
                highest.admin_level,
                count_before - len(remaining_stops_df),
            )
        else:
            # If admin_level < locality_admin_level, we assume the polygon is too large to filter points
            # directly, so we just use the first point as a representative
            logger.debug(
                "Point cannot be clustered in polygon. "
                "osm_id: %s, name: %s, "
                "iso_3166_1_code: %s, iso_3166_2_code: %s, admin_level: %s, ",
                highest.osm_id,
                highest.name,
                highest.iso_3166_1_code,
                highest.iso_3166_2_code,
                highest.admin_level,
            )
            stops_in_polygon = remaining_stops_df.iloc[[0]]
            remaining_stops_df = remaining_stops_df.iloc[1:]

        # Process ONLY ONE representative point for this stop "cluster"
        rep_geom = stops_in_polygon.iloc[0]["geometry"]
        agg = extract_location_aggregate_geopolygons(
            feed=feed,
            stop_point=rep_geom,
            geopolygons=geopolygons,
            logger=logger,
            db_session=db_session,
        )
        if not agg or agg.group_id in processed_groups:
            continue
        processed_groups.add(agg.group_id)

        if agg.group_id in location_aggregates:
            location_aggregates[agg.group_id].merge(agg)
        else:
            location_aggregates[agg.group_id] = agg

    logger.info("Completed processing all points")
