#
#
#   MobilityData 2025
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# This module provides the PmtilesBuilder class and related functions to generate PMTiles files
# from GTFS datasets. It handles downloading required files from Google Cloud Storage, processing
# and indexing GTFS data, generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles,
# and uploading the results back to GCS.
import csv
import json
import logging
import os
import shutil
import subprocess
from logging import DEBUG
from google.cloud import storage

from shared.helpers.logger import get_logger

# Files are stored locally to be able to run tippecanoe on them. This is the directory
local_dir = "./workdir"


def build_pmtiles_handler(payload) -> dict:
    """
    Entrypoint for building PMTiles files from a GTFS dataset.
    """
    try:
        feed_stable_id, dataset_stable_id = PmtilesBuilder._get_parameters(payload)
        builder = PmtilesBuilder(
            feed_stable_id=feed_stable_id, dataset_stable_id=dataset_stable_id
        )
        return builder.build_pmtiles()
    except Exception as e:
        return {"error": f"Failed to start PMTiles build: {e}"}


class PmtilesBuilder:
    """
    Orchestrates the end-to-end process of generating PMTiles files from GTFS datasets.

    This class manages downloading required files from Google Cloud Storage, processing and indexing GTFS data,
    generating GeoJSON and JSON outputs, running Tippecanoe to create PMTiles, and uploading results back to GCS.
    Temporary files are stored in the global `workdir` directory for local processing.
    """

    def __init__(
        self,
        feed_stable_id: str | None = None,
        dataset_stable_id: str | None = None,
    ):
        self.bucket = None
        self.feed_stable_id = feed_stable_id
        self.dataset_stable_id = dataset_stable_id
        self.bucket_name = os.getenv("DATASETS_BUCKET_NAME")
        self.logger = get_logger(PmtilesBuilder.__name__, dataset_stable_id)

        self.stop_times_index = {}
        self.stop_times_by_trip = None

        self.stop_times_file = f"{local_dir}/stop_times.txt"
        self.shapes_file = f"{local_dir}/shapes.txt"
        self.trips_file = f"{local_dir}/trips.txt"
        self.routes_file = f"{local_dir}/routes.txt"
        self.stops_file = f"{local_dir}/stops.txt"

    @staticmethod
    def _get_parameters(payload):
        """
        Get parameters from the payload and environment variables.
        """
        feed_stable_id = payload.get("feed_stable_id", None)
        dataset_stable_id = payload.get("dataset_stable_id", None)
        return feed_stable_id, dataset_stable_id

    def build_pmtiles(self) -> dict:
        try:
            if not self.bucket_name:
                return {
                    "error": "DATASETS_BUCKET_NAME environment variable is not defined."
                }
            if not self.feed_stable_id or not self.dataset_stable_id:
                return {
                    "error": "Both feed_stable_id and dataset_stable_id must be defined."
                }
            if self.feed_stable_id not in self.dataset_stable_id:
                return {
                    "error": (
                        "feed_stable_id %s is not a prefix of dataset_stable_id %s."
                        % (self.feed_stable_id, self.dataset_stable_id)
                    )
                }

            self.logger.info(
                "Starting PMTiles build for dataset %s", self.dataset_stable_id
            )
            unzipped_files_path = (
                f"{self.feed_stable_id}/{self.dataset_stable_id}/extracted"
            )

            self._download_files_from_gcs(unzipped_files_path)

            self._create_routes_geojson()

            self._run_tippecanoe("routes-output.geojson", "routes.pmtiles")

            self._create_stops_geojson()

            self._run_tippecanoe("stops-output.geojson", "stops.pmtiles")

            self._create_routes_json()

            files_to_upload = ["routes.pmtiles", "stops.pmtiles", "routes.json"]
            self._upload_files_to_gcs(files_to_upload)

            # List files in the relevant bucket folder instead of local_dir

            if logging.getLogger().isEnabledFor(DEBUG):
                gcs_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles/"
                try:  # We don`t want an error here to abort the whole pmtiles operation.
                    blobs = list(self.bucket.list_blobs(prefix=gcs_prefix))
                    file_list = "\n".join(
                        f"{blob.name} ({blob.size} bytes)" for blob in blobs
                    )
                    self.logger.debug("GCS files in %s:\n%s", gcs_prefix, file_list)
                except Exception as e:
                    self.logger.error(
                        "Could not list files in bucket %s for path %s: %s",
                        self.bucket_name,
                        gcs_prefix,
                        e,
                    )

            return {
                "message": f"Pmtiles successfully created for dataset {self.dataset_stable_id}."
            }
        except Exception as e:
            logging.exception(
                "Failed to build PMTiles for dataset %s", self.dataset_stable_id
            )
            return {
                "error": f"Failed to build PMTiles for dataset {self.dataset_stable_id}: {e}"
            }

    def _download_files_from_gcs(self, unzipped_files_path):
        self.logger.info(
            "Downloading dataset from GCS bucket %s, directory %s",
            self.bucket_name,
            unzipped_files_path,
        )
        try:
            self.logger.debug("Initializing storage client")
            self.bucket = storage.Client(
                # client_options={"api_endpoint": "http://localhost:4443"}
            ).get_bucket(self.bucket_name)
            self.logger.debug("Getting blobs with prefix: %s", unzipped_files_path)
            blobs = list(self.bucket.list_blobs(prefix=unzipped_files_path))
            self.logger.debug("Found %d blobs", len(blobs))
            if not blobs:
                raise Exception(
                    f"Directory '{unzipped_files_path}' does not exist or is empty in bucket '{self.bucket_name}'."
                )

            if os.path.exists(local_dir):
                shutil.rmtree(local_dir)
            os.makedirs(local_dir, exist_ok=True)
            file_names = [
                "routes.txt",
                "shapes.txt",
                "stop_times.txt",
                "trips.txt",
                "stops.txt",
            ]
            for file_name in file_names:
                blob_path = f"{unzipped_files_path}/{file_name}"
                blob = self.bucket.blob(blob_path)
                local_path = os.path.join(local_dir, file_name)
                blob.download_to_filename(local_path)
                self.logger.debug("Downloaded %s to %s", blob_path, local_path)
            return
        except Exception as e:
            raise Exception(f"Failed to download files from GCS: {e}") from e

    def _upload_files_to_gcs(self, file_to_upload):
        dest_prefix = f"{self.feed_stable_id}/{self.dataset_stable_id}/pmtiles"
        self.logger.info(
            "Uploading files to GCS bucket %s, directory %s",
            self.bucket_name,
            dest_prefix,
        )
        try:
            blobs_to_delete = list(self.bucket.list_blobs(prefix=dest_prefix + "/"))
            for blob in blobs_to_delete:
                blob.delete()
                self.logger.debug("Deleted existing blob: %s", blob.name)
            for file_name in file_to_upload:
                file_path = os.path.join(local_dir, file_name)
                if not os.path.exists(file_path):
                    self.logger.warning("File not found: %s", file_path)
                    continue
                blob_path = f"{dest_prefix}/{file_name}"
                blob = self.bucket.blob(blob_path)
                blob.upload_from_filename(file_path)
                self.logger.debug(
                    "Uploaded %s to gs://%s/%s",
                    file_path,
                    self.bucket_name,
                    blob_path,
                )
        except Exception as e:
            raise Exception(f"Failed to upload files to GCS: {e}") from e

    def _create_shapes_index(self) -> dict:
        """
        Create an index for shapes.txt file to quickly access shape points by shape_id.
        We create the index to save memory. With the index, we keep a list of positions in the file for each shape.
        If instead we read the whole file into memory, we would need 2 floats for the longitude and latitude plus an
        int for the sequence number for each point.
        The largest number of shapes we have currently in a dataset is 37 millions.
        This means about 900 MB if we have the index, and 1.6 GB if read the coordinates in memory.
        Returns:
            A dictionary with key shaped_id and values a list of positions in the shapes.txt file.
        """
        self.logger.info("Creating shapes index")
        shapes_index = {}
        try:
            with open(self.shapes_file, "r", encoding="utf-8", newline="") as f:
                header = f.readline()
                columns = next(csv.reader([header]))
                shapes_index["columns"] = columns
                count = 0
                while True:
                    pos = f.tell()
                    line = f.readline()
                    if not line:
                        break
                    row = dict(zip(columns, next(csv.reader([line]))))
                    sid = row["shape_id"]
                    shapes_index.setdefault(sid, []).append(pos)
                    count += 1
                    if count % 1000000 == 0:
                        self.logger.debug("Indexed %d lines so far...", count)
            self.logger.debug("Total indexed lines: %d", count)
            self.logger.debug("Total unique shape_ids: %d", len(shapes_index))
        except Exception as e:
            raise Exception(f"Failed to create shapes index: {e}") from e
        return shapes_index

    def _read_csv(self, filename):
        try:
            self.logger.debug("Loading %s", filename)
            with open(filename, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except Exception as e:
            raise Exception(f"Failed to read CSV file {filename}: {e}") from e

    def _get_shape_points(self, shape_id, index):
        self.logger.debug("Getting shape points for shape_id %s", shape_id)
        try:
            points = []
            with open(self.shapes_file, "r", encoding="utf-8", newline="") as f:
                for pos in index.get(shape_id, []):
                    f.seek(pos)
                    line = f.readline()
                    row = dict(zip(index["columns"], next(csv.reader([line]))))
                    points.append(
                        (
                            float(row["shape_pt_lon"]),
                            float(row["shape_pt_lat"]),
                            int(row["shape_pt_sequence"]),
                        )
                    )
            points.sort(key=lambda x: x[2])
            self.logger.debug(
                "  Found %d points for shape_id %s", len(points), shape_id
            )
            return [pt[:2] for pt in points]
        except Exception as e:
            raise Exception(f"Failed to get shape points for {shape_id}: {e}") from e

    def _create_routes_geojson(self):
        try:
            shapes_index = self._create_shapes_index()
            self.logger.info("Creating routes geojson (optimized for memory)")

            # Load stops into memory (usually not huge)
            # Used only if there is no shapes for a route
            coordinates_indexed_by_stop = {
                s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
                for s in self._read_csv(self.stops_file)
            }

            # We want the shape of a route. To do that we find one trip for each route. We will assume that all
            # trips for a route have the same shape_id. If not I am not sure how to represent this in the route map
            # when we select a route.
            shape_map_indexed_by_route = {}
            trip_map_indexed_by_route = {}
            with open(self.trips_file, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    trip_id = row["trip_id"]
                    route_id = row["route_id"]
                    shape_id = row.get("shape_id", "")
                    if shape_id and route_id not in shape_map_indexed_by_route:
                        shape_map_indexed_by_route[route_id] = shape_id
                    if trip_id and route_id not in trip_map_indexed_by_route:
                        trip_map_indexed_by_route[route_id] = trip_id

            features = []
            missing_coordinates_routes = set()
            routes_geojson = f"{local_dir}/routes-output.geojson"
            with open(routes_geojson, "w", encoding="utf-8") as geojson_file:
                geojson_file.write('{"type": "FeatureCollection", "features": [\n')
                first = True
                with open(
                    self.routes_file, newline="", encoding="utf-8"
                ) as routes_file:
                    for i, route in enumerate(csv.DictReader(routes_file), 1):
                        route_id = route["route_id"]

                        shape_id = shape_map_indexed_by_route.get(route_id, "")

                        coordinates = []
                        if shape_id:
                            coordinates = self._get_shape_points(shape_id, shapes_index)
                        if not coordinates:
                            # We don't have the coordinates for the shape, fallback on stop_times and stops
                            trip_id = trip_map_indexed_by_route.get(route_id, "")

                            if trip_id:
                                trip_stop_times = self._get_trip_stop_times(trip_id)
                                # We assume stop_times is already sorted by stop_sequence in the file.
                                # According to the SPECS:
                                #    The values must increase along the trip but do not need to be consecutive.
                                coordinates = [
                                    coordinates_indexed_by_stop[stop_id]
                                    for stop_id in trip_stop_times
                                    if stop_id in coordinates_indexed_by_stop
                                ]
                        if not coordinates:
                            missing_coordinates_routes.add(route_id)
                            continue
                        feature = {
                            "type": "Feature",
                            "properties": {k: route[k] for k in route},
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coordinates,
                            },
                        }

                        if not first:
                            geojson_file.write(",\n")
                        geojson_file.write(json.dumps(feature))
                        first = False

                        if i % 100 == 0 or i == 1:
                            self.logger.debug(
                                "Processed route %d (route_id: %s)", i, route_id
                            )

                geojson_file.write("\n]}")

            if missing_coordinates_routes:
                self.logger.info(
                    "Routes without coordinates: %s", list(missing_coordinates_routes)
                )
            self.logger.debug(
                "Wrote %d features to routes-output.geojson", len(features)
            )
        except Exception as e:
            raise Exception(f"Failed to create routes GeoJSON: {e}") from e

    def _get_trip_stop_times(self, trip_id):
        # Lazy instantiation of the dictionary, because we may not need it al all if there is a shape.
        if self.stop_times_by_trip is None:
            self.stop_times_by_trip = {}
            with open(self.stop_times_file, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self.stop_times_by_trip.setdefault(row["trip_id"], []).append(
                        row["stop_id"]
                    )

        return self.stop_times_by_trip.get(trip_id, [])

    def _run_tippecanoe(self, input_file, output_file):
        self.logger.info("Running tippecanoe for input file %s", input_file)
        try:
            cmd = [
                "tippecanoe",
                "-o",
                f"{local_dir}/{output_file}",
                "--force",
                "--no-tile-size-limit",
                "-zg",
                f"{local_dir}/{input_file}",
            ]
            self.logger.debug("Running command: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                self.logger.debug("Tippecanoe output:\n%s", result.stdout)
            if result.returncode != 0:
                self.logger.error("Tippecanoe error:\n%s", result.stderr)
                raise Exception(f"Tippecanoe failed with exit code {result.returncode}")
            self.logger.debug("Tippecanoe command executed successfully.")
        except Exception as e:
            raise Exception(
                f"Failed to run tippecanoe for output file {output_file}: {e}"
            ) from e

    def _create_stops_geojson(self):
        self.logger.info("Creating stops geojson...")
        try:
            stops = self._read_csv(f"{local_dir}/stops.txt")
            if isinstance(stops, dict) and "error" in stops:
                return stops
            self.logger.debug("Loaded %d stops.", len(stops))

            features = []
            for i, stop in enumerate(stops, 1):
                try:
                    lon = float(stop["stop_lon"])
                    lat = float(stop["stop_lat"])
                except (KeyError, ValueError):
                    self.logger.info(
                        "Skipping stop %s: invalid coordinates",
                        stop.get("stop_id", ""),
                    )
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "properties": {k: stop[k] for k in stop},
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    }
                )

            geojson = {"type": "FeatureCollection", "features": features}
            stops_geojson = f"{local_dir}/stops-output.geojson"

            self.logger.debug(
                "Writing %d features to stops-output.geojson for dataset %s",
                len(features),
                self.dataset_stable_id,
            )
            with open(stops_geojson, "w", encoding="utf-8") as f:
                json.dump(geojson, f)
        except Exception as e:
            raise Exception(
                f"Failed to create stops GeoJSON for dataset {self.dataset_stable_id}: {e}"
            ) from e

    def _create_routes_json(self):
        self.logger.info("Creating routes json...")
        try:
            routes = []
            with open(f"{local_dir}/routes.txt", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    route = {
                        "routeId": row.get("route_id", ""),
                        "routeName": row.get("route_long_name", ""),
                        "color": f"#{row.get('route_color', '000000')}",
                        "textColor": f"#{row.get('route_text_color', 'FFFFFF')}",
                        "routeType": f"{row.get('route_type', '3')}",
                    }
                    routes.append(route)

            with open(f"{local_dir}/routes.json", "w", encoding="utf-8") as f:
                json.dump(routes, f, ensure_ascii=False, indent=4)

            self.logger.debug("Converted %d routes to routes.json.", len(routes))
        except Exception as e:
            raise Exception(f"Failed to create routes JSON for dataset: {e}") from e
