import os

import functions_framework
import gtfs_kit
from cloudevents.http import CloudEvent

# from database_gen.sqlacodegen_models import Gtfsdataset
from helpers.database import start_db_session
from geoalchemy2 import WKTElement


# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def extract_bounding_box(cloud_event: CloudEvent) -> str:
    """This function is triggered by a change in a storage bucket.

    Args:
        cloud_event: The CloudEvent that triggered this function.
    Returns:
        The event ID, event type, bucket, name, metageneration, and timeCreated.
    """
    data = cloud_event.data
    print(f"data: {data}")
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split('/')[-3]
    dataset_id = resource_name.split('/')[-2]
    file_name = resource_name.split('/')[-1]
    bucket_name = data["resource"]["labels"]["bucket_name"]
    url = f"https://storage.googleapis.com/{bucket_name}/{stable_id}/{dataset_id}/{file_name}"
    print(f"url: {url}")

    feed = gtfs_kit.read_feed(url, 'km')
    min_longitude, min_latitude, max_longitude, max_latitude = feed.compute_bounds()

    points = [
        (min_longitude, min_latitude),  # Bottom-left
        (min_longitude, max_latitude),  # Top-left
        (max_longitude, max_latitude),  # Top-right
        (max_longitude, min_latitude),  # Bottom-right
        (min_longitude, min_latitude)  # Back to Bottom-left
    ]
    wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in points)}))"
    geometry_polygon = WKTElement(wkt_polygon, srid=4326)

    print(f"min_longitude: {min_longitude}, min_latitude: {min_latitude}")
    session = None
    # try:
    #
    #     session = start_db_session(os.getenv("FEEDS_DATABASE_URL"))
    #     dataset: Gtfsdataset | None = (
    #         session.query(Gtfsdataset)
    #         .filter_by(Gtfsdataset.stable_id == dataset_id)
    #         .one_or_none()
    #     )
    #     if dataset is None:
    #         raise Exception(f"Dataset {dataset_id} does not exist in the database.")
    #     dataset.bounding_box = geometry_polygon
    #     session.add(dataset)
    #     session.commit()
    # except Exception as e:
    #     if session is not None:
    #         session.rollback()
    #     raise e
    # finally:
    #     if session is not None:
    #         session.close()
    return 'Yup'
