import logging
import os
from typing import Dict, Optional

import pandas as pd
from shapely import wkt as shapely_wkt
from geoalchemy2 import WKTElement, WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from location_group_utils import GeopolygonAggregate, extract_location_aggregate, extract_location_aggregate_geopolygons

from shared.database.database import with_db_session
from shared.database_gen.sqlacodegen_models import Geopolygon
from shared.helpers.runtime_metrics import track_metrics


# ---------- geometry helpers ----------

def to_shapely(g):
    """
    Convert a GeoAlchemy WKB/WKT element or WKT string into a Shapely geometry.
    If it's already a Shapely geometry, return it as-is.
    """
    if isinstance(g, WKBElement):
        return to_shape(g)
    if isinstance(g, WKTElement):
        return shapely_wkt.loads(g.data)
    if isinstance(g, str):
        # assume WKT
        return shapely_wkt.loads(g)
    return g  # assume already shapely


def _select_highest_level_polygon(geopolygons: list[Geopolygon]) -> Optional[Geopolygon]:
    if not geopolygons:
        return None
    # Treat NULL admin_level as the lowest priority
    return max(geopolygons, key=lambda g: (-1 if g.admin_level is None else g.admin_level))

def _select_lowest_level_polygon(geopolygons: list[Geopolygon]) -> Optional[Geopolygon]:
    if not geopolygons:
        return None
    # Treat NULL admin_level as the lowest priority
    return min(geopolygons, key=lambda g: (100 if g.admin_level is None else g.admin_level))

# ---------- main implementations ----------

from typing import List, Optional

def get_country_code_from_polygons(geopolygons: list[Geopolygon]) -> Optional[str]:
    """
    Given a list of polygon GeoJSON-like features (each with 'properties'),
    return the country code (ISO 3166-1 alpha-2) from the most likely polygon.

    Args:
        polygons: List of dicts, each must have 'properties' with
                  'admin_level' and 'iso_3166_1_code'

    Returns:
        A two-letter country code string or None if not found
    """

    # Filter polygons that have country code
    country_polygons = [g for g in geopolygons if g.iso_3166_1_code]
    # valid_iso_3166_1 = any(g.iso_3166_1_code for g in geopolygons)

    if not country_polygons:
        return None

    # Prefer the one with the lowest admin_level (most local)
    lowest_admin_level_polygon = _select_lowest_level_polygon(country_polygons)

    return lowest_admin_level_polygon.iso_3166_1_code


def load_country_localy_admin_levels_from_file(file_path: str = "../country_locality_admin_levels.json") -> Dict[str, int]:
    """
    Load a mapping of country codes to their locality admin levels from a JSON file.
    """
    import json
    try:
        base_dir = os.path.dirname(__file__)
        full_path = os.path.join(base_dir, file_path)
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load locality admin levels from {file_path}: {e}")
        return {}

@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def extract_location_aggregates_per_polygon(
    feed_id: str,
    stops_df: pd.DataFrame,
    location_aggregates: Dict[str, GeopolygonAggregate],
    logger: logging.Logger,
    db_session: Session,
) -> None:
    """
    Batch points by their containing geopolygon and compute one location aggregate per group.
    """
    country_locality_admin_levels = load_country_localy_admin_levels_from_file()
    remaining_stops_df = stops_df.copy()
    processed_groups: set[str] = set()

    while not remaining_stops_df.empty:
        stop_point = remaining_stops_df.iloc[0]["geometry"]  # GeoAlchemy WKT/WKB element or WKT string

        # Get all polygons containing this point (SQL, uses DB index on geopolygon.geometry)
        geopolygons = (
            db_session.query(Geopolygon)
            .filter(Geopolygon.geometry.ST_Contains(stop_point))
            .all()
        )

        highest = _select_highest_level_polygon(geopolygons)
        if highest is None or highest.geometry is None:
            logger.warning("No geopolygons found for point: %s", stop_point)
            # drop just this point and continue
            remaining_stops_df = remaining_stops_df.iloc[1:]
            continue

        # TODO: review admin_level threshold per country/region
        country_code = get_country_code_from_polygons(geopolygons)
        if highest.admin_level >= country_locality_admin_levels.get(country_code, 7):
            # If admin_level >= 7, we can filter points inside this polygon
            # Convert to Shapely geometry for spatial operations
            poly_shp = to_shapely(highest.geometry)
            in_poly_mask = remaining_stops_df["geometry"].apply(lambda g: poly_shp.contains(to_shapely(g)))
            points_in_polygon = remaining_stops_df.loc[in_poly_mask]
            # Remove them from the remaining pool
            remaining_stops_df = remaining_stops_df.drop(points_in_polygon.index)
        else:
            # If admin_level < 7, we assume the polygon is too large to filter points
            # directly, so we just use the first point as a representative
            points_in_polygon = remaining_stops_df.iloc[[0]]
            remaining_stops_df = remaining_stops_df.iloc[1:]

        # Process ONLY ONE representative point for this polygon "cluster"
        rep_geom = points_in_polygon.iloc[0]["geometry"]
        agg = extract_location_aggregate_geopolygons(feed_id=feed_id, stop_point=rep_geom, geopolygons=geopolygons,
                                                     logger=logger, db_session=db_session)
        if not agg or agg.group_id in processed_groups:
            continue
        processed_groups.add(agg.group_id)

        if agg.group_id in location_aggregates:
            location_aggregates[agg.group_id].merge(agg)
        else:
            location_aggregates[agg.group_id] = agg

    # db_session.commit()

    logger.info("Completed processing all points for feed ID: %s", feed_id)
