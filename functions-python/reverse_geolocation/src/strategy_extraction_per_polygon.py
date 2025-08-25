import json
import logging
import os
from functools import lru_cache
from typing import Dict

import pandas as pd
from sqlalchemy.orm import Session

from location_group_utils import (
    GeopolygonAggregate,
    extract_location_aggregate_geopolygons,
    create_or_update_stop_group,
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


# TODO: Move this to a configuration service or a config file
# TODO: review admin_level threshold per country/region
@lru_cache(maxsize=1)
def get_country_locality_admin_levels() -> Dict[str, int]:
    """
    Lazily load and cache the country locality admin levels from the environment variable.
    """
    return json.loads(os.getenv("COUNTRY_LOCALITY_ADMIN_LEVELS", '{"JP": 7}'))


@lru_cache(maxsize=1)
def get_country_locality_admin_level_default() -> Dict[str, int]:
    """
    Lazily load and cache the country locality admin levels from the environment variable.
    """
    return os.getenv("COUNTRY_LOCALITY_ADMIN_LEVEL_DEFAULT", 7)


# TODO: Move this to a configuration service or a config file
def get_country_locality_admin_level(country_code: str) -> Dict[str, int]:
    """
    Get the country locality admin levels from the environment variable.
    If the variable is not set, return a default mapping.
    The default mapping is:
        {"JP": 7}
    """
    return get_country_locality_admin_levels().get(
        country_code, get_country_locality_admin_level_default()
    )


@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def extract_location_aggregates_per_polygon(
    feed: Feed,
    stops_df: pd.DataFrame,
    location_aggregates: Dict[str, GeopolygonAggregate],
    use_cache: bool,
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
    batch_size = max(
        int(total_stop_count / 20), 0
    )  # Process ~5% of the total stops in each batch
    stop_clustered_total = 0
    while not remaining_stops_df.empty:
        if (last_seen_count - len(remaining_stops_df)) >= batch_size or len(
            remaining_stops_df
        ) == total_stop_count:
            logger.info(
                "Progress %.2f%% (%d/%d)",
                100 - (len(remaining_stops_df) / total_stop_count) * 100,
                len(remaining_stops_df),
                total_stop_count,
            )
            last_seen_count = len(remaining_stops_df)
            #     Commit the changes to the database after processing the batch
            db_session.commit()

        stop_point = remaining_stops_df.iloc[0][
            "geometry"
        ]  # GeoAlchemy WKT/WKB element or WKT string
        stops_in_polygon = remaining_stops_df.iloc[[0]]
        # remove the first point from the remaining stops
        remaining_stops_df = remaining_stops_df.iloc[1:]

        # Get all polygons containing this point (SQL, uses DB index on geopolygon.geometry)
        geopolygons = get_geopolygons_covers(stop_point, db_session)

        highest = select_highest_level_polygon(geopolygons)
        if highest is None or highest.geometry is None:
            logger.warning("No geopolygons found for point: %s", stop_point)
            continue

        rep_geom = highest.geometry
        country_code = get_country_code_from_polygons(geopolygons)
        if highest.admin_level >= get_country_locality_admin_level(country_code):
            # If admin_level >= locality_admin_level, we can filter points inside this polygon
            # Convert to Shapely geometry for spatial operations
            poly_shp = to_shapely(highest.geometry)
            in_poly_mask = remaining_stops_df["geometry"].apply(
                lambda g: poly_shp.contains(to_shapely(g))
            )
            count_before = len(remaining_stops_df)
            stops_mask = remaining_stops_df.loc[in_poly_mask]
            # concat the points that are inside the polygon
            # This will include the point that is being processed in this iteration
            stops_in_polygon = pd.concat([stops_in_polygon, stops_mask])
            # Remove them from the remaining pool
            remaining_stops_df = remaining_stops_df.drop(stops_mask.index)
            logger.debug(
                "Points clustered in polygon %s: %d",
                highest.admin_level,
                count_before - len(remaining_stops_df),
            )
            stop_clustered_total += count_before - len(remaining_stops_df)
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

        # Process ONLY ONE representative point for this stop "cluster"
        location_aggregate = extract_location_aggregate_geopolygons(
            stop_point=rep_geom,
            geopolygons=geopolygons,
            logger=logger,
            db_session=db_session,
        )
        if not location_aggregate or location_aggregate.group_id in processed_groups:
            continue
        location_aggregate.stop_count = len(stops_in_polygon)
        if use_cache:
            for _, stop in stops_in_polygon.iterrows():
                # Create or update the stop group for each stop in the cluster
                # This will also update the location_aggregate with the stop count
                create_or_update_stop_group(
                    feed,
                    stop["geometry"],
                    location_aggregate.location_group,
                    logger,
                    db_session,
                )
        processed_groups.add(location_aggregate.group_id)

        if location_aggregate.group_id in location_aggregates:
            location_aggregates[location_aggregate.group_id].merge(location_aggregate)
        else:
            location_aggregates[location_aggregate.group_id] = location_aggregate
    # Make sure to commit the changes after processing all points
    db_session.commit()
    logger.info(
        "Completed processing all points with clustered total %d", stop_clustered_total
    )
