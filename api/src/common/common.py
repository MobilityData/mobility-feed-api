from geoalchemy2 import WKTElement
from sqlalchemy import or_
from sqlalchemy.orm import Query
from sqlalchemy.orm.strategy_options import _AbstractLoad, joinedload

from common.error_handling import (
    invalid_bounding_coordinates,
    invalid_bounding_method,
    raise_internal_http_validation_error,
)
from database_gen.sqlacodegen_models import Gtfsdataset, Feed


def get_joinedload_options() -> [_AbstractLoad]:
    """Returns common joinedload options for feeds queries."""
    return [joinedload(Feed.locations), joinedload(Feed.externalids), joinedload(Feed.redirectingids)]


def apply_bounding_filtering(
    query: Query,
    bounding_latitudes: str,
    bounding_longitudes: str,
    bounding_filter_method: str,
) -> Query:
    """Create a new query based on the bounding parameters."""

    if not bounding_latitudes or not bounding_longitudes or not bounding_filter_method:
        return query

    if (
        len(bounding_latitudes_tokens := bounding_latitudes.split(",")) != 2
        or len(bounding_longitudes_tokens := bounding_longitudes.split(",")) != 2
    ):
        raise_internal_http_validation_error(
            invalid_bounding_coordinates.format(bounding_latitudes, bounding_longitudes)
        )
    min_latitude, max_latitude = bounding_latitudes_tokens
    min_longitude, max_longitude = bounding_longitudes_tokens
    try:
        min_latitude = float(min_latitude)
        max_latitude = float(max_latitude)
        min_longitude = float(min_longitude)
        max_longitude = float(max_longitude)
    except ValueError:
        raise_internal_http_validation_error(
            invalid_bounding_coordinates.format(bounding_latitudes, bounding_longitudes)
        )

    points = [
        (min_longitude, min_latitude),
        (min_longitude, max_latitude),
        (max_longitude, max_latitude),
        (max_longitude, min_latitude),
        (min_longitude, min_latitude),
    ]
    wkt_polygon = f"POLYGON(({', '.join(f'{lon} {lat}' for lon, lat in points)}))"
    bounding_box = WKTElement(
        wkt_polygon,
        srid=Gtfsdataset.bounding_box.type.srid,
    )

    if bounding_filter_method == "partially_enclosed":
        return query.filter(
            or_(
                Gtfsdataset.bounding_box.ST_Overlaps(bounding_box),
                Gtfsdataset.bounding_box.ST_Contains(bounding_box),
            )
        )
    elif bounding_filter_method == "completely_enclosed":
        return query.filter(bounding_box.ST_Covers(Gtfsdataset.bounding_box))
    elif bounding_filter_method == "disjoint":
        return query.filter(Gtfsdataset.bounding_box.ST_Disjoint(bounding_box))
    else:
        raise raise_internal_http_validation_error(invalid_bounding_method.format(bounding_filter_method))
