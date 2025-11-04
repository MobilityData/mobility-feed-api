from enum import Enum
from typing import Dict, Optional

from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from geoalchemy2.types import Geography

from shared.database_gen.sqlacodegen_models import Feed, Geopolygon
import logging


class ReverseGeocodingStrategy(str, Enum):
    """
    Enum for reverse geocoding strategies.
    """

    # Per point strategy uses point-in-polygon to find the location for each point
    # It queries the database for each point, which can be slow for large datasets
    PER_POINT = "per-point"

    # Per polygon strategy uses point-in-polygon to find the location for each point
    # It queries the database for each polygon, which can be faster for large datasets
    PER_POLYGON = "per-polygon"


def get_country_code(country_name: str) -> Optional[str]:
    """
    Get ISO 3166 country code from country name

    Args:
        country_name (str): Full country name

    Returns:
        Optional[str]: Two-letter ISO country code or None if not found
    """
    import pycountry

    # Return None for empty or whitespace-only strings
    if not country_name or not country_name.strip():
        logging.error("Could not find country code for: empty string")
        return None

    try:
        # Try exact match first
        country = pycountry.countries.get(name=country_name)
        if country:
            return country.alpha_2

        # Try searching with fuzzy matching
        countries = pycountry.countries.search_fuzzy(country_name)
        if countries:
            return countries[0].alpha_2

    except LookupError:
        logging.error(f"Could not find country code for: {country_name}")
    return None


def translate_feed_locations(feed: Feed, location_translations: Dict):
    """
    Translate the locations of a feed.

    Args:
        feed: The feed object
        location_translations: The location translations
    """
    for location in feed.locations:
        location_translation = location_translations.get(location.id)

        if location_translation:
            location.subdivision_name = (
                location_translation["subdivision_name_translation"]
                if location_translation["subdivision_name_translation"]
                else location.subdivision_name
            )
            location.municipality = (
                location_translation["municipality_translation"]
                if location_translation["municipality_translation"]
                else location.municipality
            )
            location.country = (
                location_translation["country_translation"]
                if location_translation["country_translation"]
                else location.country
            )


def to_shapely(g):
    """
    Convert a GeoAlchemy WKB/WKT element or WKT string into a Shapely geometry.
    If it's already a Shapely geometry, return it as-is.
    """
    # Import here to avoid adding unnecessary dependencies if not used to GCP functions
    from shapely import wkt as shapely_wkt
    from geoalchemy2 import WKTElement, WKBElement
    from geoalchemy2.shape import to_shape

    if isinstance(g, WKBElement):
        return to_shape(g)
    if isinstance(g, WKTElement):
        return shapely_wkt.loads(g.data)
    if isinstance(g, str):
        # assume WKT
        return shapely_wkt.loads(g)
    return g  # assume already shapely


def select_highest_level_polygon(geopolygons: list[Geopolygon]) -> Optional[Geopolygon]:
    """
    Select the geopolygon with the highest admin_level from a list of geopolygons.
    Admin levels are compared, with NULL treated as the lowest priority.
    """
    if not geopolygons:
        return None
    # Treat NULL admin_level as the lowest priority
    return max(
        geopolygons, key=lambda g: (-1 if g.admin_level is None else g.admin_level)
    )


def select_lowest_level_polygon(geopolygons: list[Geopolygon]) -> Optional[Geopolygon]:
    """
    Select the geopolygon with the lowest admin_level from a list of geopolygons.
    Admin levels are compared, with NULL treated as the lowest priority.
    """
    if not geopolygons:
        return None
    # Treat NULL admin_level as the lowest priority
    return min(
        geopolygons, key=lambda g: (100 if g.admin_level is None else g.admin_level)
    )


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
    country_polygons = [g for g in geopolygons if g.iso_3166_1_code]
    if not country_polygons:
        return None

    # Prefer the one with the lowest admin_level (most local)
    lowest_admin_level_polygon = select_lowest_level_polygon(country_polygons)
    return lowest_admin_level_polygon.iso_3166_1_code


def get_geopolygons_covers(stop_point: WKTElement, db_session: Session):
    """
    Get all geopolygons that cover a given point using BigQuery-compatible semantics.
    """
    # BigQuery-compatible point-in-polygon (geodesic + border-inclusive)
    geopolygons = (
        db_session.query(Geopolygon)
        # optional prefilter to use your GiST index on geometry (fast)
        .filter(func.ST_Intersects(Geopolygon.geometry, stop_point))
        # exact check matching BigQuery's GEOGRAPHY semantics
        .filter(
            func.ST_Covers(
                cast(Geopolygon.geometry, Geography(srid=4326)),
                cast(stop_point, Geography(srid=4326)),
            )
        ).all()
    )
    return geopolygons


def round_geojson_coords(geometry, precision=5):
    """
    Recursively round all coordinates in a GeoJSON geometry to the given precision.
    Handles Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection.
    """
    geom_type = geometry.get("type")
    if geom_type == "GeometryCollection":
        return {
            "type": "GeometryCollection",
            "geometries": [
                round_geojson_coords(g, precision)
                for g in geometry.get("geometries", [])
            ],
        }
    elif "coordinates" in geometry:
        return {
            **geometry,
            "coordinates": round_coords(geometry["coordinates"], precision),
        }
    else:
        return geometry


def round_coords(coords, precision):
    """
    Recursively round coordinates to the given precision.
    Handles nested lists of coordinates.
    Args:
        coords: A coordinate or list of coordinates (can be nested)
        precision: Number of decimal places to round to
    Returns:
        Rounded coordinates with the same structure as input
    """
    if isinstance(coords, (list, tuple)):
        if coords and isinstance(coords[0], (list, tuple)):
            return [round_coords(c, precision) for c in coords]
        else:
            result = []
            for c in coords:
                if isinstance(c, (int, float)):
                    result.append(round(float(c), precision))
                else:
                    result.append(c)
            return result
    return coords
