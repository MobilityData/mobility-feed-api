import json
import logging
import os
import traceback
from datetime import datetime
from logging import Logger
from typing import Dict, Tuple, List

import flask
import pandas as pd
import shapely.geometry
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape

from shapely.geometry import mapping
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from location_group_utils import (
    ERROR_STATUS_CODE,
    GeopolygonAggregate,
    generate_color,
    get_or_create_feed_osm_location_group,
    get_or_create_location,
)
from parse_request import parse_request_parameters
from shared.common.gcp_utils import create_refresh_materialized_view_task
from shared.database.database import with_db_session, get_db_timestamp
from shared.database_gen.sqlacodegen_models import (
    Feed,
    Feedlocationgrouppoint,
    Osmlocationgroup,
    Gtfsdataset,
    Gtfsfeed,
    Gbfsfeed,
)
from shared.dataset_service.dataset_service_commons import Status

from shared.helpers.locations import ReverseGeocodingStrategy, round_geojson_coords
from shared.helpers.logger import get_logger
from shared.helpers.runtime_metrics import track_metrics
from shared.helpers.utils import (
    check_maximum_executions,
    get_execution_id,
    record_execution_trace,
)
from strategy_extraction_per_point import extract_location_aggregates_per_point
from strategy_extraction_per_polygon import extract_location_aggregates_per_polygon


@with_db_session
def get_geopolygons_with_geometry(
    feed: Feed,
    stops_df: pd.DataFrame,
    use_cache: bool,
    logger: Logger,
    db_session: Session,
) -> Tuple[str, Dict[str, GeopolygonAggregate], pd.DataFrame]:
    """


    @:returns a tuple containing:
        - feed_id: The ID of the feed.
        - location_groups: A dictionary of location groups with the group ID as the key.
        - unmatched_stop_df: DataFrame of unmatched stops with geo
    """
    logger.info("Getting cached geopolygons for stable ID.")
    stops_df["geometry"] = stops_df.apply(
        lambda x: WKTElement(f"POINT ({x['stop_lon']} {x['stop_lat']})", srid=4326),
        axis=1,
    )
    stops_df["geometry_str"] = stops_df["geometry"].apply(str)

    cached_geometries = {
        to_shape(stop.geometry).wkt for stop in feed.feedlocationgrouppoints
    }
    matched_stops_df = (
        stops_df[stops_df["geometry_str"].isin(cached_geometries)]
        if use_cache
        else pd.DataFrame(columns=stops_df.columns)
    )
    unmatched_stop_df = (
        stops_df[~stops_df["geometry_str"].isin(cached_geometries)]
        if use_cache
        else stops_df
    )
    logger.info(
        "Matched stops: %s | Unmatched stops: %s",
        len(matched_stops_df),
        len(unmatched_stop_df),
    )
    if use_cache:
        df_geometry_set = set(matched_stops_df["geometry_str"].tolist())
        geometries_to_delete = cached_geometries - df_geometry_set
        if geometries_to_delete:
            clean_stop_cache(db_session, feed, geometries_to_delete, logger)

    matched_geometries = matched_stops_df["geometry"].tolist()
    if not matched_geometries:
        logger.info("No matched geometries found.")
        return dict(), unmatched_stop_df
    location_group_counts = (
        db_session.query(
            Osmlocationgroup,
            func.count(Feedlocationgrouppoint.geometry).label("stop_count"),
        )
        .join(Feedlocationgrouppoint, Osmlocationgroup.feedlocationgrouppoints)
        .filter(
            Feedlocationgrouppoint.feed_id == feed.id,
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
    return location_groups, unmatched_stop_df


@track_metrics(metrics=("time", "memory", "cpu"))
def clean_stop_cache(db_session, feed, geometries_to_delete, logger):
    """Clean the stop cache by deleting outdated cached stops."""
    logger.info("Deleting %s outdated cached stops.", len(geometries_to_delete))
    db_session.query(Feedlocationgrouppoint).filter(
        Feedlocationgrouppoint.feed_id == feed.id,
        func.ST_AsText(Feedlocationgrouppoint.geometry).in_(list(geometries_to_delete)),
    ).delete(synchronize_session=False)
    db_session.commit()


@with_db_session
def create_geojson_aggregate(
    location_groups: List[GeopolygonAggregate],
    total_stops: int,
    bounding_box: shapely.Polygon,
    data_type: str,
    logger,
    feed: Gtfsfeed | Gbfsfeed,
    gtfs_dataset: Gtfsdataset = None,
    extraction_urls: List[str] = None,
    public: bool = True,
    db_session: Session = None,
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
                "geometry": round_geojson_coords(
                    mapping(geo_polygon_count[osm_id]["clipped_geometry"])
                ),
                "properties": {
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
    storage_client = get_storage_client()
    if data_type == "gtfs":
        bucket_name = os.getenv("DATASETS_BUCKET_NAME_GTFS")
    elif data_type == "gbfs":
        bucket_name = os.getenv("DATASETS_BUCKET_NAME_GBFS")
    else:
        raise ValueError("The data type must be either 'gtfs' or 'gbfs'.")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{feed.stable_id}/geolocation.geojson")
    blob.upload_from_string(json.dumps(json_data))
    if public:
        blob.make_public()
    feed.geolocation_file_created_date = get_db_timestamp(db_session)
    if gtfs_dataset:
        feed.geolocation_file_dataset = gtfs_dataset
    logger.info("GeoJSON data saved to %s", blob.name)


def get_storage_client():
    from google.cloud import storage

    return storage.Client()


@track_metrics(metrics=("time", "memory", "cpu"))
def update_dataset_bounding_box(
    feed: Gtfsfeed | Gbfsfeed,
    gtfs_dataset: Gtfsdataset,
    stops_df: pd.DataFrame,
    db_session: Session,
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
    if feed.data_type == "gtfs":
        if not gtfs_dataset:
            return to_shape(bounding_box)
        feed.bounding_box = bounding_box
        feed.bounding_box_dataset = gtfs_dataset
        gtfs_dataset.bounding_box = bounding_box
    elif feed.data_type == "gbfs":
        feed.bounding_box = bounding_box
        feed.bounding_box_generated_at = get_db_timestamp(db_session)
    else:
        raise ValueError("The data type must be either 'gtfs' or 'gbfs'.")

    return to_shape(bounding_box)


def load_dataset(dataset_id: str, db_session: Session) -> Gtfsdataset:
    gtfs_dataset = (
        db_session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if not gtfs_dataset:
        raise ValueError(
            f"Dataset with ID {dataset_id} does not exist in the database."
        )
    return gtfs_dataset


@with_db_session()
def reverse_geolocation_process(
    request: flask.Request, db_session: Session = None
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation processing.
    @:request: Flask request object containing the parameters for the reverse geolocation process.
    Example request JSON(GTFS):
    {
        "stable_id": "example_stable_id",
        "dataset_id": "example_dataset_id",
        "stops_url": "https://example.com/path/to/stops.csv",
        "data_type": "gtfs",
        "strategy": "per-point"
    }
    Example request JSON(GBFS):
    {
        "stable_id": "example_stable_id",
        "dataset_id": "example_dataset_id",
        "station_information_url": "https://example.com/path/to/station_information.json",
        "vehicle_status_url": "https://example.com/path/to/vehicle_status.json",
        "free_bike_status_url": "https://example.com/path/to/free_bike_status.json",
        "strategy": "per-point"
    }
    @:returns: A tuple containing a message and the HTTP status code.

    """
    try:
        # Parse request parameters
        (
            stops_df,
            stable_id,
            dataset_id,
            data_type,
            extraction_urls,
            public,
            strategy,
            use_cache,
            maximum_executions,
        ) = parse_request_parameters(request)

        logger = get_logger(__name__, stable_id)

        # Check for maximum executions to avoid repeated processing during the same day
        request_json = request.get_json(silent=True)
        execution_id = get_execution_id(request_json, stable_id)
        max_execution_error = check_maximum_executions(
            execution_id, stable_id, logger, maximum_executions
        )
        if max_execution_error:
            logger.warning(max_execution_error)
            return max_execution_error, ERROR_STATUS_CODE

        record_execution_trace(
            execution_id=execution_id,
            stable_id=stable_id,
            status=Status.PROCESSING,
            logger=logger,
            dataset_file=None,
            error_message=None,
        )
        # Remove duplicate lat/lon points
        stops_df["stop_lat"] = pd.to_numeric(stops_df["stop_lat"], errors="coerce")
        stops_df["stop_lon"] = pd.to_numeric(stops_df["stop_lon"], errors="coerce")
        stops_df = stops_df[
            stops_df["stop_lat"].notnull() & stops_df["stop_lon"].notnull()
        ]
        stops_df = stops_df.drop_duplicates(subset=["stop_lat", "stop_lon"])
        total_stops = len(stops_df)
    except ValueError as e:
        logging.error("Error parsing request parameters: %s", e)
        return str(e), ERROR_STATUS_CODE

    if stops_df.empty:
        no_stops_message = "No stops found in the feed."
        logger.warning(no_stops_message)
        return str(no_stops_message), ERROR_STATUS_CODE

    try:
        # Update the bounding box of the dataset
        gtfs_dataset: Gtfsdataset = None
        if dataset_id:
            gtfs_dataset = load_dataset(dataset_id, db_session)
        feed = load_feed(stable_id, data_type, logger, db_session)

        bounding_box = update_dataset_bounding_box(
            feed=feed,
            gtfs_dataset=gtfs_dataset,
            stops_df=stops_df,
            db_session=db_session,
        )

        location_groups = reverse_geolocation(
            strategy=strategy,
            stable_id=stable_id,
            stops_df=stops_df,
            data_type=data_type,
            logger=logger,
            use_cache=use_cache,
            db_session=db_session,
        )

        if not location_groups:
            no_locations_message = "No locations found for the provided stops."
            logger.warning(no_locations_message)
            record_execution_trace(
                execution_id=execution_id,
                stable_id=stable_id,
                status=Status.FAILED,
                logger=logger,
                dataset_file=None,
                error_message=no_locations_message,
            )
            return no_locations_message, ERROR_STATUS_CODE

        # Create GeoJSON Aggregate
        create_geojson_aggregate(
            list(location_groups.values()),
            total_stops=total_stops,
            bounding_box=bounding_box,
            data_type=data_type,
            extraction_urls=extraction_urls,
            logger=logger,
            public=public,
            feed=feed,
            gtfs_dataset=gtfs_dataset,
            db_session=db_session,
        )

        # Commit the changes to the database
        db_session.commit()
        create_refresh_materialized_view_task()
        logger.info(
            "COMPLETED. Processed %s stops for stable ID %s with strategy. "
            "Retrieved %s locations.",
            len(stops_df),
            stable_id,
            len(location_groups),
        )
        record_execution_trace(
            execution_id=execution_id,
            stable_id=stable_id,
            status=Status.SUCCESS,
            logger=logger,
            dataset_file=None,
            error_message=None,
        )
        return (
            f"Processed {total_stops} stops for stable ID {stable_id}. "
            f"Retrieved {len(location_groups)} locations.",
            200,
        )

    except Exception as e:
        logger = logger if logger else logging
        logger.error("Error processing geopolygons: %s", e)
        logger.error(traceback.format_exc())  # Log full traceback
        record_execution_trace(
            execution_id=execution_id,
            stable_id=stable_id,
            status=Status.FAILED,
            logger=logger,
            dataset_file=None,
            error_message=str(e),
        )
        return str(e), ERROR_STATUS_CODE


@with_db_session
@track_metrics(metrics=("time", "memory", "cpu"))
def reverse_geolocation(
    strategy,
    stable_id,
    stops_df,
    data_type,
    logger,
    use_cache,
    db_session: Session = None,
):
    """
    Reverse geolocation processing based on the specified strategy.
    """
    logger.info("Processing geopolygons with strategy: %s.", strategy)

    feed = load_feed(stable_id, data_type, logger, db_session)

    # Get Geopolygons with Geometry and cached location groups
    cache_location_groups, unmatched_stops_df = get_geopolygons_with_geometry(
        feed=feed, stops_df=stops_df, use_cache=use_cache, logger=logger
    )
    logger.info("Number of location groups cached: %s", len(cache_location_groups))
    if len(unmatched_stops_df) > 0:
        # Extract Location Groups
        match strategy:
            case ReverseGeocodingStrategy.PER_POINT:
                extract_location_aggregates_per_point(
                    feed=feed,
                    stops_df=unmatched_stops_df,
                    location_aggregates=cache_location_groups,
                    use_cache=use_cache,
                    logger=logger,
                )
            case ReverseGeocodingStrategy.PER_POLYGON:
                extract_location_aggregates_per_polygon(
                    feed=feed,
                    stops_df=unmatched_stops_df,
                    location_aggregates=cache_location_groups,
                    use_cache=use_cache,
                    logger=logger,
                )
            case _:
                logger.error("Invalid strategy: %s", strategy)
                return f"Invalid strategy: {strategy}", ERROR_STATUS_CODE

    update_feed_location(
        cache_location_groups=cache_location_groups,
        feed=feed,
        logger=logger,
        db_session=db_session,
    )
    return cache_location_groups


def load_feed(stable_id, data_type, logger, db_session) -> Gtfsfeed | Gbfsfeed:
    """Load feed from the database using the stable ID and data type."""
    feed = (
        db_session.query(Gbfsfeed if data_type == "gbfs" else Gtfsfeed)
        .options(joinedload(Feed.feedlocationgrouppoints))
        .filter(Feed.stable_id == stable_id)
        .one_or_none()
    )
    if not feed:
        logger.warning("No feed found for stable ID.")
        raise ValueError(f"No feed found for stable ID {stable_id}.")
    return feed


@track_metrics(metrics=("time", "memory", "cpu"))
def update_feed_location(
    cache_location_groups: Dict[str, GeopolygonAggregate],
    feed: Feed,
    logger: Logger,
    db_session: Session,
):
    osm_location_groups = [
        get_or_create_feed_osm_location_group(
            feed.id, cache_location_groups[location_group.group_id], db_session
        )
        for location_group in cache_location_groups.values()
    ]
    feed.feedosmlocationgroups.clear()
    feed.feedosmlocationgroups.extend(osm_location_groups)
    feed_locations = []
    # The location_ids set is used to avoid duplicates when creating locations.
    # Fixes: https://github.com/MobilityData/mobility-feed-api/issues/1289
    location_ids = set()
    for location_aggregate in cache_location_groups.values():
        location = get_or_create_location(location_aggregate, logger, db_session)
        if location:
            if location.id not in location_ids:
                feed_locations.append(location)
            location_ids.add(location.id)
    if feed.data_type == "gtfs":
        gtfs_feed = db_session.query(Gtfsfeed).filter(Feed.id == feed.id).one_or_none()
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
