import json
import logging
import os
from collections import defaultdict
from typing import Dict, Tuple, List, Optional
import pycountry

import flask
from google.cloud import storage
from shapely.geometry import Polygon, mapping
from database_gen.sqlacodegen_models import Geopolygon
from helpers.database import with_db_session
from sqlalchemy.orm import Session
from helpers.logger import Logger
from geoalchemy2.shape import to_shape
from common import ERROR_STATUS_CODE
from shapely.validation import make_valid
import matplotlib.pyplot as plt

# Initialize logging
logging.basicConfig(level=logging.INFO)

def generate_color(points_match, max_match, colormap_name="OrRd"):
    """
    Generate a color based on the points_match value using a matplotlib colormap.
    """
    colormap = plt.get_cmap(colormap_name)
    # Restrict normalized_value to the upper half of the spectrum (0.5 to 1)
    normalized_value = 0.5 + 0.5 * (points_match / max_match)
    rgba = colormap(normalized_value)  # Returns RGBA
    return f"rgba({int(rgba[0] * 255)}, {int(rgba[1] * 255)}, {int(rgba[2] * 255)}, {rgba[3]})"


class ReverseGeolocation:
    def __init__(
        self,
        osm_id: int,
        iso_3166_1: Optional[str],
        iso_3166_2: Optional[str],
        name: str,
        admin_level: int,
        points_match: int,
    ):
        self.osm_id = osm_id
        self.iso_3166_1 = iso_3166_1
        self.iso_3166_2 = iso_3166_2
        self.name = name
        self.admin_level = admin_level
        self.points_match = points_match
        self.children: List[ReverseGeolocation] = []
        self.parent: Optional[ReverseGeolocation] = None
        self.geometry: Optional[Polygon] = None

    def __str__(self) -> str:
        return f"{self.osm_id} - {self.name} - {self.points_match}"

    def set_geometry(self, geopolygon: Geopolygon) -> None:
        shape = to_shape(geopolygon.geometry)
        if shape.is_valid:
            self.geometry = shape
        else:
            self.geometry = make_valid(shape)

    @staticmethod
    def from_dict(data: dict, parent: Optional["ReverseGeolocation"] = None) -> List["ReverseGeolocation"]:
        nodes = []
        locations = data if isinstance(data, list) else data.get("grouped_matches", [])
        for location in locations:
            node = ReverseGeolocation(
                osm_id=location["osm_id"],
                iso_3166_1=location.get("iso_3166_1"),
                iso_3166_2=location.get("iso_3166_2"),
                name=location["name"],
                admin_level=location["admin_level"],
                points_match=location["points_match"],
            )
            if parent:
                node.parent = parent
            nodes.append(node)
            if "sub_levels" in location:
                node.children = ReverseGeolocation.from_dict(location["sub_levels"], parent=node)
        return nodes

    def to_dict(self) -> dict:
        return {
            "osm_id": self.osm_id,
            "iso_3166_1": self.iso_3166_1,
            "iso_3166_2": self.iso_3166_2,
            "name": self.name,
            "admin_level": self.admin_level,
            "points_match": self.points_match,
            "sub_levels": [child.to_dict() for child in self.children],
        }

    def get_level(self, target_level: int, current_level: int = 0) -> List["ReverseGeolocation"]:
        if current_level == target_level:
            return [self]
        results = []
        for child in self.children:
            results.extend(child.get_level(target_level, current_level + 1))
        return results

    def get_leaves(self) -> List["ReverseGeolocation"]:
        if not self.children:
            return [self]
        leaves = []
        for child in self.children:
            leaves.extend(child.get_leaves())
        return leaves

    def get_country_code(self) -> str:
        if self.iso_3166_1:
            return self.iso_3166_1
        if self.parent:
            return self.parent.get_country_code()
        return ""

    def get_display_name(self) -> str:
        display_name = self.name
        if self.iso_3166_1:
            try:
                flag = pycountry.countries.get(alpha_2=self.iso_3166_1).flag
                display_name = f"{flag} {display_name}"
            except AttributeError:
                pass
        if self.parent:
            display_name = f"{self.parent.get_display_name()}, {display_name}"
        return display_name

    def get_geojson_feature(self, max_leaves_points) -> Dict:
        if not self.geometry:
            return {}
        return {
            "type": "Feature",
            "properties": {
                "osm_id": self.osm_id,
                "country_code": self.get_country_code(),
                "display_name": self.get_display_name(),
                "points_match": self.points_match,
                "color": generate_color(self.points_match, max_leaves_points),
            },
            "geometry": mapping(self.geometry),
        }


def parse_request_parameters(request: flask.Request) -> Tuple[str, int, int, str]:
    """
    Parse the request parameters and return the execution ID, number of batches, and retry count.
    """
    logging.info("Parsing request parameters.")
    try:
        retry_count = int(request.headers.get("X-CloudTasks-TaskRetryCount", 0))
    except ValueError:
        logging.error(
            f"Error parsing retry count: {request.headers.get('X-CloudTasks-TaskRetryCount')}. Defaulting to 0."
        )
        retry_count = 0

    request_json = request.get_json(silent=True)
    if (not request_json
            or "execution_id" not in request_json
            or "n_batches" not in request_json
            or "stable_id" not in request_json):
        raise ValueError("Missing required 'execution_id', 'stable_id' or 'n_batches' in the request.")

    return (
        request_json["execution_id"],
        int(request_json["n_batches"]),
        retry_count,
        request_json["stable_id"]
    )


def list_blobs(bucket_name: str, prefix: str = "") -> List[storage.Blob]:
    """
    List all JSON files in a GCP bucket with the given prefix.
    """
    storage_client = storage.Client()
    blobs = list(storage_client.list_blobs(bucket_name, prefix=prefix))
    return [blob for blob in blobs if blob.name.endswith(".json")]


def merge_reverse_geolocations(locations: List[ReverseGeolocation]) -> List[ReverseGeolocation]:
    """
    Recursively merge a list of ReverseGeolocation objects.
    """
    if not locations:
        return []

    # Group by osm_id
    per_osm_id = defaultdict(list)
    for location in locations:
        per_osm_id[location.osm_id].append(location)

    merged_results = []
    for osm_id, grouped_locations in per_osm_id.items():
        # Aggregate points_match and merge children
        total_points_match = sum(loc.points_match for loc in grouped_locations)
        chosen_location = grouped_locations[0]
        chosen_location.points_match = total_points_match

        # Merge children recursively
        all_children = [child for loc in grouped_locations for child in loc.children]
        chosen_location.children = merge_reverse_geolocations(all_children)

        merged_results.append(chosen_location)

    return merged_results


def reverse_geolocation_aggregate(
    request: flask.Request,
) -> Tuple[str, int] | Tuple[Dict, int]:
    """
    Handle reverse geolocation aggregation by merging JSON data into a single result.
    """
    Logger.init_logger()

    source_bucket = os.getenv("BUCKET_NAME")
    max_retry = int(os.getenv("MAX_RETRY", 10))

    if not source_bucket:
        logging.error("Source bucket name not set.")
        return "Source bucket name not set.", ERROR_STATUS_CODE

    try:
        execution_id, n_batches, retry_count, stable_id = parse_request_parameters(request)
        logging.info(f"Execution ID: {execution_id}, Number of batches: {n_batches}, Retry Count: {retry_count}")
    except ValueError as e:
        return handle_error("Error parsing request parameters", e, ERROR_STATUS_CODE)

    try:
        files = validate_files_ready(source_bucket, execution_id, n_batches, retry_count, max_retry)
    except ValueError as e:
        return handle_error("Validation error", e)

    try:
        aggregated_data, total_points, geojson_data = aggregate_data_from_files(files)
        logging.info(f"Aggregated {total_points} points from {len(files)} files.")
    except Exception as e:
        return handle_error("Error aggregating data", e, ERROR_STATUS_CODE)

    try:
        save_aggregated_data(source_bucket, execution_id, aggregated_data, total_points)
        save_geojson(os.getenv("DATASETS_BUCKET_NAME"), stable_id, geojson_data)
    except Exception as e:
        return handle_error("Error saving aggregated data", e, ERROR_STATUS_CODE)

    return "Done", 200


def validate_files_ready(
    bucket_name: str, prefix: str, n_batches: int, retry_count: int, max_retry: int
) -> List[storage.Blob]:
    """
    Validate that the required number of files is available in the bucket.
    """
    files = list_blobs(bucket_name, prefix)
    logging.info(f"Found {len(files)} files in the bucket.")

    if len(files) < n_batches:
        if retry_count < max_retry:
            logging.warning("Files are not ready yet. Retrying...")
            raise ValueError("Not yet ready to process")
        logging.error("Maximum retries exceeded. Aborting.")
        raise ValueError("Maximum retries exceeded.")
    return files

@with_db_session
def aggregate_data_from_files(files: List[storage.Blob], session: Session) -> Tuple[List[Dict], int, Dict]:
    """
    Aggregate data from the given list of files.
    """
    results: List[ReverseGeolocation] = []
    total_points = 0

    for file in files:
        if file.name.endswith("output.json"):
            continue
        json_data = json.loads(file.download_as_string())
        results.extend(ReverseGeolocation.from_dict(json_data))
        total_points += json_data.get("summary", {}).get("total_points", 0)

    root_nodes = merge_reverse_geolocations(results)
    leaves = [leaf for node in root_nodes for leaf in node.get_leaves()]
    max_leaves_points = max(leaf.points_match for leaf in leaves)
    osm_ids = [leaf.osm_id for leaf in leaves]

    leaves_geopolygons = (
        session.query(Geopolygon).filter(Geopolygon.osm_id.in_(osm_ids)).all()
    )
    geopolygons_map = {geopolygon.osm_id: geopolygon for geopolygon in leaves_geopolygons}
    for leaf in leaves:
        leaf.set_geometry(geopolygons_map[leaf.osm_id])
    geojson_map = {
        "type": "FeatureCollection",
        "features": [node.get_geojson_feature(max_leaves_points) for node in leaves],
    }
    return [node.to_dict() for node in root_nodes], total_points, geojson_map

def save_geojson(bucket_name: str, stable_id: str, geojson: Dict) -> None:
    """
    Save the GeoJSON data as a JSON file in the specified bucket.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{stable_id}/geolocation-1.geojson")
    blob.upload_from_string(json.dumps(geojson))
    blob.make_public()
    logging.info(f"GeoJSON data saved to {blob.name}")

def save_aggregated_data(bucket_name: str,
                         execution_id: str,
                         aggregated_data: List[Dict],
                         total_points: int) -> None:
    """
    Save the aggregated data as a JSON file in the specified bucket.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{execution_id}/output.json")
    matched_points = sum(node["points_match"] for node in aggregated_data)
    output = {
        "summary" : {
            "total_points": total_points,
            "matched_points": matched_points,
            "unmatched_points": total_points - matched_points,
        },
        "locations": aggregated_data,
    }
    blob.upload_from_string(json.dumps(output, indent=2))
    logging.info(f"Aggregated data saved to {blob.name}")


def handle_error(message: str, exception: Exception, error_code: int = 400) -> Tuple[str, int]:
    """
    Log and handle an error, returning an appropriate response.
    """
    logging.error(f"{message}: {exception}")
    return str(exception), error_code
