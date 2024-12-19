import json
import logging
import os
import uuid
from collections import defaultdict
from typing import List, Dict, Tuple

import flask
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely.validation import make_valid
from google.cloud import storage

from database_gen.sqlacodegen_models import Geopolygon
from helpers.database import start_db_session
from helpers.logger import Logger
from common import ERROR_STATUS_CODE

# Initialize logging
logging.basicConfig(level=logging.INFO)


def build_response(
    proper_match_geopolygons: Dict[str, Dict], total_points: int, unmatched_points: int
) -> Dict:
    """Build a structured response from the matched geopolygons."""

    # Helper function to merge and build hierarchical groups
    def merge_hierarchy(root: Dict, geopolygons: List[Geopolygon], count: int) -> None:
        if not geopolygons:
            return

        # Process the current geopolygon
        current = geopolygons[0]
        osm_id = current.osm_id

        # Check if the current node already exists in the root
        if osm_id not in root:
            root[osm_id] = {
                "osm_id": current.osm_id,
                "iso_3166_1": current.iso_3166_1_code,
                "iso_3166_2": current.iso_3166_2_code,
                "name": current.name,
                "admin_level": current.admin_level,
                "points_match": 0,
                "sub_levels": defaultdict(dict),
            }

        # Increment points_match for the current node
        root[osm_id]["points_match"] += count

        # Recursively process the sub-levels
        merge_hierarchy(root[osm_id]["sub_levels"], geopolygons[1:], count)

    # Build the hierarchical response
    grouped_matches = defaultdict(dict)

    for match_data in proper_match_geopolygons.values():
        geopolygons = match_data["geopolys"]
        count = match_data["count"]

        # Merge into the top-level hierarchy
        merge_hierarchy(grouped_matches, geopolygons, count)

    # Recursive function to convert defaultdict to a regular dict and clean sub-levels
    def clean_hierarchy(root: Dict) -> List[Dict]:
        return [
            {
                "osm_id": node["osm_id"],
                "iso_3166_1": node["iso_3166_1"],
                "iso_3166_2": node["iso_3166_2"],
                "name": node["name"],
                "admin_level": node["admin_level"],
                "points_match": node["points_match"],
                "sub_levels": clean_hierarchy(node["sub_levels"])
                if node["sub_levels"]
                else [],
            }
            for node in root.values()
        ]

    # Construct the final response
    response = {
        "summary": {
            "total_points": total_points,
            "matched_points": total_points - unmatched_points,
            "unmatched_points": unmatched_points,
        },
        "grouped_matches": clean_hierarchy(grouped_matches),
    }

    return response


def parse_request_parameters(
    request: flask.Request,
) -> Tuple[List[WKTElement], WKTElement, str]:
    """
    Parse the request parameters and return a list of WKT points and a bounding box.
    """
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    logging.info(f"Request JSON: {request_json}")

    if (
        not request_json
        or "points" not in request_json
        or "execution_id" not in request_json
    ):
        raise ValueError(
            "Invalid request: missing 'points' or 'execution_id' parameter."
        )

    execution_id = str(request_json["execution_id"])
    points = request_json["points"]
    if not points:
        raise ValueError("Invalid request: 'points' parameter is empty.")
    if not isinstance(points, list):
        raise ValueError("Invalid request: 'points' parameter must be a list.")
    if not all(isinstance(lat_lon, list) and len(lat_lon) == 2 for lat_lon in points):
        raise ValueError(
            "Invalid request: 'points' must be a list of lists with two elements each "
            "representing latitude and longitude."
        )

    # Create WKT elements for each point
    wkt_points = [
        WKTElement(f"POINT({point[0]} {point[1]})", srid=4326) for point in points
    ]

    # Generate bounding box
    lons, lats = [point[0] for point in points], [point[1] for point in points]
    bounding_box_coords = [
        (min(lons), min(lats)),
        (max(lons), min(lats)),
        (max(lons), max(lats)),
        (min(lons), max(lats)),
        (min(lons), min(lats)),
    ]
    bounding_box = WKTElement(
        f"POLYGON(({', '.join([f'{lon} {lat}' for lon, lat in bounding_box_coords])}))",
        srid=4326,
    )

    return wkt_points, bounding_box, execution_id


def reverse_geolocation_process(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Main function to handle reverse geolocation population.
    """
    Logger.init_logger()
    bucket_name = os.getenv("BUCKET_NAME")

    # Parse request parameters
    try:
        wkt_points, bounding_box, execution_id = parse_request_parameters(request)
    except ValueError as e:
        logging.error(f"Error parsing request parameters: {e}")
        return str(e), ERROR_STATUS_CODE

    # Start the database session
    try:
        session = start_db_session(os.getenv("FEEDS_DATABASE_URL"), echo=False)
    except Exception as e:
        logging.error(f"Error connecting to the database: {e}")
        return str(e), 500

    # Fetch geopolygons within the bounding box
    try:
        geopolygons = (
            session.query(Geopolygon)
            .filter(Geopolygon.geometry.ST_Intersects(bounding_box))
            .all()
        )
        geopolygons_ids = [geopolygon.osm_id for geopolygon in geopolygons]
    except Exception as e:
        logging.error(f"Error fetching geopolygons: {e}")
        return str(e), ERROR_STATUS_CODE

    try:
        logging.info(f"Found {len(geopolygons)} geopolygons within the bounding box.")
        logging.info(f"The osm_ids of the geopolygons are: {geopolygons_ids}")

        # Map geopolygons into shapes
        wkb_geopolygons = {
            geopolygon.osm_id: {
                "polygon": to_shape(geopolygon.geometry),
                "object": geopolygon,
            }
            for geopolygon in geopolygons
        }

        # Ensure geometries are valid
        for geopolygon in wkb_geopolygons.values():
            if not geopolygon["polygon"].is_valid:
                geopolygon["polygon"] = make_valid(geopolygon["polygon"])

        points = [to_shape(point) for point in wkt_points]
        points_match = {}

        # Match points to geopolygons
        for point in points:
            for osm_id, geopolygon in wkb_geopolygons.items():
                if geopolygon["polygon"].contains(point):
                    point_id = str(point)
                    if point_id not in points_match:
                        points_match[point_id] = []
                    points_match[point_id].append(geopolygon["object"])

        # Clean up duplicate admin levels
        proper_match_geopolygons = {}
        for point, geopolygons in points_match.items():
            if len(geopolygons) > 1:
                admin_levels = {g.admin_level for g in geopolygons}
                if len(admin_levels) == len(geopolygons):
                    valid_iso_3166_1 = any(g.iso_3166_1_code for g in geopolygons)
                    valid_iso_3166_2 = any(g.iso_3166_2_code for g in geopolygons)
                    if not valid_iso_3166_1 or not valid_iso_3166_2:
                        logging.info(f"Invalid ISO codes for point: {point}")
                        continue
                    geopolygons.sort(key=lambda x: x.admin_level)
                    geopolygon_as_string = ", ".join([str(g.osm_id) for g in geopolygons])
                    if geopolygon_as_string not in proper_match_geopolygons:
                        proper_match_geopolygons[geopolygon_as_string] = {
                            "geopolys": geopolygons,
                            "count": 0,
                        }
                    proper_match_geopolygons[geopolygon_as_string]["count"] += 1

        unmatched_points = len(wkt_points) - sum(
            item["count"] for item in proper_match_geopolygons.values()
        )
        logging.info(f"Unmatched points: {unmatched_points}")
        response = build_response(
            proper_match_geopolygons, len(wkt_points), unmatched_points
        )
        logging.info(f"Response: {response}")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(f"{execution_id}/{uuid.uuid4()}.json")
        blob.upload_from_string(json.dumps(response, indent=2))
        blob.make_public()

        # Save the response to GCP bucket
        return response, 200
    except Exception as e:
        logging.error(f"Error processing geopolygons: {e}")
        return str(e), ERROR_STATUS_CODE
