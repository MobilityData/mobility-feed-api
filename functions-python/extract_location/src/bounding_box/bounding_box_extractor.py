import numpy
from geoalchemy2 import WKTElement

from database_gen.sqlacodegen_models import Gtfsdataset


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
