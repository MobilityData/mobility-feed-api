import os
import logging

import functions_framework
import gtfs_kit
import numpy
from cloudevents.http import CloudEvent
from geoalchemy2 import WKTElement

from database_gen.sqlacodegen_models import Gtfsdataset
from helpers.database import start_db_session
from helpers.logger import Logger

logging.basicConfig(level=logging.INFO)


def parse_resource_data(data: dict) -> tuple:
    """
    Parse the cloud event data to extract resource information.
    @:param data (dict): The data part of the CloudEvent.
    @:return tuple: A tuple containing stable_id, dataset_id, and the resource URL.
    """
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split("/")[-3]
    dataset_id = resource_name.split("/")[-2]
    file_name = resource_name.split("/")[-1]
    bucket_name = data["resource"]["labels"]["bucket_name"]
    url = f"https://storage.googleapis.com/{bucket_name}/{stable_id}/{dataset_id}/{file_name}"
    return stable_id, dataset_id, url


def get_gtfs_feed_bounds(url: str, dataset_id: str) -> numpy.ndarray:
    """
    Retrieve the bounding box coordinates from the GTFS feed.
    @:param url (str): URL to the GTFS feed.
    @:param dataset_id (str): ID of the dataset for logs
    @:return numpy.ndarray: An array containing the bounds (min_longitude, min_latitude, max_longitude, max_latitude).
    @:raises Exception: If the GTFS feed is invalid
    """
    try:
        feed = gtfs_kit.read_feed(url, "km")
        return feed.compute_bounds()
    except Exception as e:
        print(f"[{dataset_id}] Error retrieving GTFS feed from {url}: {e}")
        raise Exception(e)


def create_polygon_wkt_element(bounds: numpy.ndarray) -> WKTElement:
    """
    Create a WKTElement polygon from bounding box coordinates.
    @:param bounds (numpy.ndarray): Bounding box coordinates.
    @:return WKTElement: The polygon representation of the bounding box.
    """
    min_longitude, min_latitude, max_longitude, max_latitude = bounds
    points = [
        (min_longitude, min_latitude),
        (min_longitude, max_latitude),
        (max_longitude, max_latitude),
        (max_longitude, min_latitude),
        (min_longitude, min_latitude),
    ]
    wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in points)}))"
    return WKTElement(wkt_polygon, srid=4326)


def update_dataset_bounding_box(session, dataset_id, geometry_polygon):
    """
    Update the bounding box of a dataset in the database.
    @:param session (Session): The database session.
    @:param dataset_id (str): The ID of the dataset.
    @:param geometry_polygon (WKTElement): The polygon representing the bounding box.
    @:raises Exception: If the dataset is not found in the database.
    """
    dataset: Gtfsdataset | None = (
        session.query(Gtfsdataset)
        .filter(Gtfsdataset.stable_id == dataset_id)
        .one_or_none()
    )
    if dataset is None:
        raise Exception(f"Dataset {dataset_id} does not exist in the database.")
    dataset.bounding_box = geometry_polygon
    session.add(dataset)
    session.commit()


@functions_framework.cloud_event
def extract_bounding_box(cloud_event: CloudEvent) -> None:
    """
    Main function triggered by a GTFS dataset upload to extract and update the bounding box in the database.
    @:param cloud_event (CloudEvent): The CloudEvent that triggered this function.
    """
    Logger.init_logger()
    data = cloud_event.data
    logging.info(f"Function Triggered with event data: {data}")

    stable_id, dataset_id, url = parse_resource_data(data)
    logging.info(f"[{dataset_id}] accessing url: {url}")

    bounds = get_gtfs_feed_bounds(url, dataset_id)
    logging.info(f"[{dataset_id}] extracted bounding = {bounds}")

    geometry_polygon = create_polygon_wkt_element(bounds)

    session = None
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
        update_dataset_bounding_box(session, dataset_id, geometry_polygon)
    except Exception as e:
        logging.error(f"{dataset_id}] Error while processing: {e}")
        if session is not None:
            session.rollback()
        raise e
    finally:
        if session is not None:
            session.close()
    logging.info(f"[{stable_id} - {dataset_id}] Bounding box updated successfully.")
