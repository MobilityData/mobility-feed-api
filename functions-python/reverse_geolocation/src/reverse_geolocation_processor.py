import json
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Tuple, Optional, List

import flask
import pandas as pd
import shapely.geometry
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from google.cloud import storage
from shapely.geometry import mapping
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from location_group_utils import (
    ERROR_STATUS_CODE,
    GeopolygonAggregate,
    generate_color,
    geopolygons_as_string,
)
from parse_request import parse_request_parameters
from shared.database.database import with_db_session, refresh_materialized_view
from shared.database_gen.sqlacodegen_models import (
    Geopolygon,
    Feed,
    Feedlocationgrouppoint,
    Osmlocationgroup,
    Feedosmlocationgroup,
    Location,
    t_feedsearch,
    Gtfsdataset,
    Gtfsfeed,
)
from shared.helpers.logger import get_logger


@with_db_session
def get_cached_geopolygons(
    stable_id: str, stops_df: pd.DataFrame, logger, db_session: Session
) -> Tuple[str, Dict[str, GeopolygonAggregate], pd.DataFrame]:
    """
    Get the geopolygons from the database cache.

    @:returns a tuple containing:
        - feed_id: The ID of the feed.
        - location_groups: A dictionary of location groups with the group ID as the key.
        - unmatched_stop_df: DataFrame of unmatched stops for further processing.
    """
    logger.info("Getting cached geopolygons for stable ID.")

    if stops_df.empty:
        logger.warning("The provided stops DataFrame is empty.")
        raise ValueError("The provided stops DataFrame is empty.")

    stops_df["geometry"] = stops_df.apply(
        lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
        axis=1,
    )
    stops_df["geometry_str"] = stops_df["geometry"].apply(str)

    feed = (
        db_session.query(Feed)
        .options(joinedload(Feed.feedlocationgrouppoints))
        .filter(Feed.stable_id == stable_id)
        .one_or_none()
    )
    if not feed:
        logger.warning("No feed found for stable ID.")
        raise ValueError(f"No feed found for stable ID {stable_id}.")

    feed_id = feed.id

    cached_geometries = {
        to_shape(stop.geometry).wkt for stop in feed.feedlocationgrouppoints
    }
    matched_stops_df = stops_df[stops_df["geometry_str"].isin(cached_geometries)]
    unmatched_stop_df = stops_df[~stops_df["geometry_str"].isin(cached_geometries)]

    logger.info(
        "Matched stops: %s | Unmatched stops: %s",
        len(matched_stops_df),
        len(unmatched_stop_df),
    )

    df_geometry_set = set(matched_stops_df["geometry_str"].tolist())
    geometries_to_delete = cached_geometries - df_geometry_set

    if geometries_to_delete:
        logger.info("Deleting %s outdated cached stops.", len(geometries_to_delete))
        db_session.query(Feedlocationgrouppoint).filter(
            Feedlocationgrouppoint.feed_id == feed_id,
            func.ST_AsText(Feedlocationgrouppoint.geometry).in_(
                list(geometries_to_delete)
            ),
        ).delete(synchronize_session=False)
        db_session.flush()

    matched_geometries = matched_stops_df["geometry"].tolist()
    if not matched_geometries:
        logger.info("No matched geometries found.")
        return feed_id, dict(), unmatched_stop_df
    location_group_counts = (
        db_session.query(
            Osmlocationgroup,
            func.count(Feedlocationgrouppoint.geometry).label("stop_count"),
        )
        .join(Feedlocationgrouppoint, Osmlocationgroup.feedlocationgrouppoints)
        .filter(
            Feedlocationgrouppoint.feed_id == feed_id,
            Feedlocationgrouppoint.geometry.in_(matched_geometries),
        )
        .group_by(Osmlocationgroup.group_id)
        .options(joinedload(Osmlocationgroup.osms))
        .all()
    )

    location_groups = {
        group.group_id: GeopolygonAggregate(group, stop_count)
        for group, stop_count in location_group_counts
    }

    logger.info("Total location groups retrieved: %s", len(location_groups))
    return feed_id, location_groups, unmatched_stop_df


def extract_location_aggregate(
    feed_id: str, stop_point: WKTElement, logger, db_session: Session
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
        logger.warning(
            "Invalid number of geopolygons for point: %s -> %s", stop_point, geopolygons
        )
        return None
    admin_levels = {g.admin_level for g in geopolygons}
    if len(admin_levels) != len(geopolygons):
        logger.warning(
            "Duplicate admin levels for point: %s -> %s",
            stop_point,
            geopolygons_as_string(geopolygons),
        )
        return None

    valid_iso_3166_1 = any(g.iso_3166_1_code for g in geopolygons)
    valid_iso_3166_2 = any(g.iso_3166_2_code for g in geopolygons)
    if not valid_iso_3166_1 or not valid_iso_3166_2:
        logger.warning(
            "Invalid ISO codes for point: %s -> %s",
            stop_point,
            geopolygons_as_string(geopolygons),
        )
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
        db_session.add(group)
        db_session.flush() # Ensure the group is added before using it
    stop = (
        db_session.query(Feedlocationgrouppoint)
        .filter(
            Feedlocationgrouppoint.feed_id == feed_id,
            Feedlocationgrouppoint.geometry == stop_point,
        )
        .one_or_none()
    )
    if not stop:
        stop = Feedlocationgrouppoint(
            feed_id=feed_id,
            geometry=stop_point,
        )
        db_session.add(stop)
    stop.group = group
    logger.info(
        "Point %s matched to %s", stop_point, ", ".join([g.name for g in geopolygons])
    )
    return GeopolygonAggregate(group, 1)


def get_or_create_feed_osm_location_group(
    feed_id: str, location_aggregate: GeopolygonAggregate, db_session: Session
) -> Feedosmlocationgroup:
    """Get or create the feed osm location group."""
    feed_osm_location = (
        db_session.query(Feedosmlocationgroup)
        .filter(
            Feedosmlocationgroup.feed_id == feed_id,
            Feedosmlocationgroup.group_id == location_aggregate.group_id,
        )
        .one_or_none()
    )
    if not feed_osm_location:
        feed_osm_location = Feedosmlocationgroup(
            feed_id=feed_id,
            group_id=location_aggregate.group_id,
        )
    feed_osm_location.stops_count = location_aggregate.stop_count
    return feed_osm_location


def create_geojson_aggregate(
    location_groups: List[GeopolygonAggregate],
    total_stops: int,
    stable_id: str,
    bounding_box: shapely.Polygon,
    data_type: str,
    logger,
    extraction_urls: List[str] = None,
) -> None:
    """Create a GeoJSON file with the aggregated locations. This file will be uploaded to GCS and used for
    visualization."""
    geo_polygon_count = dict()
    for group in location_groups:
        highest_admin_geometry = group.highest_admin_geometry()

        # Clip the geometry using intersection with the bounding box
        clipped_geometry = highest_admin_geometry.intersection(bounding_box)

        highest_admin_level_osm_id = group.group_id.split(".")[-1]
        geo_polygon_count[highest_admin_level_osm_id] = {
            "group": group,
            "clipped_geometry": clipped_geometry,
        }

    max_match = max(
        [geo_polygon_count[osm_id]["group"].stop_count for osm_id in geo_polygon_count]
    )
    json_data = {
        "type": "FeatureCollection",
        "extracted_at": datetime.now().isoformat(),
        "extraction_url": extraction_urls,
        "features": [
            {
                "type": "Feature",
                "geometry": mapping(geo_polygon_count[osm_id]["clipped_geometry"]),
                "properties": {
                    "osm_id": osm_id,
                    "country_code": geo_polygon_count[osm_id]["group"].iso_3166_1_code,
                    "subdivision_code": geo_polygon_count[osm_id][
                        "group"
                    ].iso_3166_2_code,
                    "display_name": geo_polygon_count[osm_id]["group"].display_name(),
                    "stops_in_area": geo_polygon_count[osm_id]["group"].stop_count,
                    "stops_in_area_coverage": f"{geo_polygon_count[osm_id]['group'].stop_count / total_stops * 100:.2f}"
                    f"%",
                    "color": generate_color(
                        geo_polygon_count[osm_id]["group"].stop_count, max_match
                    ),
                },
            }
            for osm_id in geo_polygon_count
        ],
    }
    storage_client = storage.Client()
    if data_type == "gtfs":
        bucket_name = os.getenv("DATASETS_BUCKET_NAME_GTFS")
    elif data_type == "gbfs":
        bucket_name = os.getenv("DATASETS_BUCKET_NAME_GBFS")
    else:
        raise ValueError("The data type must be either 'gtfs' or 'gbfs'.")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{stable_id}/geolocation.geojson")
    blob.upload_from_string(json.dumps(json_data))
    blob.make_public()
    logger.info("GeoJSON data saved to %s", blob.name)


def get_or_create_location(
    location_group: GeopolygonAggregate, logger, db_session: Session
) -> Optional[Location]:
    """Get or create the Location entity."""
    try:
        logger.info("Location ID : %s", location_group.location_id())
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
        logger.error("Error creating location: %s", e)
        return None


@with_db_session
def extract_location_aggregates(
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
    for _, stop in stops_df.iterrows():
        i += 1
        logger.info("Processing stop %s/%s", i, total_stop_count)
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
            i % 100 == 0
        ):  # Commit every 100 stops to avoid reprocessing all stops in case of failure
            db_session.commit()

    feed = db_session.query(Feed).filter(Feed.id == feed_id).one_or_none()
    osm_location_groups = [
        get_or_create_feed_osm_location_group(
            feed_id, location_aggregates[location_group.group_id], db_session
        )
        for location_group in location_aggregates.values()
    ]
    feed.feedosmlocationgroups.clear()
    feed.feedosmlocationgroups.extend(osm_location_groups)
    feed_locations = []
    for location_aggregate in location_aggregates.values():
        location = get_or_create_location(location_aggregate, logger, db_session)
        if location:
            feed_locations.append(location)

    if feed.data_type == "gtfs":
        gtfs_feed = db_session.query(Gtfsfeed).filter(Feed.id == feed_id).one_or_none()
        for gtfs_rt_feed in gtfs_feed.gtfs_rt_feeds:
            logger.info(
                "Updating GTFS-RT feed with stable ID %s", gtfs_rt_feed.stable_id
            )
            gtfs_rt_feed.feedosmlocationgroups.clear()
            gtfs_rt_feed.feedosmlocationgroups.extend(osm_location_groups)
            if feed_locations:
                gtfs_rt_feed.locations.clear()
                gtfs_rt_feed.locations = feed_locations

    if feed_locations:
        feed.locations = feed_locations

    # Commit the changes to the database before refreshing the materialized view
    db_session.commit()
    refresh_materialized_view(db_session, t_feedsearch.name)


@with_db_session
def update_dataset_bounding_box(
    dataset_id: str, stops_df: pd.DataFrame, db_session: Session
) -> shapely.Polygon:
    """
    Update the bounding box of the dataset using the stops DataFrame.
    @:returns The bounding box as a shapely Polygon.
    """
    lat_min, lat_max = stops_df["stop_lat"].min(), stops_df["stop_lat"].max()
    lon_min, lon_max = stops_df["stop_lon"].min(), stops_df["stop_lon"].max()
    bounding_box = WKTElement(
        f"POLYGON(("
        f"{lon_min} {lat_min},"
        f"{lon_max} {lat_min},"
        f"{lon_max} {lat_max},"
        f"{lon_min} {lat_max},"
        f"{lon_min} {lat_min})"
        f")",
        srid=4326,
    )
    if not dataset_id:
        return to_shape(bounding_box)
    gtfs_dataset = (
        db_session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if not gtfs_dataset:
        raise ValueError(f"Dataset {dataset_id} does not exist in the database.")
    gtfs_dataset.bounding_box = bounding_box
    return to_shape(bounding_box)


def reverse_geolocation_process(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation processing.
    """
    overall_start = datetime.now()

    try:
        # Parse request parameters
        (
            stops_df,
            stable_id,
            dataset_id,
            data_type,
            extraction_urls,
        ) = parse_request_parameters(request)

        # Remove duplicate lat/lon points
        stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
        stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
        stops_df = stops_df[
            stops_df["stop_lat"].notnull() & stops_df["stop_lon"].notnull()
        ]
        stops_df = stops_df.drop_duplicates(subset=["stop_lat", "stop_lon"])
        if stops_df.empty:
            logging.warning("All stops have null lat/lon values.")
            return "All stops have null lat/lon values", ERROR_STATUS_CODE
        total_stops = len(stops_df)
    except ValueError as e:
        logging.error(f"Error parsing request parameters: {e}")
        return str(e), ERROR_STATUS_CODE

    logger = get_logger(__name__, stable_id)

    try:
        # Update the bounding box of the dataset
        bounding_box = update_dataset_bounding_box(dataset_id, stops_df)

        # Get Cached Geopolygons
        feed_id, location_groups, stops_df = get_cached_geopolygons(
            stable_id, stops_df, logger
        )
        logger.info("Number of location groups extracted: %s", len(location_groups))

        # Extract Location Groups
        extract_location_aggregates(feed_id, stops_df, location_groups, logger)

        # Create GeoJSON Aggregate
        create_geojson_aggregate(
            list(location_groups.values()),
            total_stops=total_stops,
            stable_id=stable_id,
            bounding_box=bounding_box,
            data_type=data_type,
            extraction_urls=extraction_urls,
            logger=logger,
        )

        # Overall Time
        overall_duration = (datetime.now() - overall_start).total_seconds()
        logger.info(f"Total time taken for the process: {overall_duration:.2f} seconds")
        logger.info(
            "COMPLETED. Processed %s stops for stable ID %s. Retrieved %s locations.",
            total_stops,
            stable_id,
            len(location_groups),
        )
        return (
            f"Processed {total_stops} stops for stable ID {stable_id}. Retrieved {len(location_groups)} locations.",
            200,
        )

    except Exception as e:
        logger = logger if logger else logging
        logger.error("Error processing geopolygons: %s", e)
        logger.error(traceback.format_exc())  # Log full traceback
        return str(e), ERROR_STATUS_CODE
