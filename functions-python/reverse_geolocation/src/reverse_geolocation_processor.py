import io
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Tuple, Optional, List
from sqlalchemy.sql import text
import flask
import pandas as pd
import requests
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from google.cloud import storage
from shapely.geometry import mapping
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from location_group_utils import ERROR_STATUS_CODE, GeopolygonAggregate, generate_color
from shared.database_gen.sqlacodegen_models import (
    Geopolygon,
    Feed,
    Stop,
    Osmlocationgroup,
    Feedosmlocation,
    Location,
    t_feedsearch,
)
from shared.helpers.database import with_db_session
from shared.helpers.logger import Logger, StableIdFilter
from shared.helpers.utils import cors_configuration


# Initialize logging
logging.basicConfig(level=logging.INFO)


def parse_request_parameters(
    request: flask.Request,
) -> Tuple[pd.DataFrame, str]:
    """
    Parse the request parameters and return a DataFrame with the stops data.
    """
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    logging.info(f"Request JSON: {request_json}")

    if (
        not request_json
        or "stops_url" not in request_json
        or "stable_id" not in request_json
    ):
        raise ValueError(
            "Invalid request: missing 'stops_url' or 'stable_id' parameter."
        )

    stable_id = request_json["stable_id"]

    # Read the stops from the URL
    try:
        s = requests.get(request_json["stops_url"]).content
        stops_df = pd.read_csv(io.StringIO(s.decode("utf-8")))
    except Exception as e:
        raise ValueError(
            f"Error reading stops from URL {request_json['stops_url']}: {e}"
        )

    return stops_df, stable_id


@with_db_session(echo=False)
def get_cached_geopolygons(
    stable_id: str, stops_df: pd.DataFrame, db_session
) -> Tuple[str, Dict[str, GeopolygonAggregate], pd.DataFrame]:
    """
    Get the geopolygons from the database cache.

    Returns:
        location_groups: Set of LocationGroup objects with stop counts.
        unmatched_stop_df: DataFrame of unmatched stops for further processing.
    """
    logging.info(f"Getting cached geopolygons for stable ID {stable_id}.")

    if stops_df.empty:
        logging.warning("The provided stops DataFrame is empty.")
        raise ValueError("The provided stops DataFrame is empty.")

    stops_df["geometry"] = stops_df.apply(
        lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
        axis=1,
    )
    stops_df["geometry_str"] = stops_df["geometry"].apply(str)

    feed = (
        db_session.query(Feed)
        .options(joinedload(Feed.stops))
        .filter(Feed.stable_id == stable_id)
        .one_or_none()
    )
    if not feed:
        logging.warning(f"No feed found for stable ID {stable_id}.")
        raise ValueError(f"No feed found for stable ID {stable_id}.")

    feed_id = feed.id

    cached_geometries = {to_shape(stop.geometry).wkt for stop in feed.stops}
    matched_stops_df = stops_df[stops_df["geometry_str"].isin(cached_geometries)]
    unmatched_stop_df = stops_df[~stops_df["geometry_str"].isin(cached_geometries)]

    logging.info(
        f"Matched stops: {len(matched_stops_df)} | Unmatched stops: {len(unmatched_stop_df)}"
    )

    df_geometry_set = set(matched_stops_df["geometry_str"].tolist())
    geometries_to_delete = cached_geometries - df_geometry_set

    if geometries_to_delete:
        logging.info(f"Deleting {len(geometries_to_delete)} outdated cached stops.")
        db_session.query(Stop).filter(
            Stop.feed_id == feed_id,
            func.ST_AsText(Stop.geometry).in_(list(geometries_to_delete)),
        ).delete(synchronize_session=False)
        db_session.commit()

    matched_geometries = matched_stops_df["geometry"].tolist()
    if not matched_geometries:
        logging.info("No matched geometries found.")
        return feed_id, dict(), unmatched_stop_df
    location_group_counts = (
        db_session.query(
            Osmlocationgroup, func.count(Stop.geometry).label("stop_count")
        )
        .join(Stop, Osmlocationgroup.stops)
        .filter(Stop.feed_id == feed_id, Stop.geometry.in_(matched_geometries))
        .group_by(Osmlocationgroup.group_id)
        .options(joinedload(Osmlocationgroup.osms))
        .all()
    )

    location_groups = {
        group.group_id: GeopolygonAggregate(group, stop_count)
        for group, stop_count in location_group_counts
    }

    logging.info(f"Total location groups retrieved: {len(location_groups)}")
    return feed_id, location_groups, unmatched_stop_df


def extract_location_group(
    feed_id: str, stop_point: WKTElement, db_session: Session
) -> Optional[GeopolygonAggregate]:
    """
    Extract the location group for a given stop point.
    """
    geopolygons = (
        db_session.query(Geopolygon)
        .filter(Geopolygon.geometry.ST_Contains(stop_point))
        .all()
    )

    if len(geopolygons) <= 1:
        logging.warning(
            f"Invalid number of geopolygons for point: {stop_point} -> {geopolygons}"
        )
        return None
    admin_levels = {g.admin_level for g in geopolygons}
    if len(admin_levels) != len(geopolygons):
        logging.warning(
            f"Duplicate admin levels for point: {stop_point} -> {geopolygons}"
        )
        return None

    valid_iso_3166_1 = any(g.iso_3166_1_code for g in geopolygons)
    valid_iso_3166_2 = any(g.iso_3166_2_code for g in geopolygons)
    if not valid_iso_3166_1 or not valid_iso_3166_2:
        logging.warning(f"Invalid ISO codes for point: {stop_point} -> {geopolygons}")
        return

    # Sort the polygons by admin level so that lower levels come first
    geopolygons.sort(key=lambda x: x.admin_level)

    group_id = ".".join([str(g.osm_id) for g in geopolygons])
    group = (
        db_session.query(Osmlocationgroup)
        .filter(Osmlocationgroup.group_id == group_id)
        .one_or_none()
    )
    if not group:
        group = Osmlocationgroup(
            group_id=group_id,
            group_name=", ".join([g.name for g in geopolygons]),
            osms=geopolygons,
        )
    stop = Stop(feed_id=feed_id, geometry=stop_point)
    stop.group = group
    db_session.add(stop)
    logging.info(
        f"Point {stop_point} matched to {', '.join([g.name for g in geopolygons])}"
    )
    return GeopolygonAggregate(group, 1)


def get_or_create_feed_osm_location(
    feed_id: str, location_group: GeopolygonAggregate, db_session: Session
):
    """Get or create the feed osm location group."""
    feed_osm_location = (
        db_session.query(Feedosmlocation)
        .filter(
            Feedosmlocation.feed_id == feed_id,
            Feedosmlocation.group_id == location_group.group_id,
        )
        .one_or_none()
    )
    if not feed_osm_location:
        feed_osm_location = Feedosmlocation(
            feed_id=feed_id,
            group_id=location_group.group_id,
        )
    feed_osm_location.stops_count = location_group.stop_count
    return feed_osm_location


def create_geojson_aggregate(
    location_groups: List[GeopolygonAggregate], total_stops: int, stable_id: str
):
    """Create a GeoJSON object for the location group."""
    geo_polygon_count = dict()
    for group in location_groups:
        if len(group.group_id.split(".")) < 3:
            continue
        highest_admin_level_osm_id = group.group_id.split(".")[-1]
        geo_polygon_count[highest_admin_level_osm_id] = {
            "group": group,
        }

    max_match = max(
        [geo_polygon_count[osm_id]["group"].stop_count for osm_id in geo_polygon_count]
    )
    json_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(
                    geo_polygon_count[osm_id]["group"].highest_admin_geometry()
                ),
                "properties": {
                    "osm_id": osm_id,
                    "country_code": geo_polygon_count[osm_id]["group"].iso_3166_1_code,
                    "subdivision_code": geo_polygon_count[osm_id][
                        "group"
                    ].iso_3166_2_code,
                    "display_name": geo_polygon_count[osm_id][
                        "group"
                    ].get_display_name(),
                    "stops_in_area": geo_polygon_count[osm_id]["group"].stop_count,
                    "stops_in_area_coverage": f"{geo_polygon_count[osm_id]['group'].stop_count / total_stops * 100:.2f}%",
                    "color": generate_color(
                        geo_polygon_count[osm_id]["group"].stop_count, max_match
                    ),
                },
            }
            for osm_id in geo_polygon_count
        ],
    }
    storage_client = storage.Client()
    bucket_name = os.getenv("DATASETS_BUCKET_NAME")
    cors_configuration(bucket_name)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{stable_id}/geolocation.geojson")
    blob.upload_from_string(json.dumps(json_data))
    blob.make_public()
    logging.info(f"GeoJSON data saved to {blob.name}")


def get_or_create_location(
    location_group: GeopolygonAggregate, db_session: Session
) -> Optional[Location]:
    try:
        logging.info(f"Location ID : {location_group.location_id()}")
        location = (
            db_session.query(Location)
            .filter(Location.id == location_group.location_id())
            .one_or_none()
        )
        if not location:
            location = Location(
                id=location_group.location_id(),
                country_code=location_group.iso_3166_1_code,
                country=location_group.country(),
                subdivision_name=location_group.subdivision_name(),
                municipality=location_group.municipality(),
            )
        return location
    except Exception as e:
        logging.error(f"Error creating location: {e}")
        return None


@with_db_session(echo=False)
def extract_location_groups(
    feed_id: str,
    stops_df: pd.DataFrame,
    location_groups: Dict[str, GeopolygonAggregate],
    db_session: Session,
) -> None:
    i = 0
    total_stop_count = len(stops_df)
    for _, stop in stops_df.iterrows():
        i += 1
        logging.info(f"Processing stop {i}/{total_stop_count}")
        location_group = extract_location_group(feed_id, stop["geometry"], db_session)
        if not location_group:
            continue
        if location_group.group_id in location_groups:
            location_groups[location_group.group_id].merge(location_group)
        else:
            location_groups[location_group.group_id] = location_group
        if (
            i % 100 == 0
        ):  # Commit every 100 stops to avoid reprocessing all stops in case of failure
            db_session.commit()

    feed = db_session.query(Feed).filter(Feed.id == feed_id).one_or_none()
    feed.feedosmlocations = [
        get_or_create_feed_osm_location(
            feed_id, location_groups[location_group.group_id], db_session
        )
        for location_group in location_groups.values()
    ]
    feed_locations = []
    for location_group in location_groups.values():
        location = get_or_create_location(location_group, db_session)
        if location:
            feed_locations.append(location)
    if feed_locations:
        feed.locations = feed_locations
    db_session.execute(
        text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {t_feedsearch.name}")
    )


def reverse_geolocation_process(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation population.
    """
    Logger.init_logger()

    # Start overall timing
    overall_start = datetime.now()

    # Parse request parameters
    try:
        parse_start = datetime.now()
        stops_df, stable_id = parse_request_parameters(request)
        stops_df = stops_df[
            stops_df["stop_lat"].notnull() & stops_df["stop_lon"].notnull()
        ]
        stops_df = stops_df.drop_duplicates(subset=["stop_lat", "stop_lon"])
        if stops_df.empty:
            logging.warning("All stops have null lat/lon values.")
            return "All stops have null lat/lon values", ERROR_STATUS_CODE

        total_stops = len(stops_df)
        parse_duration = (datetime.now() - parse_start).total_seconds()
        logging.info(f"Parsed request parameters in {parse_duration:.2f} seconds")
    except ValueError as e:
        logging.error(f"Error parsing request parameters: {e}")
        return str(e), ERROR_STATUS_CODE

    stable_id_filter = StableIdFilter(stable_id)
    logging.getLogger().addFilter(stable_id_filter)

    try:
        # ⏱️ Get Cached Geopolygons
        geo_start = datetime.now()
        feed_id, location_groups, stops_df = get_cached_geopolygons(stable_id, stops_df)
        # Remove duplicate lat/lon points
        geo_duration = (datetime.now() - geo_start).total_seconds()
        logging.info(f"Number of location groups extracted: {len(location_groups)}")
        logging.info(
            f"Time taken to get cached geopolygons: {geo_duration:.2f} seconds"
        )

        # ⏱️ Extract Location Groups
        extract_start = datetime.now()
        extract_location_groups(feed_id, stops_df, location_groups)
        extract_duration = (datetime.now() - extract_start).total_seconds()
        logging.info(
            f"Time taken to extract location groups: {extract_duration:.2f} seconds"
        )

        # ⏱️ Create GeoJSON Aggregate
        geojson_start = datetime.now()
        create_geojson_aggregate(
            list(location_groups.values()), total_stops=total_stops, stable_id=stable_id
        )
        geojson_duration = (datetime.now() - geojson_start).total_seconds()
        logging.info(
            f"Time taken to create GeoJSON aggregate: {geojson_duration:.2f} seconds"
        )

        # ✅ Overall Time
        overall_duration = (datetime.now() - overall_start).total_seconds()
        logging.info(
            f"Total time taken for the process: {overall_duration:.2f} seconds"
        )
        logging.info(
            f"COMPLETED. Processed {total_stops} stops for stable ID {stable_id}. Retrieved "
            f"{len(location_groups)} locations."
        )
        return "Done or wtv", 200

    except Exception as e:
        logging.error(f"Error processing geopolygons: {e}")
        logging.error(traceback.format_exc())  # Log full traceback
        return str(e), ERROR_STATUS_CODE

    finally:
        logging.getLogger().removeFilter(stable_id_filter)
